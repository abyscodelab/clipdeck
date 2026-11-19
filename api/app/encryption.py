"""Fernet encryption utilities for securing provider API keys at rest."""

import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Return a lazily-initialized Fernet instance."""
    global _fernet
    if _fernet is None:
        key = settings.CLIPDECK_MASTER_KEY
        if not key:
            raise RuntimeError(
                "CLIPDECK_MASTER_KEY environment variable is not set. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_value(plaintext: str) -> bytes:
    """Encrypt a plaintext string and return cipher bytes."""
    return _get_fernet().encrypt(plaintext.encode("utf-8"))


def decrypt_value(encrypted: bytes) -> str:
    """Decrypt cipher bytes and return the original plaintext string."""
    try:
        return _get_fernet().decrypt(encrypted).decode("utf-8")
    except InvalidToken:
        logger.error("Failed to decrypt value — invalid token or wrong master key")
        raise ValueError("Decryption failed. The master key may have changed.")


def mask_value(value: str, visible: int = 4) -> str:
    """Return a masked version of a value, showing only the last `visible` characters."""
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]
