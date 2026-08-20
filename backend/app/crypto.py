import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


def _secret_key() -> str:
    return os.getenv(
        "SECRET_KEY", "dev-secret-change-me-please-set-in-env-var-0123456789"
    )


def _fernet() -> Fernet:
    digest = hashlib.sha256(_secret_key().encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""
