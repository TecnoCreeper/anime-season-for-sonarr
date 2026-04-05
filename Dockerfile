# python:3.13.12-alpine3.23
FROM python@sha256:bb1f2fdb1065c85468775c9d680dcd344f6442a2d1181ef7916b60a623f11d40 AS builder

# uv:0.11.3-alpine3.23
COPY --from=ghcr.io/astral-sh/uv@sha256:594980da480fac1536122ca142b159adf1d5ad490d2f63a9eea122b0c734b516 /usr/local/bin/uv /usr/local/bin/uvx /bin/
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --locked --no-editable --no-install-project

COPY anime_season_for_sonarr.py ./
RUN uv sync --no-dev --locked --no-editable

# python:3.13.12-alpine3.23
FROM python@sha256:bb1f2fdb1065c85468775c9d680dcd344f6442a2d1181ef7916b60a623f11d40 AS runtime

WORKDIR /app

COPY --from=builder --chown=root:root /app/.venv /app/.venv
COPY --from=builder --chown=root:root /app/anime_season_for_sonarr.py /app/anime_season_for_sonarr.py

RUN chmod -R o=rx /app && adduser -D -H user
USER user

ENV PYTHONPATH=/app/.venv/lib/python3.13/site-packages
ENTRYPOINT ["python", "anime_season_for_sonarr.py"]