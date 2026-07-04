"""Fetcher unit tests — network is stubbed at the transport level via
httpx.MockTransport, so nothing here ever goes online."""

import httpx
import pytest

from insight_mcp.ingest import Fetcher, urls_from_sitemap


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Throttling is real code but tests must not wait 1s per request."""
    monkeypatch.setattr("insight_mcp.ingest.time.sleep", lambda s: None)


def make_fetcher(tmp_path, handler) -> Fetcher:
    fetcher = Fetcher(tmp_path / "cache")
    fetcher._client = httpx.Client(
        transport=httpx.MockTransport(handler), follow_redirects=True
    )
    return fetcher


def test_fetch_caches_and_skips_second_request(tmp_path):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(200, text="<html>page</html>")

    fetcher = make_fetcher(tmp_path, handler)
    assert fetcher.fetch("https://example.com/a") == "<html>page</html>"
    assert fetcher.fetch("https://example.com/a") == "<html>page</html>"
    fetcher.close()
    # one robots.txt + one page fetch, second call served from disk cache
    assert calls == ["https://example.com/robots.txt", "https://example.com/a"]


def test_fetch_honors_robots_disallow(tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private/")
        return httpx.Response(200, text="ok")

    fetcher = make_fetcher(tmp_path, handler)
    assert fetcher.fetch("https://example.com/private/doc") is None
    assert fetcher.fetch("https://example.com/public") == "ok"
    fetcher.close()


def test_fetch_unretrievable_robots_defaults_to_allowed(tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(403)
        return httpx.Response(200, text="ok")

    fetcher = make_fetcher(tmp_path, handler)
    assert fetcher.fetch("https://example.com/page") == "ok"
    fetcher.close()


def test_fetch_http_error_returns_none(tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(500)

    fetcher = make_fetcher(tmp_path, handler)
    assert fetcher.fetch("https://example.com/broken") is None
    fetcher.close()


SITEMAP_NS = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'


def test_sitemap_index_recursion_and_filter(tmp_path):
    def handler(request):
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        if path == "/sitemap_index.xml":
            return httpx.Response(200, text=f"""<?xml version="1.0"?>
<sitemapindex {SITEMAP_NS}>
  <sitemap><loc>https://example.com/sub.xml</loc></sitemap>
</sitemapindex>""")
        return httpx.Response(200, text=f"""<?xml version="1.0"?>
<urlset {SITEMAP_NS}>
  <url><loc>https://example.com/en/post-1</loc></url>
  <url><loc>https://example.com/fr/post-2</loc></url>
</urlset>""")

    fetcher = make_fetcher(tmp_path, handler)
    urls = urls_from_sitemap(fetcher, "https://example.com/sitemap_index.xml", "/en/")
    fetcher.close()
    assert urls == ["https://example.com/en/post-1"]


def test_sitemap_cycle_terminates(tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        # sitemap index that references itself
        return httpx.Response(200, text=f"""<?xml version="1.0"?>
<sitemapindex {SITEMAP_NS}>
  <sitemap><loc>https://example.com/loop.xml</loc></sitemap>
</sitemapindex>""")

    fetcher = make_fetcher(tmp_path, handler)
    assert urls_from_sitemap(fetcher, "https://example.com/loop.xml") == []
    fetcher.close()


def test_bad_xml_returns_empty(tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(200, text="not xml at all")

    fetcher = make_fetcher(tmp_path, handler)
    assert urls_from_sitemap(fetcher, "https://example.com/sitemap.xml") == []
    fetcher.close()


def test_rate_limit_sleeps_between_requests(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr("insight_mcp.ingest.time.sleep", lambda s: sleeps.append(s))

    def handler(request):
        return httpx.Response(200, text="User-agent: *\nAllow: /")

    fetcher = make_fetcher(tmp_path, handler)
    fetcher.fetch("https://example.com/a")
    fetcher.fetch("https://example.com/b")
    fetcher.close()
    # robots + 2 pages = 3 network hits -> at least 2 throttle sleeps
    assert len(sleeps) >= 2
