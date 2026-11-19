"""Settings routes — app settings + encrypted provider key management."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Setting, User
from app.schemas import (
    MessageResponse,
    ProviderKeyCreate,
    ProviderKeyResponse,
    ProviderKeyUpdate,
    SettingResponse,
    SettingsUpdateRequest,
)
from app.services.key_service import delete_key, list_keys, store_key, test_key_connection, update_key

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ---------------------------------------------------------------------------
# App settings
# ---------------------------------------------------------------------------


@router.get("", response_model=list[SettingResponse])
async def get_settings(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Setting).order_by(Setting.key))
    return list(result.scalars().all())


@router.put("", response_model=list[SettingResponse])
async def update_settings(
    body: SettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    updated: list[Setting] = []
    for key, value in body.settings.items():
        result = await db.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()
        if setting is None:
            setting = Setting(key=key, value=value)
            db.add(setting)
        else:
            setting.value = value
        await db.flush()
        await db.refresh(setting)
        updated.append(setting)
    return updated


# ---------------------------------------------------------------------------
# Provider keys
# ---------------------------------------------------------------------------


@router.get("/keys", response_model=list[ProviderKeyResponse])
async def get_provider_keys(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await list_keys(db)


@router.post("/keys", response_model=ProviderKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_provider_key(
    body: ProviderKeyCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    key = await store_key(db, body.provider, body.key_name, body.value)
    from app.encryption import decrypt_value, mask_value

    decrypted = decrypt_value(key.encrypted_value)
    return ProviderKeyResponse(
        id=key.id,
        provider=key.provider,
        key_name=key.key_name,
        masked_value=mask_value(decrypted),
        created_at=key.created_at,
        updated_at=key.updated_at,
    )


@router.put("/keys/{key_id}", response_model=ProviderKeyResponse)
async def update_provider_key(
    key_id: int,
    body: ProviderKeyUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    key = await update_key(db, key_id, body.value)
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider key not found")
    from app.encryption import decrypt_value, mask_value

    decrypted = decrypt_value(key.encrypted_value)
    return ProviderKeyResponse(
        id=key.id,
        provider=key.provider,
        key_name=key.key_name,
        masked_value=mask_value(decrypted),
        created_at=key.created_at,
        updated_at=key.updated_at,
    )


@router.delete("/keys/{key_id}", response_model=MessageResponse)
async def delete_provider_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    deleted = await delete_key(db, key_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider key not found")
    return MessageResponse(message="Provider key deleted")


@router.post("/keys/{key_id}/test", response_model=dict)
async def test_provider_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Test connectivity with a stored provider key."""
    result = await test_key_connection(db, key_id)
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error", "Test failed"))
    return result
