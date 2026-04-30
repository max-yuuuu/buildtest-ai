from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import bcrypt
import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.verification_code import VerificationCode
from app.schemas.auth import (
    CheckEmailResponse,
    RegisterResponse,
    SendCodeResponse,
    VerifyPasswordResponse,
)
from app.services.auth_service import AuthService

pytestmark = pytest.mark.asyncio


async def test_send_code_success(session: AsyncSession):
    """send_code returns success when no prior code exists."""
    svc = AuthService(session)
    with patch(
        "app.services.auth_service.send_verification_email",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await svc.send_code("alice@example.com", "register")
    assert isinstance(result, SendCodeResponse)
    assert result.success is True
    assert result.expires_in == 300


async def test_send_code_rate_limited(session: AsyncSession):
    """send_code raises 429 when a code was sent within the last 60 seconds."""
    svc = AuthService(session)
    # Insert a recent verification code
    vc = VerificationCode(
        email="bob@example.com",
        code_hash="dummy",
        purpose="register",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    session.add(vc)
    await session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await svc.send_code("bob@example.com", "register")
    assert exc_info.value.status_code == 429
    assert "60" in exc_info.value.detail


async def test_send_code_rejects_registered_email(session: AsyncSession):
    """send_code raises 409 when the email is already registered."""
    svc = AuthService(session)
    # Insert an existing user
    user = User(
        external_id="credentials:test@example.com",
        email="test@example.com",
        name="Existing User",
    )
    session.add(user)
    await session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await svc.send_code("test@example.com", "register")
    assert exc_info.value.status_code == 409
    assert "已注册" in exc_info.value.detail


async def test_register_success(session: AsyncSession):
    """register creates a user when given a valid code."""
    svc = AuthService(session)
    code = "123456"
    code_hash = bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    vc = VerificationCode(
        email="newuser@example.com",
        code_hash=code_hash,
        purpose="register",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    session.add(vc)
    await session.commit()

    result = await svc.register("newuser@example.com", "123456", "passw0rd99", name="New User")
    assert isinstance(result, RegisterResponse)
    assert result.success is True

    # Verify user was created
    from sqlalchemy import select

    db_user = (
        (await session.execute(select(User).where(User.email == "newuser@example.com")))
        .scalar_one_or_none()
    )
    assert db_user is not None
    assert db_user.external_id == "credentials:newuser@example.com"
    assert db_user.email == "newuser@example.com"
    assert db_user.name == "New User"
    assert db_user.password_hash is not None
    # Verify password was hashed correctly
    assert bcrypt.checkpw(b"passw0rd99", db_user.password_hash.encode("utf-8"))


async def test_register_invalid_code(session: AsyncSession):
    """register raises 400 when the code is wrong."""
    svc = AuthService(session)
    code_hash = bcrypt.hashpw(b"123456", bcrypt.gensalt()).decode("utf-8")
    vc = VerificationCode(
        email="bad@example.com",
        code_hash=code_hash,
        purpose="register",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    session.add(vc)
    await session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await svc.register("bad@example.com", "999999", "passw0rd99")
    assert exc_info.value.status_code == 400
    assert "验证码" in exc_info.value.detail


async def test_check_email_registered(session: AsyncSession):
    """check_email returns registered=True for existing user."""
    svc = AuthService(session)
    user = User(
        external_id="credentials:registered@example.com",
        email="registered@example.com",
    )
    session.add(user)
    await session.commit()

    result = await svc.check_email("registered@example.com")
    assert isinstance(result, CheckEmailResponse)
    assert result.registered is True


async def test_check_email_not_registered(session: AsyncSession):
    """check_email returns registered=False when no user exists."""
    svc = AuthService(session)
    result = await svc.check_email("ghost@example.com")
    assert isinstance(result, CheckEmailResponse)
    assert result.registered is False


async def test_verify_password_success(session: AsyncSession):
    """verify_password returns user info for valid credentials."""
    svc = AuthService(session)
    password_hash = bcrypt.hashpw(b"correcthorse", bcrypt.gensalt()).decode("utf-8")
    user = User(
        external_id="credentials:auth@example.com",
        email="auth@example.com",
        name="Auth User",
        password_hash=password_hash,
    )
    session.add(user)
    await session.commit()

    result = await svc.verify_password("auth@example.com", "correcthorse")
    assert isinstance(result, VerifyPasswordResponse)
    assert result.id == "credentials:auth@example.com"
    assert result.email == "auth@example.com"
    assert result.name == "Auth User"


async def test_verify_password_wrong_password(session: AsyncSession):
    """verify_password returns None for wrong password."""
    svc = AuthService(session)
    password_hash = bcrypt.hashpw(b"correcthorse", bcrypt.gensalt()).decode("utf-8")
    user = User(
        external_id="credentials:auth2@example.com",
        email="auth2@example.com",
        name="Auth User 2",
        password_hash=password_hash,
    )
    session.add(user)
    await session.commit()

    result = await svc.verify_password("auth2@example.com", "wrongpassword")
    assert result is None


async def test_verify_password_nonexistent_user(session: AsyncSession):
    """verify_password returns None when user does not exist."""
    svc = AuthService(session)
    result = await svc.verify_password("nobody@example.com", "anypassword")
    assert result is None
