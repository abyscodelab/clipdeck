"""Key service — encrypt, decrypt, store, test provider API keys."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.encryption import decrypt_value, encrypt_value, mask_value
from app.models import ProviderKey
from app.schemas import ProviderKeyResponse


async def store_key(db: AsyncSession, provider: str, key_name: str, plaintext_value: str) -> ProviderKey:
    """Encrypt and persist a provider key."""
    encrypted = encrypt_value(plaintext_value)
    key = ProviderKey(provider=provider, key_name=key_name, encrypted_value=encrypted)
    db.add(key)
    await db.flush()
    await db.refresh(key)
    return key


async def get_key_decrypted(db: AsyncSession, key_id: int) -> str | None:
    """Return the decrypted value for internal use (never expose via API)."""
    result = await db.execute(select(ProviderKey).where(ProviderKey.id == key_id))
    key = result.scalar_one_or_none()
    if key is None:
        return None
    return decrypt_value(key.encrypted_value)


async def list_keys(db: AsyncSession) -> list[ProviderKeyResponse]:
    """Return all provider keys with masked values."""
    result = await db.execute(select(ProviderKey).order_by(ProviderKey.provider))
    keys = result.scalars().all()
    out: list[ProviderKeyResponse] = []
    for k in keys:
        try:
            decrypted = decrypt_value(k.encrypted_value)
            masked = mask_value(decrypted)
        except Exception:
            masked = "****"
        out.append(
            ProviderKeyResponse(
                id=k.id,
                provider=k.provider,
                key_name=k.key_name,
                masked_value=masked,
                created_at=k.created_at,
                updated_at=k.updated_at,
            )
        )
    return out


async def update_key(db: AsyncSession, key_id: int, plaintext_value: str) -> ProviderKey | None:
    """Re-encrypt and update an existing key."""
    result = await db.execute(select(ProviderKey).where(ProviderKey.id == key_id))
    key = result.scalar_one_or_none()
    if key is None:
        return None
    key.encrypted_value = encrypt_value(plaintext_value)
    await db.flush()
    await db.refresh(key)
    return key


async def delete_key(db: AsyncSession, key_id: int) -> bool:
    """Delete a provider key. Returns True if deleted."""
    result = await db.execute(select(ProviderKey).where(ProviderKey.id == key_id))
    key = result.scalar_one_or_none()
    if key is None:
        return False
    await db.delete(key)
    await db.flush()
    return True


async def test_key_connection(db: AsyncSession, key_id: int) -> dict:
    """Placeholder: test connectivity with a provider key. Returns a status dict."""
    decrypted = await get_key_decrypted(db, key_id)
    if decrypted is None:
        return {"success": False, "error": "Key not found"}
    # In a real implementation, this would make an API call to the provider
    return {"success": True, "message": "Connection test placeholder — key is valid and decryptable"}
