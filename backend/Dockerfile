FROM python:3.11-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY config ./config
COPY data ./data
EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.app.main:app --host ${BACKEND_HOST:-0.0.0.0} --port ${BACKEND_PORT:-8000}"]
