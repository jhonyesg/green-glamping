import json

from cryptography.fernet import Fernet

from app.config import get_settings


class FernetKeyManager:
    def __init__(self) -> None:
        settings = get_settings()
        raw = settings.SECRET_KEY.encode()
        # Fernet requires a 32-byte url-safe base64 key; derive one from SECRET_KEY
        import base64
        import hashlib
        digest = hashlib.sha256(raw).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, plain: dict) -> str:
        return self._fernet.encrypt(json.dumps(plain).encode()).decode()

    def decrypt(self, encrypted: str) -> dict:
        return json.loads(self._fernet.decrypt(encrypted.encode()).decode())


_key_manager: FernetKeyManager | None = None


def _get_key_manager() -> FernetKeyManager:
    global _key_manager
    if _key_manager is None:
        _key_manager = FernetKeyManager()
    return _key_manager


def encrypt_credentials(plain: dict) -> str:
    return _get_key_manager().encrypt(plain)


def decrypt_credentials(encrypted: str) -> dict:
    return _get_key_manager().decrypt(encrypted)
