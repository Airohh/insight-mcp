"""Ingestion pipeline: public URLs → extracted text → chunks → SQLite.

Polite by design: robots.txt is honored, requests carry an identifiable
User-Agent, fetches are rate-limited (~1 req/s) and cached on disk so a
re-run never re-downloads. The CLI entry point is `scripts/ingest.py`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlparse

import httpx
import trafilatura

from insight_mcp.corpus import Corpus

log = logging.getLogger(__name__)

USER_AGENT = "insight-mcp/0.1 (+https://github.com/Airohh/insight-mcp)"
REQUEST_DELAY_S = 1.0
CHUNK_WORDS = 400
CHUNK_OVERLAP_WORDS = 50


def chunk_text(
    text: str, size: int = CHUNK_WORDS, overlap: int = CHUNK_OVERLAP_WORDS
) -> list[str]:
    """Split text into overlapping word windows (~size words each)."""
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    words = text.split()
    if not words:
        return []
    step = size - overlap
    chunks = []
    for start in range(0, len(words), step):
        window = words[start : start + size]
        chunks.append(" ".join(window))
        if start + size >= len(words):
            break
    return chunks


def extract_article(html: str, url: str) -> dict | None:
    """Extract main text + metadata from an HTML page.

    Returns {"title", "date", "text"} or None when no article content is found.
    """
    raw = trafilatura.extract(
        html, url=url, output_format="json", with_metadata=True
    )
    if not raw:
        return None
    data = json.loads(raw)
    text = (data.get("text") or "").strip()
    if not text:
        return None
    return {
        "title": data.get("title") or url,
        "date": data.get("date"),
        "text": text,
    }


class Fetcher:
    """HTTP fetching with disk cache, robots.txt checks, and rate limiting."""

    def __init__(self, cache_dir: Path):
        self._cache_dir = cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True
        )
        self._robots: dict[str, robotparser.RobotFileParser] = {}
        self._last_request = 0.0

    def close(self) -> None:
        self._client.close()

    def _cache_path(self, url: str) -> Path:
        return self._cache_dir / (hashlib.sha256(url.encode()).hexdigest() + ".html")

    def _allowed(self, url: str) -> bool:
        host = urlparse(url).scheme + "://" + urlparse(url).netloc
        if host not in self._robots:
            rp = robotparser.RobotFileParser(host + "/robots.txt")
            try:
                rp.read()
            except OSError:
                # Unreachable robots.txt: default to allowed (standard practice)
                rp.allow_all = True
            self._robots[host] = rp
        return self._robots[host].can_fetch(USER_AGENT, url)

    def _throttled_get(self, url: str) -> httpx.Response:
        elapsed = time.monotonic() - self._last_request
        if elapsed < REQUEST_DELAY_S:
            time.sleep(REQUEST_DELAY_S - elapsed)
        self._last_request = time.monotonic()
        return self._client.get(url)

    def fetch(self, url: str) -> str | None:
        """Return the page body, from cache when available."""
        cached = self._cache_path(url)
        if cached.exists():
            return cached.read_text(encoding="utf-8")
        if not self._allowed(url):
            log.warning("robots.txt disallows fetch", extra={"url": url})
            return None
        try:
            resp = self._throttled_get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("fetch failed", extra={"url": url, "error": str(exc)})
            return None
        cached.write_text(resp.text, encoding="utf-8")
        return resp.text


def urls_from_sitemap(fetcher: Fetcher, sitemap_url: str, url_filter: str = "") -> list[str]:
    """Collect <loc> URLs from a sitemap (recursing into sub-sitemaps)."""
    body = fetcher.fetch(sitemap_url)
    if body is None:
        return []
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        log.warning("sitemap parse failed", extra={"url": sitemap_url})
        return []
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    if root.tag.endswith("sitemapindex"):
        urls: list[str] = []
        for loc in root.findall(".//sm:sitemap/sm:loc", ns):
            urls += urls_from_sitemap(fetcher, (loc.text or "").strip(), url_filter)
        return urls
    locs = [(loc.text or "").strip() for loc in root.findall(".//sm:url/sm:loc", ns)]
    return [u for u in locs if url_filter in u]


def ingest_urls(urls: list[str], corpus: Corpus, cache_dir: Path) -> int:
    """Fetch, extract, chunk and store each URL. Returns the number ingested."""
    fetcher = Fetcher(cache_dir)
    ingested = 0
    try:
        for url in urls:
            html = fetcher.fetch(url)
            if html is None:
                continue
            article = extract_article(html, url)
            if article is None:
                log.warning("no article content", extra={"url": url})
                continue
            chunks = chunk_text(article["text"])
            corpus.upsert_document(
                url=url,
                title=article["title"],
                date=article["date"],
                text=article["text"],
                chunks=chunks,
                fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
            )
            ingested += 1
            log.info(
                "ingested",
                extra={"url": url, "title": article["title"], "chunks": len(chunks)},
            )
    finally:
        fetcher.close()
    return ingested
