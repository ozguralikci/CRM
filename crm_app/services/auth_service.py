from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets

from sqlalchemy import select

from crm_app.database.session import get_session
from crm_app.models.user import User


LOGGER = logging.getLogger(__name__)

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 120_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(dk).decode("ascii")
    return f"{_ALGO}${_ITERATIONS}${salt_b64}${hash_b64}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algo, iters_str, salt_b64, hash_b64 = password_hash.split("$", 3)
        if algo != _ALGO:
            return False
        iters = int(iters_str)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(hash_b64.encode("ascii"))
    except Exception:
        return False

    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
    return hmac.compare_digest(dk, expected)


def authenticate(username: str, password: str) -> User | None:
    username = (username or "").strip()
    if not username:
        return None

    with get_session() as session:
        user = session.scalar(select(User).where(User.username == username).limit(1))
        if not user:
            return None
        if not verify_password(password or "", user.password_hash):
            return None
        return user


def ensure_default_admin() -> None:
    with get_session() as session:
        existing_user = session.scalar(select(User.id).limit(1))
        if existing_user:
            return

        user = User(username="admin", password_hash=hash_password("admin"))
        session.add(user)
        session.commit()
        LOGGER.warning("Default admin user created. Please change password later.")

