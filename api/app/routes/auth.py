"""Auth routes — login, TOTP setup/verify, token refresh, password change."""

import base64
import io

import pyotp
import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.encryption import decrypt_value, encrypt_value
from app.models import User
from app.schemas import (
    LoginRequest,
    LoginResponse,
    MessageResponse,
    PasswordChangeRequest,
    RefreshRequest,
    TOTPSetupResponse,
    TOTPVerifyRequest,
    UserResponse,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate with username/password (and optional TOTP)."""
    from sqlalchemy import select

    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # TOTP check
    if user.totp_enabled:
        if not body.totp_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="TOTP code required",
            )
        secret = decrypt_value(user.totp_secret) if user.totp_secret else ""
        totp = pyotp.TOTP(secret)
        if not totp.verify(body.totp_code, valid_window=1):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid TOTP code")

    return LoginResponse(
        access_token=create_access_token(user.id, user.username),
        refresh_token=create_refresh_token(user.id, user.username),
        must_change_password=user.must_change_password,
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(body: RefreshRequest):
    """Exchange a refresh token for a new access + refresh pair."""
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    user_id = int(payload["sub"])
    username = payload["username"]
    return LoginResponse(
        access_token=create_access_token(user_id, username),
        refresh_token=create_refresh_token(user_id, username),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Return the current authenticated user."""
    return user


@router.put("/password", response_model=MessageResponse)
async def change_password(
    body: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the current user's password."""
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    await db.commit()
    return MessageResponse(message="Password changed successfully")


@router.post("/totp/setup", response_model=TOTPSetupResponse)
async def totp_setup(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Generate a new TOTP secret and QR code for the user."""
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=user.username, issuer_name="ClipDeck")

    # Generate QR code as base64
    img = qrcode.make(provisioning_uri)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    # Encrypt and store the secret (not yet enabled until verified)
    user.totp_secret = encrypt_value(secret)
    await db.flush()

    return TOTPSetupResponse(secret=secret, provisioning_uri=provisioning_uri, qr_code_base64=qr_b64)


@router.post("/totp/verify", response_model=MessageResponse)
async def totp_verify(
    body: TOTPVerifyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify a TOTP code and enable 2FA for the user."""
    if not user.totp_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run TOTP setup first")

    secret = decrypt_value(user.totp_secret)
    totp = pyotp.TOTP(secret)
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TOTP code")

    user.totp_enabled = True
    await db.flush()
    return MessageResponse(message="TOTP enabled successfully")
