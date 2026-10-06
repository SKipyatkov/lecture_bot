FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_DIR=/app/data

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        espeak-ng \
        ca-certificates \
        curl \
        unzip \
    && ln -sf /usr/bin/espeak-ng /usr/local/bin/espeak \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY bot/requirements.txt /app/bot/requirements.txt
RUN pip install --no-cache-dir -r /app/bot/requirements.txt

COPY bot /app/bot
COPY models/faster-whisper-small /app/models/faster-whisper-small

RUN useradd --create-home --uid 1000 bot \
    && mkdir -p /app/data/logs /app/data/cache /app/data/backups /app/data/temp \
    && chown -R bot:bot /app

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh

USER root
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "bot/main.py"]
