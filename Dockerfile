# Build native InsightFace dependencies separately so compilers stay out of runtime.
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1
WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN python -m pip wheel --wheel-dir /wheels -r requirements.txt

# Small runtime image; run the application as an unprivileged user.
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp \
    SIC_DATABASE_PATH=/data/classroom.db \
    INSIGHTFACE_HOME=/models \
    AUTH_COOKIE_SECURE=0

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 sic \
    && useradd --system --uid 10001 --gid sic --home-dir /nonexistent --shell /usr/sbin/nologin sic \
    && mkdir -p /data /models \
    && chown 10001:10001 /data /models

COPY --from=builder /wheels /wheels
COPY backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-index --find-links=/wheels -r /tmp/requirements.txt \
    && rm -rf /wheels /tmp/requirements.txt

WORKDIR /app/backend
COPY backend/ ./
COPY frontend/ /app/frontend/

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
