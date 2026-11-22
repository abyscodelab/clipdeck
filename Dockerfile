FROM python:3.11-slim

# Install system dependencies: FFmpeg, Redis Server, GCC, curl, git
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    redis-server \
    gcc \
    g++ \
    make \
    curl \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create user with UID 1000 (standard for Hugging Face Spaces & security)
RUN useradd -m -u 1000 user || true
ENV HOME=/home/user

# Install Python requirements
COPY requirements-cloud.txt /app/requirements-cloud.txt
RUN pip install --no-cache-dir -r /app/requirements-cloud.txt

# Copy application source code
COPY shared /app/clipdeck/shared
COPY worker /app/clipdeck/worker
COPY api /app/api
COPY subtle /app/clipdeck/subtle
COPY start.sh /app/start.sh

# Environment settings
ENV PYTHONPATH="/app:/app/clipdeck:/app/api"
ENV PYTHONUNBUFFERED=1
ENV PORT=7860
ENV MEDIA_STORAGE_PATH="/app/media"

# Create storage and temp directories with permissive read/write access
RUN mkdir -p /app/data /app/media /data/media /tmp && \
    chmod -R 777 /app/data /app/media /data/media /tmp && \
    chmod +x /app/start.sh

# Switch to non-root user (Hugging Face compatible)
USER 1000

EXPOSE 7860

CMD ["/app/start.sh"]
