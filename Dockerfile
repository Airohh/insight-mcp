# The image ships CODE ONLY — never the corpus (indexed third-party content
# must not be redistributed). Provide data at runtime: mount a volume on
# /app/data, or set INGEST_ON_BOOT=1 to build the index from seed URLs at start.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY scripts ./scripts
COPY docker-entrypoint.sh ./
RUN useradd --create-home appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app/data \
    && chmod +x docker-entrypoint.sh
USER appuser

# Paths must be explicit here: the package is pip-installed (not a checkout),
# so the repo-root-relative defaults in settings.py do not apply.
ENV DATA_DIR=/app/data \
    CORPUS_SEED_FILE=/app/scripts/seed_urls_wavestone.txt \
    MCP_PORT=8020
EXPOSE 8020

ENTRYPOINT ["./docker-entrypoint.sh"]
