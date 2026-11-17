FROM python:3.13-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app/ app/
COPY data/ data/
RUN python -m app.train

FROM python:3.13-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" MODEL_PATH=/srv/model/model.joblib
RUN useradd --create-home --uid 1001 appuser
WORKDIR /srv
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build/model /srv/model
COPY app/ /srv/app/
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1
# Only Caddy can reach this internal port; it overwrites the forwarded client IP.
# Keep one worker: the demo limiter is intentionally in-memory.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--root-path", "/api", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-access-log"]
