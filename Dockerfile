# syntax=docker/dockerfile:1
FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY 前端/package*.json ./前端/
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm ci --prefix 前端
COPY 前端 ./前端
RUN npm run build --prefix 前端

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md requirements-dev.lock MANIFEST.in ./
COPY src ./src
COPY .github/scripts ./.github/scripts
COPY --from=frontend /build/src/langrensha/static ./src/langrensha/static
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -c requirements-dev.lock '.[ai,web,rag]' \
    && useradd --uid 10001 --create-home town \
    && mkdir -p /home/town/.cache/langrensha /data \
    && chown -R town:town /home/town/.cache /data
USER town
ENV LANGRENSHA_DATABASE=/data/对局.sqlite3
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)" || exit 1
CMD ["langrensha-web", "--host", "0.0.0.0", "--port", "8000"]
