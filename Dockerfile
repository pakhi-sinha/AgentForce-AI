FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV OLLAMA_HOST=127.0.0.1:11434
ENV OLLAMA_BASE_URL=http://127.0.0.1:11434
ENV AGENTFORGE_START_OLLAMA=auto

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates zstd \
    && curl -fsSL https://ollama.com/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY frontend ./frontend
COPY models ./models
COPY docker/start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-8080}/health" || exit 1

CMD ["/start.sh"]
