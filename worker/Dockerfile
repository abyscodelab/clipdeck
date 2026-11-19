FROM python:3.11-slim

# Install system dependencies including FFmpeg and Streamlink requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY worker/requirements.txt /app/worker/requirements.txt
RUN pip install --no-cache-dir -r /app/worker/requirements.txt

# Copy source code
COPY shared /app/clipdeck/shared
COPY worker /app/clipdeck/worker
COPY api /app/api

ENV PYTHONPATH="/app:/app/clipdeck:/app/api"
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "worker.main"]
