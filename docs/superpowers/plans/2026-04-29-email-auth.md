# Email Registration & Login Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add email + password registration and login with verification code, alongside existing GitHub/Google OAuth.

**Architecture:** NextAuth Credentials Provider calls a backend `verify-password` endpoint. Registration flow (send-code → register) goes through BFF proxy (`/api/backend/v1/auth/...`). The `external_id` format `credentials:email` unifies with existing OAuth `provider:accountId` pattern.

**Tech Stack:** NextAuth v5 (Auth.js), FastAPI, SQLAlchemy async, bcrypt, Resend (email), shadcn/ui

---

## File Structure

### New Files

| File | Responsibility |
|---|---|
| `backend/app/models/verification_code.py` | VerificationCode ORM model |
| `backend/app/schemas/auth.py` | Auth request/response Pydantic schemas |
| `backend/app/repositories/verification_code.py` | VerificationCode data access |
| `backend/app/services/auth_service.py` | Auth business logic (send-code, register, verify) |
| `backend/app/services/email_service.py` | Resend email integration |
| `backend/app/api/v1/auth/routes.py` | Auth API endpoints |
| `backend/tests/unit/test_auth_service.py` | Unit tests for auth service |
| `backend/tests/unit/test_email_service.py` | Unit tests for email service |

### Modified Files

| File | Change |
|---|---|
| `backend/app/models/user.py` | Add `password_hash` column |
| `backend/app/api/v1/router.py` | Register auth router |
| `backend/app/core/config.py` | Add `resend_api_key` setting |
| `frontend/lib/auth.ts` | Add Credentials provider, modify JWT callback |
| `frontend/app/login/page.tsx` | Add email form UI |
| `frontend/lib/api.ts` | Add `authApi` with send-code, register, check-email |
| `.env.example` | Add `RESEND_API_KEY` |

---

## Task 1: Database — VerificationCode Model + User password_hash

**Files:**
- Create: `backend/app/models/verification_code.py`
- Modify: `backend/app/models/user.py:17-18` (add password_hash after avatar_url)
- Create: `alembic/versions/0012_email_auth.py`

- [ ] **Step 1: Add password_hash to User model**

Edit `backend/app/models/user.py`, add `password_hash` column after `avatar_url`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 2: Create VerificationCode model**

Create `backend/app/models/verification_code.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 3: Generate and apply Alembic migration**

Run: `cd backend && alembic revision --autogenerate -m "add email auth columns and verification_codes table"`

Then verify the generated migration file has:
1. `op.add_column("users", sa.Column("password_hash", ...))`
2. `op.create_table("verification_codes", ...)`
3. Index on `verification_codes.email`

If autogenerate missed anything, manually edit the migration file.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/user.py backend/app/models/verification_code.py alembic/versions/0012_*.py
git commit -m "feat(db): 添加邮箱认证相关表和字段"
```

---

## Task 2: Backend Config — Resend API Key

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Add resend_api_key to Settings**

Edit `backend/app/core/config.py`, add after `app_encryption_key`:

```python
    resend_api_key: str = ""
```

- [ ] **Step 2: Update .env.example**

Append to `.env.example`:

```bash

# ---------- 邮件服务(Resend) ----------
RESEND_API_KEY=
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/config.py .env.example
git commit -m "feat(config): 添加 Resend API Key 配置项"
```

---

## Task 3: Backend — Email Service

**Files:**
- Create: `backend/app/services/email_service.py`
- Create: `backend/tests/unit/test_email_service.py`

- [ ] **Step 1: Write failing test for email service**

Create `backend/tests/unit/test_email_service.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest

from app.services.email_service import send_verification_email


@pytest.mark.asyncio
@patch("app.services.email_service.resend.Emails.send", new_callable=AsyncMock)
async def test_send_verification_email_calls_resend(mock_send):
    mock_send.return_value = {"id": "msg_123"}
    result = await send_verification_email("test@example.com", "123456")
    assert result is True
    mock_send.assert_called_once()
    call_args = mock_send.call_args[0][0]
    assert call_args["to"] == ["test@example.com"]
    assert "123456" in call_args["html"]


@pytest.mark.asyncio
@patch("app.services.email_service.resend.Emails.send", new_callable=AsyncMock)
async def test_send_verification_email_returns_false_on_error(mock_send):
    mock_send.side_effect = Exception("resend error")
    result = await send_verification_email("test@example.com", "123456")
    assert result is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_email_service.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement email service**

Create `backend/app/services/email_service.py`:

```python
import logging

import resend

from app.core.config import settings

logger = logging.getLogger(__name__)

resend.api_key = settings.resend_api_key

FROM_ADDRESS = "BuildTest AI <noreply@buildtest.ai>"


def _verification_code_html(code: str) -> str:
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
        <h2 style="color: #1a1a1a; margin-bottom: 16px;">BuildTest AI 验证码</h2>
        <p style="color: #4a4a4a; font-size: 15px; line-height: 1.6;">
            您的验证码是：
        </p>
        <div style="background: #f4f4f5; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
            <span style="font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #1a1a1a;">{code}</span>
        </div>
        <p style="color: #71717a; font-size: 13px; line-height: 1.5;">
            验证码 5 分钟内有效。如果这不是您的操作，请忽略此邮件。
        </p>
    </div>
    """


async def send_verification_email(email: str, code: str) -> bool:
    """发送验证码邮件。成功返回 True，失败返回 False。"""
    try:
        resend.Emails.send(
            {
                "from": FROM_ADDRESS,
                "to": [email],
                "subject": "BuildTest AI - 邮箱验证码",
                "html": _verification_code_html(code),
            }
        )
        return True
    except Exception:
        logger.exception("Failed to send verification email to %s", email)
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_email_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/email_service.py backend/tests/unit/test_email_service.py
git commit -m "feat(backend): 添加 Resend 邮件发送服务"
```

---

## Task 4: Backend — Auth Schemas

**Files:**
- Create: `backend/app/schemas/auth.py`

- [ ] **Step 1: Create auth schemas**

Create `backend/app/schemas/auth.py`:

```python
from pydantic import BaseModel, EmailStr, field_validator
import re


class SendCodeRequest(BaseModel):
    email: EmailStr
    purpose: str = "register"

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, v: str) -> str:
        if v not in ("register",):
            raise ValueError("invalid purpose")
        return v


class SendCodeResponse(BaseModel):
    success: bool
    expires_in: int = 300


class RegisterRequest(BaseModel):
    email: EmailStr
    code: str
    password: str
    name: str | None = None

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not re.fullmatch(r"\d{6}", v):
            raise ValueError("验证码必须为 6 位数字")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("密码长度不能少于 8 位")
        if not re.search(r"[a-zA-Z]", v) or not re.search(r"\d", v):
            raise ValueError("密码必须包含字母和数字")
        return v


class RegisterResponse(BaseModel):
    success: bool


class CheckEmailRequest(BaseModel):
    email: EmailStr


class CheckEmailResponse(BaseModel):
    registered: bool


class VerifyPasswordRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyPasswordResponse(BaseModel):
    id: str
    email: str
    name: str | None = None
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/auth.py
git commit -m "feat(backend): 添加认证相关 Pydantic schemas"
```

---

## Task 5: Backend — Verification Code Repository

**Files:**
- Create: `backend/app/repositories/verification_code.py`
- Create: `backend/tests/unit/test_verification_code_repo.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_verification_code_repo.py`:

```python
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.verification_code import VerificationCode
from app.repositories.verification_code import VerificationCodeRepository


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_and_get_latest(session: AsyncSession):
    repo = VerificationCodeRepository(session)
    code = VerificationCode(
        email="test@example.com",
        code_hash="$2b$12$hashed",
        purpose="register",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    await repo.create(code)
    await session.commit()

    latest = await repo.get_latest("test@example.com", "register")
    assert latest is not None
    assert latest.email == "test@example.com"
    assert latest.used is False


@pytest.mark.asyncio
async def test_get_latest_returns_none_when_all_used(session: AsyncSession):
    repo = VerificationCodeRepository(session)
    code = VerificationCode(
        email="test@example.com",
        code_hash="$2b$12$hashed",
        purpose="register",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        used=True,
    )
    await repo.create(code)
    await session.commit()

    latest = await repo.get_latest("test@example.com", "register")
    assert latest is None


@pytest.mark.asyncio
async def test_rate_limit_check(session: AsyncSession):
    repo = VerificationCodeRepository(session)
    code = VerificationCode(
        email="test@example.com",
        code_hash="$2b$12$hashed",
        purpose="register",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    await repo.create(code)
    await session.commit()

    recent = await repo.has_recent("test@example.com", "register", seconds=60)
    assert recent is True

    old = await repo.has_recent("test@example.com", "register", seconds=0)
    assert old is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_verification_code_repo.py -v`
Expected: FAIL

- [ ] **Step 3: Implement repository**

Create `backend/app/repositories/verification_code.py`:

```python
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.verification_code import VerificationCode


class VerificationCodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, code: VerificationCode) -> None:
        self.session.add(code)
        await self.session.flush()

    async def get_latest(
        self, email: str, purpose: str
    ) -> VerificationCode | None:
        """获取最新的未使用、未过期验证码。"""
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(VerificationCode)
            .where(
                VerificationCode.email == email,
                VerificationCode.purpose == purpose,
                VerificationCode.used.is_(False),
                VerificationCode.expires_at > now,
            )
            .order_by(VerificationCode.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def has_recent(
        self, email: str, purpose: str, seconds: int = 60
    ) -> bool:
        """检查指定秒数内是否已有发送记录。"""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=seconds)
        result = await self.session.execute(
            select(VerificationCode.id)
            .where(
                VerificationCode.email == email,
                VerificationCode.purpose == purpose,
                VerificationCode.created_at > cutoff,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_verification_code_repo.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/verification_code.py backend/tests/unit/test_verification_code_repo.py
git commit -m "feat(backend): 添加验证码仓库层"
```

---

## Task 6: Backend — Auth Service

**Files:**
- Create: `backend/app/services/auth_service.py`
- Create: `backend/tests/unit/test_auth_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_auth_service.py`:

```python
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.user import User
from app.models.verification_code import VerificationCode
from app.repositories.user import UserRepository
from app.repositories.verification_code import VerificationCodeRepository
from app.services.auth_service import AuthService


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.fixture
def auth_service(session: AsyncSession):
    return AuthService(session)


@pytest.mark.asyncio
@patch("app.services.auth_service.send_verification_email", new_callable=AsyncMock)
async def test_send_code_success(mock_send, auth_service: AuthService):
    mock_send.return_value = True
    result = await auth_service.send_code("test@example.com", "register")
    assert result.success is True
    assert result.expires_in == 300
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_code_rate_limited(auth_service: AuthService):
    # Create a recent code
    code = VerificationCode(
        email="test@example.com",
        code_hash="$2b$12$hashed",
        purpose="register",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    auth_service.session.add(code)
    await auth_service.session.commit()

    with pytest.raises(Exception) as exc_info:
        await auth_service.send_code("test@example.com", "register")
    assert "60" in str(exc_info.value)


@pytest.mark.asyncio
async def test_send_code_rejects_registered_email(auth_service: AuthService):
    # Create a user with credentials external_id
    user = User(
        external_id="credentials:test@example.com",
        email="test@example.com",
        name="Test",
    )
    auth_service.session.add(user)
    await auth_service.session.commit()

    with pytest.raises(Exception) as exc_info:
        await auth_service.send_code("test@example.com", "register")
    assert "已注册" in str(exc_info.value)


@pytest.mark.asyncio
async def test_register_success(auth_service: AuthService):
    import bcrypt

    code = "123456"
    code_hash = bcrypt.hashpw(code.encode(), bcrypt.gensalt()).decode()
    vc = VerificationCode(
        email="new@example.com",
        code_hash=code_hash,
        purpose="register",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    auth_service.session.add(vc)
    await auth_service.session.commit()

    with patch("app.services.auth_service.send_verification_email", new_callable=AsyncMock):
        result = await auth_service.register("new@example.com", "123456", "Passw0rd", "New User")
    assert result.success is True

    # Verify user was created
    repo = UserRepository(auth_service.session)
    user = await repo.get_by_external_id("credentials:new@example.com")
    assert user is not None
    assert user.email == "new@example.com"
    assert user.name == "New User"
    assert user.password_hash is not None


@pytest.mark.asyncio
async def test_register_invalid_code(auth_service: AuthService):
    import bcrypt

    code_hash = bcrypt.hashpw("123456".encode(), bcrypt.gensalt()).decode()
    vc = VerificationCode(
        email="new@example.com",
        code_hash=code_hash,
        purpose="register",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    auth_service.session.add(vc)
    await auth_service.session.commit()

    with pytest.raises(Exception) as exc_info:
        await auth_service.register("new@example.com", "000000", "Passw0rd")
    assert "验证码" in str(exc_info.value)


@pytest.mark.asyncio
async def test_check_email_registered(auth_service: AuthService):
    user = User(
        external_id="credentials:exists@example.com",
        email="exists@example.com",
    )
    auth_service.session.add(user)
    await auth_service.session.commit()

    result = await auth_service.check_email("exists@example.com")
    assert result.registered is True


@pytest.mark.asyncio
async def test_check_email_not_registered(auth_service: AuthService):
    result = await auth_service.check_email("nobody@example.com")
    assert result.registered is False


@pytest.mark.asyncio
async def test_verify_password_success(auth_service: AuthService):
    import bcrypt

    password_hash = bcrypt.hashpw("Passw0rd".encode(), bcrypt.gensalt()).decode()
    user = User(
        external_id="credentials:login@example.com",
        email="login@example.com",
        name="Login User",
        password_hash=password_hash,
    )
    auth_service.session.add(user)
    await auth_service.session.commit()

    result = await auth_service.verify_password("login@example.com", "Passw0rd")
    assert result is not None
    assert result.id == "credentials:login@example.com"
    assert result.email == "login@example.com"


@pytest.mark.asyncio
async def test_verify_password_wrong_password(auth_service: AuthService):
    import bcrypt

    password_hash = bcrypt.hashpw("Passw0rd".encode(), bcrypt.gensalt()).decode()
    user = User(
        external_id="credentials:login@example.com",
        email="login@example.com",
        password_hash=password_hash,
    )
    auth_service.session.add(user)
    await auth_service.session.commit()

    result = await auth_service.verify_password("login@example.com", "WrongPass1")
    assert result is None


@pytest.mark.asyncio
async def test_verify_password_nonexistent_user(auth_service: AuthService):
    result = await auth_service.verify_password("nobody@example.com", "Passw0rd")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_auth_service.py -v`
Expected: FAIL

- [ ] **Step 3: Implement auth service**

Create `backend/app/services/auth_service.py`:

```python
import random
import string

import bcrypt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.verification_code import VerificationCode
from app.repositories.user import UserRepository
from app.repositories.verification_code import VerificationCodeRepository
from app.schemas.auth import (
    CheckEmailResponse,
    RegisterResponse,
    SendCodeResponse,
    VerifyPasswordResponse,
)
from app.services.email_service import send_verification_email


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.vc_repo = VerificationCodeRepository(session)
        self.user_repo = UserRepository(session)

    async def send_code(self, email: str, purpose: str) -> SendCodeResponse:
        """发送验证码。"""
        # Check if already registered (for register purpose)
        if purpose == "register":
            existing = await self.user_repo.get_by_external_id(f"credentials:{email}")
            if existing is not None:
                raise HTTPException(status_code=409, detail="该邮箱已注册")

        # Rate limit: 60s per email
        if await self.vc_repo.has_recent(email, purpose, seconds=60):
            raise HTTPException(status_code=429, detail="验证码发送过于频繁，请 60 秒后重试")

        # Generate 6-digit code
        code = "".join(random.choices(string.digits, k=6))
        code_hash = bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # Store hashed code
        from datetime import datetime, timedelta, timezone

        vc = VerificationCode(
            email=email,
            code_hash=code_hash,
            purpose=purpose,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        await self.vc_repo.create(vc)
        await self.session.commit()

        # Send email
        sent = await send_verification_email(email, code)
        if not sent:
            raise HTTPException(status_code=502, detail="验证码发送失败，请稍后重试")

        return SendCodeResponse(success=True, expires_in=300)

    async def register(
        self, email: str, code: str, password: str, name: str | None = None
    ) -> RegisterResponse:
        """注册新用户。"""
        # Find latest unused, unexpired code
        vc = await self.vc_repo.get_latest(email, "register")
        if vc is None:
            raise HTTPException(status_code=400, detail="验证码已过期或不存在")

        # Check attempts
        if vc.attempts >= 5:
            raise HTTPException(status_code=400, detail="验证码已失效，请重新获取")

        # Verify code
        if not bcrypt.checkpw(code.encode("utf-8"), vc.code_hash.encode("utf-8")):
            vc.attempts += 1
            await self.session.commit()
            raise HTTPException(status_code=400, detail="验证码错误")

        # Mark code as used
        vc.used = True
        await self.session.commit()

        # Hash password
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        # Create user
        user = User(
            external_id=f"credentials:{email}",
            email=email,
            name=name,
            password_hash=password_hash,
        )
        self.session.add(user)
        await self.session.commit()

        return RegisterResponse(success=True)

    async def check_email(self, email: str) -> CheckEmailResponse:
        """检查邮箱是否已注册。"""
        user = await self.user_repo.get_by_external_id(f"credentials:{email}")
        return CheckEmailResponse(registered=user is not None)

    async def verify_password(
        self, email: str, password: str
    ) -> VerifyPasswordResponse | None:
        """验证邮箱密码，返回用户信息或 None。"""
        user = await self.user_repo.get_by_external_id(f"credentials:{email}")
        if user is None or user.password_hash is None:
            return None

        if not bcrypt.checkpw(
            password.encode("utf-8"), user.password_hash.encode("utf-8")
        ):
            return None

        return VerifyPasswordResponse(
            id=user.external_id,
            email=user.email,
            name=user.name,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_auth_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/auth_service.py backend/tests/unit/test_auth_service.py
git commit -m "feat(backend): 添加认证服务（注册/验证码/密码验证）"
```

---

## Task 7: Backend — Auth API Routes

**Files:**
- Create: `backend/app/api/v1/auth/__init__.py`
- Create: `backend/app/api/v1/auth/routes.py`
- Modify: `backend/app/api/v1/router.py`

- [ ] **Step 1: Create auth routes**

Create `backend/app/api/v1/auth/__init__.py` (empty):

```python
```

Create `backend/app/api/v1/auth/routes.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_session
from app.schemas.auth import (
    CheckEmailRequest,
    CheckEmailResponse,
    RegisterRequest,
    RegisterResponse,
    SendCodeRequest,
    SendCodeResponse,
    VerifyPasswordRequest,
    VerifyPasswordResponse,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/send-code", response_model=SendCodeResponse)
async def send_code(
    data: SendCodeRequest,
    session: AsyncSession = Depends(get_session),
) -> SendCodeResponse:
    return await AuthService(session).send_code(data.email, data.purpose)


@router.post("/register", response_model=RegisterResponse)
async def register(
    data: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> RegisterResponse:
    return await AuthService(session).register(
        data.email, data.code, data.password, data.name
    )


@router.post("/check-email", response_model=CheckEmailResponse)
async def check_email(
    data: CheckEmailRequest,
    session: AsyncSession = Depends(get_session),
) -> CheckEmailResponse:
    return await AuthService(session).check_email(data.email)


@router.post("/verify-password", response_model=VerifyPasswordResponse | None)
async def verify_password(
    data: VerifyPasswordRequest,
    session: AsyncSession = Depends(get_session),
) -> VerifyPasswordResponse | None:
    return await AuthService(session).verify_password(data.email, data.password)
```

- [ ] **Step 2: Register auth router**

Edit `backend/app/api/v1/router.py`, add import and include:

```python
from app.api.v1.auth.routes import router as auth_router
```

And add to `api_router`:

```python
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
```

The final file should look like:

```python
from fastapi import APIRouter

from app.api.v1.auth.routes import router as auth_router
from app.api.v1.chat.routes import router as chat_router
from app.api.v1.knowledge_bases.routes import router as knowledge_bases_router
from app.api.v1.models.routes import router as models_router
from app.api.v1.notifications.routes import router as notifications_router
from app.api.v1.providers.routes import router as providers_router
from app.api.v1.users.routes import router as users_router
from app.api.v1.vector_dbs.routes import router as vector_dbs_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(providers_router, prefix="/providers", tags=["providers"])
api_router.include_router(models_router, prefix="/providers/{provider_id}/models", tags=["models"])
api_router.include_router(vector_dbs_router, prefix="/vector-dbs", tags=["vector-dbs"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(
    knowledge_bases_router, prefix="/knowledge-bases", tags=["knowledge-bases"]
)
```

- [ ] **Step 3: Run backend lint**

Run: `cd backend && ruff check app tests`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/auth/ backend/app/api/v1/router.py
git commit -m "feat(backend): 添加认证 API 路由（send-code/register/check-email/verify-password）"
```

---

## Task 8: Frontend — Auth API Client

**Files:**
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Add authApi to api.ts**

Append to `frontend/lib/api.ts` (after `notificationApi`):

```typescript
export const authApi = {
  sendCode: (email: string, purpose = "register") =>
    request<{ success: boolean; expires_in: number }>("/auth/send-code", {
      method: "POST",
      body: JSON.stringify({ email, purpose }),
    }),
  register: (data: {
    email: string;
    code: string;
    password: string;
    name?: string;
  }) =>
    request<{ success: boolean }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  checkEmail: (email: string) =>
    request<{ registered: boolean }>("/auth/check-email", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
};
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "feat(frontend): 添加认证 API 客户端"
```

---

## Task 9: Frontend — NextAuth Credentials Provider

**Files:**
- Modify: `frontend/lib/auth.ts`

- [ ] **Step 1: Add Credentials provider**

Rewrite `frontend/lib/auth.ts`:

```typescript
import NextAuth from "next-auth";
import type { JWT } from "next-auth/jwt";
import Credentials from "next-auth/providers/credentials";
import GitHub from "next-auth/providers/github";
import Google from "next-auth/providers/google";

/**
 * Auth.js v5 在未配置 database adapter 时，OAuth 回调里的 user.id 每次登录都是新的随机 UUID
 *（见 @auth/core getUserAndAccount），会导致 BFF 的 X-User-Id 变化、后端误判为新用户。
 * 使用 provider + providerAccountId（OAuth sub / GitHub id）作为跨会话稳定主键。
 */
function applyStableUserId(token: JWT, account: { provider?: string; providerAccountId?: string } | null | undefined) {
  if (!account?.provider || account.providerAccountId == null || account.providerAccountId === "") {
    return;
  }
  const stable = `${account.provider}:${String(account.providerAccountId)}`;
  token.sub = stable;
  token.id = stable;
}

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    GitHub({
      clientId: process.env.GITHUB_ID!,
      clientSecret: process.env.GITHUB_SECRET!,
    }),
    Google({
      clientId: process.env.GOOGLE_ID!,
      clientSecret: process.env.GOOGLE_SECRET!,
    }),
    Credentials({
      name: "credentials",
      credentials: {
        email: { type: "email" },
        password: { type: "password" },
      },
      authorize: async (credentials) => {
        const backendUrl = process.env.BACKEND_URL ?? "http://backend:8000";
        try {
          const res = await fetch(`${backendUrl}/api/v1/auth/verify-password`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: credentials?.email,
              password: credentials?.password,
            }),
          });
          if (!res.ok) return null;
          const user = await res.json();
          if (!user?.id) return null;
          return { id: user.id, email: user.email, name: user.name };
        } catch {
          return null;
        }
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user, account }) {
      if (account && account.provider !== "credentials") {
        applyStableUserId(token, account);
      } else if (user) {
        // Credentials: authorize 已返回正确的 id（credentials:email）
        token.sub = user.id;
        token.id = user.id;
      }
      return token;
    },
    async session({ session, token }) {
      const id = (token.id as string | undefined) ?? token.sub;
      if (id) (session.user as { id?: string }).id = id;
      return session;
    },
  },
});
```

- [ ] **Step 2: Run frontend typecheck**

Run: `cd frontend && pnpm typecheck`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/auth.ts
git commit -m "feat(frontend): 添加 NextAuth Credentials Provider"
```

---

## Task 10: Frontend — Login Page UI

**Files:**
- Modify: `frontend/app/login/page.tsx`

- [ ] **Step 1: Rewrite login page with email form**

Rewrite `frontend/app/login/page.tsx`:

```tsx
"use client";

import { signIn } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import {
  Database,
  FlaskConical,
  Github,
  KeyRound,
  Mail,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { authApi } from "@/lib/api";

type Mode = "login" | "register";

function EmailAuthForm({ callbackUrl }: { callbackUrl: string }) {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [codeSent, setCodeSent] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    if (cooldown <= 0) return;
    timerRef.current = setInterval(() => {
      setCooldown((c) => {
        if (c <= 1) {
          clearInterval(timerRef.current);
          return 0;
        }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(timerRef.current);
  }, [cooldown]);

  const handleCheckEmail = useCallback(async () => {
    if (!email || !email.includes("@")) return;
    try {
      const res = await authApi.checkEmail(email);
      setMode(res.registered ? "login" : "register");
    } catch {
      // ignore check errors
    }
  }, [email]);

  const handleSendCode = async () => {
    if (!email) return;
    setError("");
    setLoading(true);
    try {
      await authApi.sendCode(email);
      setCodeSent(true);
      setCooldown(60);
    } catch (e) {
      setError(e instanceof Error ? e.message : "发送验证码失败");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (mode === "register") {
        await authApi.register({ email, code, password, name: name || undefined });
      }
      // Login (or auto-login after register)
      const result = await signIn("credentials", {
        email,
        password,
        redirect: false,
        callbackUrl,
      });
      if (result?.error) {
        setError(mode === "register" ? "注册成功但自动登录失败，请手动登录" : "邮箱或密码错误");
      } else if (result?.url) {
        window.location.href = result.url;
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Mode tabs */}
      <div className="flex rounded-lg border border-border/60 bg-muted/30 p-0.5">
        <button
          type="button"
          onClick={() => {
            setMode("login");
            setError("");
          }}
          className={cn(
            "flex-1 rounded-md py-1.5 text-sm font-medium transition-colors",
            mode === "login"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          登录
        </button>
        <button
          type="button"
          onClick={() => {
            setMode("register");
            setError("");
          }}
          className={cn(
            "flex-1 rounded-md py-1.5 text-sm font-medium transition-colors",
            mode === "register"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          注册
        </button>
      </div>

      {/* Email */}
      <div className="space-y-1.5">
        <Label htmlFor="email" className="text-xs">
          邮箱
        </Label>
        <Input
          id="email"
          type="email"
          placeholder="name@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onBlur={handleCheckEmail}
          required
          className="h-9"
        />
      </div>

      {/* Register-only fields */}
      {mode === "register" && (
        <>
          <div className="space-y-1.5">
            <Label htmlFor="code" className="text-xs">
              验证码
            </Label>
            <div className="flex gap-2">
              <Input
                id="code"
                type="text"
                inputMode="numeric"
                maxLength={6}
                placeholder="6 位数字"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                required
                className="h-9 flex-1"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleSendCode}
                disabled={loading || cooldown > 0}
                className="h-9 shrink-0 text-xs"
              >
                {cooldown > 0 ? `${cooldown}s` : codeSent ? "重新发送" : "发送验证码"}
              </Button>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="name" className="text-xs">
              用户名 <span className="text-muted-foreground">(可选)</span>
            </Label>
            <Input
              id="name"
              type="text"
              placeholder="你的名字"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-9"
            />
          </div>
        </>
      )}

      {/* Password */}
      <div className="space-y-1.5">
        <Label htmlFor="password" className="text-xs">
          密码
        </Label>
        <Input
          id="password"
          type="password"
          placeholder={mode === "register" ? "至少 8 位，包含字母和数字" : "输入密码"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={mode === "register" ? 8 : undefined}
          className="h-9"
        />
      </div>

      {/* Error */}
      {error && (
        <p className="text-xs text-destructive">{error}</p>
      )}

      {/* Submit */}
      <Button type="submit" className="h-9 w-full text-sm" disabled={loading}>
        {loading ? "处理中…" : mode === "register" ? "注册" : "登录"}
      </Button>
    </form>
  );
}

function OAuthButtons() {
  const params = useSearchParams();
  const callbackUrl = params.get("callbackUrl") ?? "/providers";
  const oauthClass =
    "h-11 w-full rounded-xl border-border/80 bg-background/70 font-medium backdrop-blur-sm transition-all hover:border-primary/35 hover:bg-accent/40 hover:shadow-sm";
  return (
    <div className="space-y-3">
      <Button
        className={oauthClass}
        variant="outline"
        onClick={() => signIn("github", { callbackUrl })}
      >
        <Github className="mr-2 h-4 w-4" />
        使用 GitHub 登录
      </Button>
      <Button
        className={oauthClass}
        variant="outline"
        onClick={() => signIn("google", { callbackUrl })}
      >
        <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24" aria-hidden>
          <path
            fill="currentColor"
            d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
          />
          <path
            fill="currentColor"
            d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
          />
          <path
            fill="currentColor"
            d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
          />
          <path
            fill="currentColor"
            d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
          />
        </svg>
        使用 Google 登录
      </Button>
    </div>
  );
}

const highlights = [
  {
    icon: KeyRound,
    label: "Provider 加密托管",
    iconBg: "bg-gradient-to-br from-emerald-400 via-teal-500 to-cyan-500",
  },
  {
    icon: Database,
    label: "知识库与向量检索",
    iconBg: "bg-gradient-to-br from-sky-400 via-blue-500 to-indigo-500",
  },
  {
    icon: FlaskConical,
    label: "评测任务可追溯",
    iconBg: "bg-gradient-to-br from-violet-400 via-fuchsia-500 to-pink-500",
  },
] as const;

function LoginContent() {
  const params = useSearchParams();
  const callbackUrl = params.get("callbackUrl") ?? "/providers";

  return (
    <div className="w-full max-w-[17rem] space-y-8 lg:max-w-none">
      <div className="flex items-center gap-3 lg:hidden">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-primary via-fuchsia-500 to-cyan-500 text-white shadow-md animate-pulse-glow">
          <Sparkles className="h-4 w-4 drop-shadow" aria-hidden />
        </div>
        <div>
          <p className="text-base font-semibold tracking-tight">
            BuildTest AI
          </p>
          <p className="text-xs text-muted-foreground">
            RAG / Agent 开发 · 评测 · 迭代
          </p>
        </div>
      </div>

      <div className="relative space-y-7">
        <div className="space-y-2 text-center lg:text-left">
          <h1 className="text-2xl font-semibold tracking-tight text-ai-gradient sm:text-[1.6rem]">
            登录到工作台
          </h1>
          <p className="text-sm leading-relaxed text-muted-foreground">
            使用邮箱注册登录，或通过第三方账号快速登录。
          </p>
        </div>

        {/* Email auth form */}
        <EmailAuthForm callbackUrl={callbackUrl} />

        {/* Divider */}
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t border-border/60" />
          </div>
          <div className="relative flex justify-center text-xs">
            <span className="bg-background px-2 text-muted-foreground">
              或
            </span>
          </div>
        </div>

        {/* OAuth buttons */}
        <OAuthButtons />

        <p className="text-center text-xs leading-relaxed text-muted-foreground lg:text-left">
          登录即表示同意{" "}
          <span className="cursor-default underline underline-offset-4">
            服务条款
          </span>{" "}
          与{" "}
          <span className="cursor-default underline underline-offset-4">
            隐私政策
          </span>
          。
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <main className="grid min-h-screen min-w-0 bg-background lg:grid-cols-[minmax(0,1fr)_40rem]">
      {/* 左侧：深色品牌区（大屏）——渐变底 + 细网格 + 光晕，避免纯黑平板感 */}
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-zinc-950 via-zinc-900 to-zinc-950 p-10 text-zinc-50 lg:flex">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-gradient-to-b from-zinc-800/25 via-transparent to-black/50"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-grid-pattern opacity-[0.11] mask-radial-fade"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-noise opacity-[0.08] mix-blend-overlay"
        />
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.65]"
          style={{
            backgroundImage:
              "radial-gradient(ellipse 100% 80% at 0% 0%, rgba(99,102,241,0.22), transparent 55%), radial-gradient(ellipse 90% 70% at 100% 100%, rgba(14,165,233,0.18), transparent 50%), radial-gradient(circle at 50% 40%, rgba(250,250,250,0.03), transparent 45%)",
          }}
          aria-hidden
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 overflow-hidden"
        >
          <div className="animate-aurora absolute -right-32 top-1/4 h-72 w-72 rounded-full bg-gradient-to-br from-fuchsia-500/25 via-violet-500/15 to-transparent blur-3xl" />
          <div
            className="animate-aurora absolute bottom-1/4 -left-24 h-64 w-64 rounded-full bg-gradient-to-tr from-cyan-500/25 via-emerald-500/12 to-transparent blur-3xl"
            style={{ animationDelay: "4s" }}
          />
        </div>
        <div
          aria-hidden
          className="pointer-events-none absolute inset-y-0 right-0 w-px bg-gradient-to-b from-transparent via-white/25 to-transparent"
        />

        <div className="relative flex items-center gap-3">
          <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-white/20 via-fuchsia-400/30 to-cyan-400/25 text-white shadow-lg ring-1 ring-white/10 animate-pulse-glow">
            <Sparkles className="h-5 w-5 drop-shadow" aria-hidden />
          </div>
          <div className="flex min-w-0 flex-col leading-tight">
            <span className="text-lg font-semibold tracking-tight">
              BuildTest AI
            </span>
            <span className="mt-0.5 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-[0.14em] text-zinc-400">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
              </span>
              Online
            </span>
          </div>
        </div>

        <div className="relative flex flex-1 flex-col justify-center py-12">
          <ul className="max-w-sm space-y-3">
            {highlights.map((item) => {
              const Icon = item.icon;
              return (
                <li
                  key={item.label}
                  className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2.5 backdrop-blur-sm"
                >
                  <div
                    className={cn(
                      "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-white shadow-md",
                      item.iconBg,
                    )}
                  >
                    <Icon className="h-4 w-4" aria-hidden />
                  </div>
                  <span className="text-sm text-zinc-300">{item.label}</span>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="relative space-y-3">
          <p className="text-xl font-medium leading-relaxed text-zinc-50">
            让 AI 应用从「能跑起来」走到「敢上线」。
          </p>
          <p className="text-sm leading-relaxed text-zinc-400">
            面向 RAG / Agent 的开发 · 评测 · 迭代一体化平台。统一管理 Provider、知识库、Prompt
            版本与评测结果。
          </p>
        </div>
      </aside>

      {/* 右侧：浅色工作台背景，表单无卡片容器 */}
      <section className="relative flex min-w-0 flex-col overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-dot-pattern mask-fade-bottom opacity-60"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-noise opacity-[0.05] mix-blend-overlay"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 overflow-hidden"
        >
          <div className="animate-aurora absolute -right-32 -top-32 h-[22rem] w-[22rem] rounded-full bg-gradient-to-br from-primary/20 via-fuchsia-500/12 to-transparent blur-3xl" />
          <div
            className="animate-aurora absolute -bottom-28 -left-20 h-[20rem] w-[20rem] rounded-full bg-gradient-to-tr from-cyan-500/15 via-emerald-500/10 to-transparent blur-3xl"
            style={{ animationDelay: "3s" }}
          />
        </div>

        <div className="relative flex flex-1 flex-col items-center justify-center px-6 py-16 sm:px-10 sm:py-20 lg:px-32 lg:py-28">
          <Suspense
            fallback={
              <div className="py-2 text-center text-sm text-muted-foreground lg:text-left">
                加载中…
              </div>
            }
          >
            <LoginContent />
          </Suspense>
        </div>
      </section>
    </main>
  );
}
```

- [ ] **Step 2: Run frontend typecheck**

Run: `cd frontend && pnpm typecheck`
Expected: PASS (may need to verify Input and Label components exist in shadcn)

- [ ] **Step 3: Run frontend lint**

Run: `cd frontend && pnpm lint`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/app/login/page.tsx
git commit -m "feat(frontend): 登录页增加邮箱注册/登录表单"
```

---

## Task 11: Integration — Verify BFF Proxy Works for Auth Routes

**Files:**
- No new files (verification only)

- [ ] **Step 1: Verify BFF proxy forwards /auth/* routes**

The BFF proxy at `frontend/app/api/backend/[...path]/route.ts` forwards all requests under `/api/backend/*` to the backend's `/api/v1/*`. Since we added auth routes at `/api/v1/auth/*`, the frontend calls to `/api/backend/auth/send-code` etc. should automatically be proxied.

Read `frontend/app/api/backend/[...path]/route.ts` and confirm:
1. It proxies GET, POST, PUT, DELETE
2. The path construction strips `/api/backend/` prefix and prepends `/api/v1/`
3. Auth endpoints don't require `X-User-Id` (they are pre-authentication)

- [ ] **Step 2: Verify auth routes don't use get_current_user_id dependency**

Confirm that `backend/app/api/v1/auth/routes.py` only uses `get_session` (not `get_current_user_id`) for all four endpoints. This is critical — auth endpoints are called before the user has a session.

- [ ] **Step 3: Commit (if any fixes needed)**

If any adjustments were needed:
```bash
git add -A
git commit -m "fix: 修复认证路由 BFF 代理兼容性"
```

---

## Task 12: Backend — Final Verification

- [ ] **Step 1: Run all backend unit tests**

Run: `cd backend && python -m pytest tests/unit/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run backend lint**

Run: `cd backend && ruff check app tests`
Expected: PASS

- [ ] **Step 3: Run frontend typecheck and lint**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: ALL PASS
