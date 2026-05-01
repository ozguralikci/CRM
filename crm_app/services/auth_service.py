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


def get_user_by_id(user_id: int) -> User | None:
    with get_session() as session:
        return session.get(User, user_id)


def ensure_default_admin() -> None:
    with get_session() as session:
        existing_user = session.scalar(select(User.id).limit(1))
        if not existing_user:
            user = User(
                username="admin",
                password_hash=hash_password("admin"),
                must_change_password=True,
            )
            session.add(user)
            session.commit()
            LOGGER.warning("Default admin user created. Please change password later.")
            return

        admin = session.scalar(select(User).where(User.username == "admin").limit(1))
        if not admin:
            return

        if verify_password("admin", admin.password_hash):
            if not admin.must_change_password:
                admin.must_change_password = True
                session.commit()
            LOGGER.warning("Default admin user still uses default password. Please change password later.")


def change_password(*, user_id: int, old_password: str, new_password: str) -> None:
    new_password = (new_password or "").strip()
    if len(new_password) < 8:
        raise ValueError("Yeni şifre en az 8 karakter olmalıdır.")

    with get_session() as session:
        user = session.get(User, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        if not verify_password(old_password or "", user.password_hash):
            raise ValueError("Eski şifre hatalı.")

        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        session.commit()

