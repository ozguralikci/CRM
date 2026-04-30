from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from crm_app.database.base import Base
from crm_app.utils.app_paths import get_database_path


DATABASE_PATH = get_database_path()
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Session:
    return SessionLocal()


def init_database() -> None:
    from crm_app.models import all_models  # noqa: F401
    from crm_app.services.sample_data import seed_sample_data

    Base.metadata.create_all(bind=engine)
    ensure_custom_field_schema()
    seed_sample_data()


def ensure_custom_field_schema() -> None:
    with engine.begin() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        }
        if "field_definitions" not in tables:
            return

        columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(field_definitions)")).fetchall()
        }

        if "is_visible" not in columns:
            connection.execute(
                text("ALTER TABLE field_definitions ADD COLUMN is_visible BOOLEAN DEFAULT 1")
            )
        if "sort_order" not in columns:
            connection.execute(
                text("ALTER TABLE field_definitions ADD COLUMN sort_order INTEGER DEFAULT 0")
            )
        if "options_json" not in columns:
            connection.execute(
                text("ALTER TABLE field_definitions ADD COLUMN options_json TEXT DEFAULT ''")
            )

        connection.execute(
            text("UPDATE field_definitions SET sort_order = id WHERE sort_order IS NULL OR sort_order = 0")
        )
