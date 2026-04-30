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
