#!/bin/bash
set -e

echo "=========================================================="
echo "🎬 Starting ClipDeck 24/7 Cloud Worker & API Engine"
echo "=========================================================="

# 1. Start local Redis if REDIS_URL is local or unset
if [ -z "$REDIS_URL" ] || [[ "$REDIS_URL" == *"localhost"* ]] || [[ "$REDIS_URL" == *"127.0.0.1"* ]] || [[ "$REDIS_URL" == "redis://redis:6379/0" ]]; then
    echo "[+] Initializing internal Redis server on 127.0.0.1:6379..."
    export REDIS_URL="redis://127.0.0.1:6379/0"
    redis-server --daemonize yes --port 6379 --bind 127.0.0.1 --dir /tmp --pidfile /tmp/redis.pid --logfile /tmp/redis.log --protected-mode no
    sleep 1
    if redis-cli -p 6379 ping | grep -q PONG; then
        echo "[✓] Internal Redis is READY and responding to PING."
    else
        echo "[!] Redis ping warning, check /tmp/redis.log"
    fi
else
    echo "[✓] Using external Redis queue at $REDIS_URL"
fi

# 2. Start the Background Ingest & Clipping Worker daemon
echo "[+] Starting ClipDeck Background Worker daemon..."
python -m worker.main &
WORKER_PID=$!
echo "[✓] Worker daemon running with PID: $WORKER_PID"

# Graceful shutdown handler
shutdown_handler() {
    echo "Shutting down ClipDeck..."
    kill -TERM "$WORKER_PID" 2>/dev/null || true
    wait "$WORKER_PID" 2>/dev/null || true
    redis-cli -p 6379 shutdown 2>/dev/null || true
    exit 0
}
trap shutdown_handler SIGTERM SIGINT

# 3. Start the FastAPI server in foreground on $PORT (required by Hugging Face Spaces port 7860)
PORT="${PORT:-7860}"
echo "[+] Starting FastAPI server on 0.0.0.0:$PORT..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
