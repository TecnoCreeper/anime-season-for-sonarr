FROM python:3.13-alpine

WORKDIR /app

COPY anime_season_for_sonarr.py ./
COPY config.ini ./
COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "anime_season_for_sonarr.py"]