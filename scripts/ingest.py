"""CLI for the ingestion pipeline.

Usage:
    python scripts/ingest.py                          # seed file from settings
    python scripts/ingest.py --seed-file urls.txt
    python scripts/ingest.py --sitemap https://example.com/sitemap.xml --filter /insight/
    python scripts/ingest.py --max-docs 30
"""

from __future__ import annotations

import argparse
import sys

from insight_mcp.corpus import Corpus
from insight_mcp.ingest import Fetcher, ingest_urls, urls_from_sitemap
from insight_mcp.logging_conf import setup_logging
from insight_mcp.settings import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest public URLs into the corpus")
    parser.add_argument("--seed-file", help="text file with one URL per line")
    parser.add_argument("--sitemap", help="sitemap URL to crawl instead of a seed file")
    parser.add_argument("--filter", default="", help="substring filter for sitemap URLs")
    parser.add_argument("--max-docs", type=int, default=50)
    args = parser.parse_args()

    setup_logging()
    settings = get_settings()

    if args.sitemap:
        fetcher = Fetcher(settings.cache_dir)
        try:
            urls = urls_from_sitemap(fetcher, args.sitemap, args.filter)
        finally:
            fetcher.close()
    else:
        seed_path = args.seed_file or settings.corpus_seed_file
        with open(seed_path, encoding="utf-8") as f:
            urls = [
                line.strip()
                for line in f
                if line.strip() and not line.startswith("#")
            ]

    urls = urls[: args.max_docs]
    if not urls:
        print("No URLs to ingest.", file=sys.stderr)
        return 1

    corpus = Corpus(settings.db_path)
    try:
        count = ingest_urls(urls, corpus, settings.cache_dir)
        stats = corpus.stats()
    finally:
        corpus.close()
    print(
        f"Ingested {count}/{len(urls)} URLs — corpus now has"
        f" {stats['documents']} documents / {stats['chunks']} chunks.",
        file=sys.stderr,
    )
    return 0 if count else 1


if __name__ == "__main__":
    raise SystemExit(main())
