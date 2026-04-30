from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.verification_code import VerificationCode
from app.repositories.verification_code import VerificationCodeRepository


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
