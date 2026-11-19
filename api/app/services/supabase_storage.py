"""Supabase Storage Service for uploading and serving clips & thumbnails."""

import logging
import mimetypes
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

_supabase_client = None


def get_supabase_client():
    """Lazily initialize Supabase client if configured."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    if not settings.SUPABASE_URL or not (settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY):
        return None

    try:
        from supabase import create_client, Client
        key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
        _supabase_client = create_client(settings.SUPABASE_URL, key)
        return _supabase_client
    except Exception as e:
        logger.warning(f"Could not initialize Supabase client: {e}")
        return None


class SupabaseStorageService:
    """Service to handle uploads to Supabase Storage buckets."""

    def __init__(self):
        self.url = settings.SUPABASE_URL
        self.clips_bucket = settings.SUPABASE_STORAGE_BUCKET_CLIPS
        self.thumbnails_bucket = settings.SUPABASE_STORAGE_BUCKET_THUMBNAILS

    def is_configured(self) -> bool:
        """Check if Supabase credentials are provided."""
        return bool(self.url and (settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY))

    def get_public_url(self, bucket: str, filename: str) -> str:
        """Generate public CDN URL for a file in Supabase Storage."""
        clean_url = self.url.rstrip("/")
        clean_file = filename.lstrip("/")
        return f"{clean_url}/storage/v1/object/public/{bucket}/{clean_file}"

    async def upload_file(
        self,
        local_path: str,
        bucket: str,
        destination_name: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> Optional[str]:
        """Upload a local file to Supabase Storage and return its public URL."""
        client = get_supabase_client()
        if not client:
            logger.debug("Supabase not configured, skipping remote upload")
            return None

        path_obj = Path(local_path)
        if not path_obj.exists():
            logger.error(f"Local file does not exist: {local_path}")
            return None

        dest = destination_name or path_obj.name
        if not content_type:
            content_type, _ = mimetypes.guess_type(local_path)
            content_type = content_type or "application/octet-stream"

        try:
            with open(local_path, "rb") as f:
                file_bytes = f.read()

            # Upload with upsert=True
            client.storage.from_(bucket).upload(
                path=dest,
                file=file_bytes,
                file_options={"content-type": content_type, "upsert": "true"},
            )
            public_url = self.get_public_url(bucket, dest)
            logger.info(f"Uploaded {dest} to Supabase Storage [{bucket}]: {public_url}")
            return public_url
        except Exception as e:
            logger.error(f"Failed to upload {dest} to Supabase storage bucket {bucket}: {e}")
            return None

    async def upload_thumbnail(self, local_path: str, custom_name: Optional[str] = None) -> Optional[str]:
        """Upload thumbnail image to Supabase thumbnails bucket."""
        return await self.upload_file(
            local_path=local_path,
            bucket=self.thumbnails_bucket,
            destination_name=custom_name,
            content_type="image/jpeg",
        )

    async def upload_clip(self, local_path: str, custom_name: Optional[str] = None) -> Optional[str]:
        """Upload vertical MP4 clip to Supabase clips bucket."""
        return await self.upload_file(
            local_path=local_path,
            bucket=self.clips_bucket,
            destination_name=custom_name,
            content_type="video/mp4",
        )


supabase_storage = SupabaseStorageService()
