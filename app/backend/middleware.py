"""Cross-cutting HTTP middleware: correlation ids, rate limiting, API key."""

import asyncio
import hmac
import logging
import re
import time
import uuid
from collections import deque
from functools import lru_cache
from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network
from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse
from starlette.requests import Request as StarletteRequest

from app.core.config import cfg
from app.core.logging import bind_request_id

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
_X_FORWARDED_FOR = "X-Forwarded-For"
_API_KEY_HEADER = "X-API-Key"
_SAFE_REQUEST_ID = re.compile(r"[^A-Za-z0-9._-]")
_MAX_REQUEST_ID = 64
_EXEMPT_SUFFIXES = ("/health",)
_EXEMPT_PREFIXES = ("/docs", "/redoc", "/openapi.json")

RequestCall = Any


def _headers(scope: dict[str, Any]) -> dict[str, str]:
    return {
        key.decode("latin-1"): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }


@lru_cache(maxsize=8)
def _parse_networks(entries: tuple[str, ...]) -> tuple[Any, ...]:
    """Parse `trusted_proxies` (IPs/CIDRs); invalid entries are ignored."""
    networks = []
    for entry in entries:
        try:
            networks.append(ip_network(entry, strict=False))
        except ValueError:
            continue
    return tuple(networks)


def _networks() -> tuple[Any, ...]:
    return _parse_networks(tuple(cfg.application.trusted_proxies))


def _is_trusted_proxy(host: str) -> bool:
    networks = _networks()
    if not networks:
        return False
    try:
        address: IPv4Address | IPv6Address = ip_address(host)
    except ValueError:
        return False
    return any(address in network for network in networks)


def client_key(request: StarletteRequest) -> str:
    """Bucket key for rate limiting: real client IP, trusting only known proxies."""
    peer = request.client.host if request.client else "unknown"
    if _is_trusted_proxy(peer):
        forwarded = request.headers.get(_X_FORWARDED_FOR)
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                try:
                    ip_address(first)
                except ValueError:
                    pass
                else:
                    return first
    return peer


class RequestContextMiddleware:
    """Attach a correlation id to every request and every log line (pure ASGI)."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = _headers(scope)
        incoming = headers.get(REQUEST_ID_HEADER, "")
        request_id = _SAFE_REQUEST_ID.sub("", incoming)[:_MAX_REQUEST_ID] or uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_id(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                raw = message.setdefault("headers", [])
                raw.append((REQUEST_ID_HEADER.encode("latin-1"), request_id.encode("latin-1")))
            await send(message)

        with bind_request_id(request_id):
            await self.app(scope, receive, send_with_id)


class RateLimitMiddleware:
    """In-memory sliding-window limiter, keyed by client IP.

    Stale buckets are swept on a timer so the table cannot grow without bound
    when clients come and go (or when an attacker rotates source addresses).
    """

    _SWEEP_INTERVAL = 10.0
    _MAX_KEYS = 10_000

    def __init__(self, app: Any, *, per_minute: int, burst: int) -> None:
        self.app = app
        self._window = 60.0
        self._capacity = per_minute + max(0, burst)
        self._hits: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()
        self._next_sweep = time.monotonic() + self._SWEEP_INTERVAL

    def _sweep(self, now: float) -> None:
        stale: list[str] = []
        for key, bucket in self._hits.items():
            while bucket and now - bucket[0] > self._window:
                bucket.popleft()
            if not bucket:
                stale.append(key)
        for key in stale:
            del self._hits[key]

        # Hard bound: dict keeps insertion order, so the head is the oldest.
        overflow = len(self._hits) - self._MAX_KEYS
        if overflow > 0:
            for key in list(self._hits)[:overflow]:
                del self._hits[key]
            logger.warning("rate limit table trimmed to %s keys", self._MAX_KEYS)

        self._next_sweep = now + self._SWEEP_INTERVAL

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        scope_request = StarletteRequest(scope)
        if scope_request.method == "OPTIONS" or _is_exempt(scope["url"].get("path", "")):
            await self.app(scope, receive, send)
            return

        now = time.monotonic()
        async with self._lock:
            if now >= self._next_sweep:
                self._sweep(now)

            key = client_key(scope_request)
            bucket = self._hits.get(key)
            if bucket is None:
                bucket = deque()
                self._hits[key] = bucket
            while bucket and now - bucket[0] > self._window:
                bucket.popleft()

            if len(bucket) >= self._capacity:
                retry_after = max(1, int(self._window - (now - bucket[0])))
                logger.warning("rate limit exceeded for %s", key)
                response = JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Слишком много запросов, попробуйте позже."},
                    headers={"Retry-After": str(retry_after)},
                )
                await response(scope, receive, send)
                return
            bucket.append(now)

        await self.app(scope, receive, send)


class ApiKeyMiddleware:
    """Optional shared-secret guard for the public API (pure ASGI)."""

    def __init__(self, app: Any, *, api_key: str) -> None:
        self.app = app
        self._api_key = api_key

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        scope_request = StarletteRequest(scope)
        if scope_request.method == "OPTIONS" or _is_exempt(scope["url"].get("path", "")):
            await self.app(scope, receive, send)
            return

        headers = _headers(scope)
        provided = headers.get(_API_KEY_HEADER, "")
        if not hmac.compare_digest(provided, self._api_key):
            request_id = scope.get("state", {}).get("request_id", "-")
            response = JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Неверный или отсутствующий API-ключ."},
                headers={REQUEST_ID_HEADER: str(request_id)},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def _is_exempt(path: str) -> bool:
    if any(path.startswith(prefix) for prefix in _EXEMPT_PREFIXES):
        return True
    return any(path.endswith(suffix) for suffix in _EXEMPT_SUFFIXES)


def install_middleware(app: Any) -> None:
    """Register request-scoped middleware (add order: outermost runs last)."""
    application = cfg.application

    if application.api_key is not None and application.api_key.get_secret_value().strip():
        app.add_middleware(
            ApiKeyMiddleware, api_key=application.api_key.get_secret_value().strip()
        )

    if application.rate_limit_per_minute > 0:
        app.add_middleware(
            RateLimitMiddleware,
            per_minute=application.rate_limit_per_minute,
            burst=application.rate_limit_burst,
        )

    app.add_middleware(RequestContextMiddleware)
