# The image the organisers build and run for the final (and for the dry run of every upload).
# Change it freely: any language works as long as the container follows the contract below.
#
# Contract: configuration comes only from the environment. ARENA_BASE_URL and OPENROUTER_BASE_URL point at the
# organisers' gateway, ARENA_API_KEY and OPENROUTER_API_KEY are tokens that only work there, ARENA_RUN_KIND is
# dev (dry run) or final. Run to completion; the container is stopped after 30 minutes.
#
# Dependencies (whatever exists): uv.lock (or pyproject.toml), requirements.txt, pnpm-lock.yaml, package-lock.json.
# Entry point: `python main.py` if main.py exists, else `npm start`.
#
# Test it locally:
#   docker build -t my-harness .
#   docker run --rm --env-file .env -e ARENA_RUN_KIND=dev my-harness --tasks t01

# TODO(pin): pin both base images by digest before the event.
FROM node:24-bookworm-slim AS node

FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.9.11 /uv /usr/local/bin/uv
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN set -eu; \
    ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm; \
    ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx; \
    ln -s ../lib/node_modules/corepack/dist/corepack.js /usr/local/bin/corepack; \
    corepack enable pnpm; \
    useradd --create-home --uid 10001 harness; \
    mkdir /app; chown harness:harness /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_NO_CACHE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false \
    NPM_CONFIG_AUDIT=false \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    PATH="/app/.venv/bin:/app/node_modules/.bin:${PATH}"

# Everything below runs as the non-root user; /app stays writable (runs/, .cache/).
USER harness
WORKDIR /app
COPY --chown=harness:harness . .

RUN set -eu; \
    if [ ! -f main.py ] && [ ! -f package.json ]; then \
        echo "ERROR: need main.py or a package.json with a start script at the project root" >&2; exit 1; \
    fi; \
    if [ -f uv.lock ]; then uv sync --frozen --no-dev --no-install-project; \
    elif [ -f requirements.txt ]; then uv venv -q /app/.venv && uv pip install -q --python /app/.venv/bin/python -r requirements.txt; \
    elif [ -f pyproject.toml ]; then uv sync --no-dev --no-install-project; \
    fi; \
    if [ -f pnpm-lock.yaml ]; then pnpm install --frozen-lockfile; \
    elif [ -f package-lock.json ]; then npm ci; \
    elif [ -f package.json ]; then npm install; \
    fi; \
    rm -rf /home/harness/.npm /home/harness/.cache

ENTRYPOINT ["/bin/sh", "-c", "if [ -f main.py ]; then exec python main.py \"$@\"; else exec npm start --silent -- \"$@\"; fi", "harness"]
CMD []
