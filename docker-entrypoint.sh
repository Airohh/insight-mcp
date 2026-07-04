#!/bin/sh
set -e

# Build the index at boot when no volume provides it (e.g. cloud free tier
# without persistent storage). Downloads from the configured public URLs.
if [ "$INGEST_ON_BOOT" = "1" ] && [ ! -f "$DATA_DIR/corpus.db" ]; then
    echo "corpus.db missing, ingesting seed URLs..." >&2
    python scripts/ingest.py
fi

exec python -m insight_mcp.server --http
