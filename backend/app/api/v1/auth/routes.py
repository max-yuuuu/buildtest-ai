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
