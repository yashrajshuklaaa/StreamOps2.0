# Multi-Stage Production Dockerfile for Stream-Ops Speculative Control Plane
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final Runtime Stage
FROM python:3.11-slim AS runner

WORKDIR /app

# Create non-root unprivileged user
RUN groupadd -r streamops && useradd -r -g streamops -u 10001 streamops

COPY --from=builder /root/.local /home/streamops/.local
COPY --chown=streamops:streamops . /app

ENV PATH=/home/streamops/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER streamops

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "streamops.proxy.server:app", "--host", "0.0.0.0", "--port", "8000"]
