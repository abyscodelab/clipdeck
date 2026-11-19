"""Health check endpoint — database, disk, worker status."""

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas import HealthResponse
from app.services.sse_service import broadcaster

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db),
):
    """Return system health: database connectivity, disk usage, SSE subscribers.

    Unauthenticated to support Docker container HEALTHCHECK and external monitors.
    """
    # Database check
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    # Disk usage
    media_path = Path(settings.MEDIA_STORAGE_PATH)
    disk_info: dict | None = None
    try:
        usage = shutil.disk_usage(media_path if media_path.exists() else "/")
        disk_info = {
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent_used": round(usage.used / usage.total * 100, 1),
            "sse_subscribers": broadcaster.subscriber_count,
        }
    except Exception:
        pass

    return HealthResponse(
        status="healthy" if db_status == "ok" else "degraded",
        database=db_status,
        disk_usage=disk_info,
    )
