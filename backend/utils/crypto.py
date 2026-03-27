import base64
import hashlib
import os
from functools import lru_cache

from cryptography.fernet import Fernet


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    raw = os.environ.get("AIOPS_SECRET_KEY", "")
    if raw:
        key_material = hashlib.sha256(raw.encode("utf-8")).digest()
    else:
        key_material = hashlib.sha256(b"aiops-dev-secret-key").digest()
    key = base64.urlsafe_b64encode(key_material)
    return Fernet(key)


def encrypt_secret(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text:
        return text
    if text.startswith("enc$"):
        return text
    token = _get_fernet().encrypt(text.encode("utf-8")).decode("utf-8")
    return f"enc${token}"


def decrypt_secret(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text.startswith("enc$"):
        return text
    token = text[4:]
    plain = _get_fernet().decrypt(token.encode("utf-8"))
    return plain.decode("utf-8")
