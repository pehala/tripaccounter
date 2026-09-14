# syntax=docker/dockerfile:1
# Builder: resolve/install deps with uv, compile bytecode. Alpine + musl wheels
# (psycopg[binary], uvloop, httptools all ship musllinux wheels) keep both
# stages on the same tiny base.
FROM python:3.13-alpine AS builder
COPY --from=ghcr.io/astral-sh/uv:0.9.13 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-editable

COPY app ./app
COPY alembic ./alembic
COPY static ./static
RUN uv sync --frozen --no-dev --no-editable

# Final: no C toolchain, no cache — venv, app and uv (make migrate/start_server
# shell out to `uv run`, which just execs into the already-synced venv, no
# network access).
FROM python:3.13-alpine AS final
RUN apk add --no-cache make

COPY --from=ghcr.io/astral-sh/uv:0.9.13 /uv /bin/uv
RUN addgroup -g 1000 app && adduser -D -u 1000 -G app app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
COPY --chown=app:app Makefile ./

# The build id versions every static asset URL, so the proxy in front can cache them
# permanently without ever serving a stale one (design/STATIC_CACHING.md). Unset, the
# assets are served unversioned and uncacheable.
ARG BUILD_ID=""

ENV PATH="/app/.venv/bin:$PATH" \
    UV_NO_SYNC=1 \
    TA_BUILD_ID=${BUILD_ID}

USER app
EXPOSE 8000

ENTRYPOINT ["make"]
CMD ["migrate", "start_server"]
