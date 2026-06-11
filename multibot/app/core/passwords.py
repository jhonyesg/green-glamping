"""Password hashing with PBKDF2-SHA256 (stdlib only, no extra deps)."""

import hashlib
import secrets

_ITERATIONS = 100_000


def hash_password(plain: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), _ITERATIONS)
    return f"{salt}${digest.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$", 1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), _ITERATIONS)
    return secrets.compare_digest(digest.hex(), expected)
