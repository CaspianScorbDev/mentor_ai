from app.integrations.search import _extract_text, _parse_results, _unwrap_url

SAMPLE_HTML = """
<div class="result results_links results_links_deep web-result">
  <h2 class="result__title">
    <a rel="nofollow" class="result__a"
       href="//duckduckgo.com/l/?uddg=https%3A%2F%2Ffastapi.tiangolo.com%2Fasync%2F&amp;rut=abc">
      Concurrency and <b>async</b> / await - FastAPI
    </a>
  </h2>
  <a class="result__snippet">Details about <b>async</b> and await in FastAPI.</a>
</div>
<div class="result results_links results_links_deep web-result">
  <h2 class="result__title">
    <a rel="nofollow" class="result__a"
       href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fstackoverflow.com%2Fq%2F1&amp;rut=xyz">
      What does async actually do?
    </a>
  </h2>
  <a class="result__snippet">Async def in a path operation function...</a>
</div>
"""


def test_parse_results_extracts_title_url_snippet() -> None:
    results = _parse_results(SAMPLE_HTML, limit=5)
    assert len(results) == 2
    assert results[0].title == "Concurrency and async / await - FastAPI"
    assert results[0].url == "https://fastapi.tiangolo.com/async/"
    assert "async" in results[0].snippet
    assert results[1].url == "https://stackoverflow.com/q/1"


def test_parse_results_respects_limit() -> None:
    assert len(_parse_results(SAMPLE_HTML, limit=1)) == 1


def test_parse_results_empty_page() -> None:
    assert _parse_results("<html></html>", limit=5) == []


def test_unwrap_url_decodes_redirect() -> None:
    href = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage&amp;rut=z"
    assert _unwrap_url(href) == "https://example.com/page"


def test_unwrap_url_passthrough_direct_link() -> None:
    assert _unwrap_url("https://example.com") == "https://example.com"


def test_extract_text_strips_scripts_and_tags() -> None:
    page = (
        "<html><head><style>.a{color:red}</style>"
        "<script>evil()</script></head>"
        "<body>Hello <b>world</b> &amp; friends</body></html>"
    )
    text = _extract_text(page)
    assert "Hello" in text
    assert "world" in text
    assert "& friends" in text
    assert "evil()" not in text
    assert ".a{color:red}" not in text
    assert "<b>" not in text
