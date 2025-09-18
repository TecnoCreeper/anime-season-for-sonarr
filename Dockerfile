FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

COPY pyproject.toml .
COPY uv.lock .
COPY anime_season_for_sonarr.py .

ENTRYPOINT ["uv", "run", "--locked", "--no-dev", "anime_season_for_sonarr.py"]