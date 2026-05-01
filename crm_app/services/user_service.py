from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from crm_app.database.session import get_session
from crm_app.models.user import User
from crm_app.services.auth_service import hash_password


def list_users() -> list[User]:
    with get_session() as session:
        return list(session.scalars(select(User).order_by(User.username.asc())).all())


def create_user(*, username: str, password: str) -> None:
    username = (username or "").strip()
    if not username:
        raise ValueError("Kullanıcı adı zorunludur.")

    password = (password or "").strip()
    if len(password) < 8:
        raise ValueError("Şifre en az 8 karakter olmalıdır.")

    with get_session() as session:
        user = User(
            username=username,
            password_hash=hash_password(password),
            must_change_password=True,
        )
        session.add(user)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise ValueError("Bu kullanıcı adı zaten mevcut.") from None

