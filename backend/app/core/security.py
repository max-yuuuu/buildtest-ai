from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String, TypeDecorator

from app.core.config import settings


def _cipher() -> Fernet:
    if not settings.app_encryption_key:
        raise RuntimeError("APP_ENCRYPTION_KEY not configured")
    return Fernet(settings.app_encryption_key.encode())


def encrypt(plain: str) -> str:
    return _cipher().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _cipher().decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise ValueError("Invalid encrypted value") from e


class EncryptedString(TypeDecorator):
    """SQLAlchemy 类型:明文进,密文出;密文进,明文出。"""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return decrypt(value)
