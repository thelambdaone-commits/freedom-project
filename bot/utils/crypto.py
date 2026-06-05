from cryptography.fernet import Fernet
from bot.utils.config import settings


def get_cipher() -> Fernet:
    if not settings.is_encryption_configured:
        raise RuntimeError("FERNET_KEY not configured in .env")
    return Fernet(settings.fernet_key.encode())


def encrypt(data: str) -> bytes:
    return get_cipher().encrypt(data.encode())


def decrypt(data: bytes) -> str:
    return get_cipher().decrypt(data).decode()
