import random
import string
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException
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
        if email in self._BUILTIN_TEST_ACCOUNTS:
            return CheckEmailResponse(registered=True)
        user = await self.user_repo.get_by_external_id(f"credentials:{email}")
        return CheckEmailResponse(registered=user is not None)

    # 内置测试账号，仅用于开发环境
    _BUILTIN_TEST_ACCOUNTS: dict[str, tuple[str, str | None]] = {
        "admin@buildtest.ai": ("123456", "Admin"),
    }

    async def verify_password(
        self, email: str, password: str
    ) -> VerifyPasswordResponse | None:
        # 先检查内置测试账号
        if email in self._BUILTIN_TEST_ACCOUNTS:
            expected_password, name = self._BUILTIN_TEST_ACCOUNTS[email]
            if password == expected_password:
                return VerifyPasswordResponse(
                    id=f"credentials:{email}",
                    email=email,
                    name=name,
                )
            return None

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
