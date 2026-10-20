import asyncio
import html
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from app.core.config import cfg

logger = logging.getLogger(__name__)

DDG_URL = "https://html.duckduckgo.com/html/"
DEFAULT_TIMEOUT = 8.0
DEFAULT_LIMIT = 5
DEFAULT_READ = 3
PAGE_TIMEOUT = 6.0
MAX_PAGE_CHARS = 1800

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    "Accept-Language": "ru,en;q=0.8",
}

_RESULT_ANCHOR_RE = re.compile(
    r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_SNIPPET_RE = re.compile(
    r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_WS_RE = re.compile(r"[ \t\r\f\v]+")


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    content: str = field(default="")


_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """One connection pool for the process; building a client per search threw
    away keep-alive and paid a fresh TLS handshake on every query."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=cfg.search.timeout,
            follow_redirects=True,
            headers=_HEADERS,
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


def _clean(fragment: str) -> str:
    text = _TAG_RE.sub("", fragment)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _extract_text(page: str) -> str:
    stripped = _SCRIPT_RE.sub(" ", page)
    text = _TAG_RE.sub(" ", stripped)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def _unwrap_url(href: str) -> str:
    if href.startswith("//"):
        href = f"https:{href}"
    parsed = urlparse(href)
    target = parse_qs(parsed.query).get("uddg")
    if target:
        return unquote(target[0])
    return href


def _parse_results(page: str, limit: int) -> list[SearchResult]:
    anchors = _RESULT_ANCHOR_RE.findall(page)
    snippets = [_clean(fragment) for fragment in _SNIPPET_RE.findall(page)]

    results: list[SearchResult] = []
    for index, (href, title_html) in enumerate(anchors):
        if len(results) >= limit:
            break
        title = _clean(title_html)
        url = _unwrap_url(href)
        if not title or not url:
            continue
        snippet = snippets[index] if index < len(snippets) else ""
        results.append(SearchResult(title=title, url=url, snippet=snippet))
    return results


def _provider_order() -> list[str]:
    settings = cfg.search
    if settings.provider != "auto":
        return [settings.provider]
    order: list[str] = []
    if settings.has_brave:
        order.append("brave")
    if settings.searxng_url:
        order.append("searxng")
    order.append("duckduckgo")
    return order


async def _brave_search(
    client: httpx.AsyncClient, query: str, limit: int
) -> list[SearchResult]:
    settings = cfg.search
    if not settings.has_brave:
        return []
    assert settings.brave_api_key is not None
    response = await client.get(
        settings.brave_base_url,
        params={"q": query, "count": limit},
        headers={"X-Subscription-Token": settings.brave_api_key.get_secret_value()},
    )
    response.raise_for_status()
    payload = response.json()
    results: list[SearchResult] = []
    for item in payload.get("web", {}).get("results", [])[:limit]:
        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        if not title or not url:
            continue
        results.append(
            SearchResult(
                title=title,
                url=url,
                snippet=_clean(str(item.get("description", ""))),
            )
        )
    return results


async def _searxng_search(
    client: httpx.AsyncClient, query: str, limit: int
) -> list[SearchResult]:
    settings = cfg.search
    response = await client.get(
        f"{settings.searxng_url}/search",
        params={"q": query, "format": "json"},
    )
    response.raise_for_status()
    payload = response.json()
    results: list[SearchResult] = []
    for item in payload.get("results", [])[:limit]:
        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        if not title or not url:
            continue
        results.append(
            SearchResult(
                title=title,
                url=url,
                snippet=_clean(str(item.get("content", ""))),
            )
        )
    return results


async def _duckduckgo_search(
    client: httpx.AsyncClient, query: str, limit: int
) -> list[SearchResult]:
    response = await client.post(DDG_URL, data={"q": query})
    response.raise_for_status()
    return _parse_results(response.text, limit)


_PROVIDERS = {
    "brave": _brave_search,
    "searxng": _searxng_search,
    "duckduckgo": _duckduckgo_search,
}


async def _fetch_page(
    client: httpx.AsyncClient, url: str, *, semaphore: asyncio.Semaphore, max_chars: int
) -> str:
    async with semaphore:
        try:
            response = await client.get(url, timeout=cfg.search.page_timeout)
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - a page that won't load is simply skipped
            logger.debug("page fetch failed for %s: %s", url, exc)
            return ""
    return _extract_text(response.text)[:max_chars]


async def read_pages(results: list[SearchResult], *, read: int | None = None) -> None:
    """Best-effort: fill `content` on the top results with the page's main text."""
    settings = cfg.search
    count = settings.read_pages if read is None else read
    targets = [r for r in results[:count] if r.url]
    if not targets:
        return
    semaphore = asyncio.Semaphore(settings.max_concurrency)
    client = _get_client()
    texts = await asyncio.gather(
        *(
            _fetch_page(
                client, r.url, semaphore=semaphore, max_chars=settings.max_page_chars
            )
            for r in targets
        )
    )
    for result, text in zip(targets, texts, strict=False):
        result.content = text


async def search_web(
    query: str,
    *,
    limit: int | None = None,
) -> list[SearchResult]:
    """Run a web search across the configured providers.

    Providers are tried in order; the first one that returns results wins.
    Raises only when every provider fails, so callers can degrade gracefully.
    """
    query = query.strip()
    if not query:
        return []

    settings = cfg.search
    count = limit if limit is not None else settings.max_results
    errors: list[str] = []

    client = _get_client()
    for provider in _provider_order():
        handler = _PROVIDERS.get(provider)
        if handler is None:
            continue
        try:
            results = await handler(client, query, count)
        except Exception as exc:  # noqa: BLE001 - try the next provider
            errors.append(f"{provider}: {exc}")
            logger.warning("search provider %s failed: %s", provider, exc)
            continue
        if results:
            await read_pages(results)
            return results
        errors.append(f"{provider}: empty")

    raise RuntimeError("; ".join(errors) or "no search provider available")
