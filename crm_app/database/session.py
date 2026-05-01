from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from crm_app.database.base import Base

_CONFIGURED = False
DATABASE_PATH: Path | None = None
DATABASE_URL: str | None = None
engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def configure_database(database_path: Path) -> None:
    """
    Configure SQLAlchemy engine/session factory for the active SQLite database file.

    Must be called once at application startup before any ORM operations.
    """
    global _CONFIGURED, DATABASE_PATH, DATABASE_URL, engine, SessionLocal

    if _CONFIGURED:
        raise RuntimeError("Database already configured. configure_database() must be called only once.")

    resolved = database_path.expanduser().resolve()
    DATABASE_PATH = resolved
    DATABASE_URL = f"sqlite:///{resolved.as_posix()}"
    engine = create_engine(DATABASE_URL, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    _CONFIGURED = True


def _require_configured() -> None:
    if not _CONFIGURED or SessionLocal is None or engine is None:
        raise RuntimeError(
            "Database not configured. Call configure_database(Path(...)) before using the ORM."
        )


def get_session() -> Session:
    _require_configured()
    return SessionLocal()


def init_database() -> None:
    _require_configured()
    from crm_app.models import all_models  # noqa: F401
    from crm_app.services.auth_service import ensure_default_admin
    from crm_app.services.sample_data import seed_sample_data

    Base.metadata.create_all(bind=engine)
    ensure_users_schema()
    ensure_companies_sales_schema()
    ensure_research_targets_rules_schema()
    ensure_custom_field_schema()
    ensure_default_admin()
    seed_sample_data()


def ensure_users_schema() -> None:
    _require_configured()
    with engine.begin() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        }
        if "users" not in tables:
            return

        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(users)")).fetchall()}
        if "must_change_password" not in columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT 1")
            )


def ensure_custom_field_schema() -> None:
    _require_configured()
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


def ensure_research_targets_rules_schema() -> None:
    """Additive kolonlar: kural tabanlı skor dökümü ve sürüm (FAZ 2D)."""
    _require_configured()
    with engine.begin() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        }
        if "research_targets" not in tables:
            return

        columns = {
            row[1] for row in connection.execute(text("PRAGMA table_info(research_targets)")).fetchall()
        }
        if "rules_score_breakdown" not in columns:
            connection.execute(text("ALTER TABLE research_targets ADD COLUMN rules_score_breakdown TEXT"))
        if "rules_score_version" not in columns:
            connection.execute(text("ALTER TABLE research_targets ADD COLUMN rules_score_version TEXT"))
        if "rules_score_updated_at" not in columns:
            connection.execute(text("ALTER TABLE research_targets ADD COLUMN rules_score_updated_at DATETIME"))


def ensure_companies_sales_schema() -> None:
    _require_configured()
    with engine.begin() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        }
        if "companies" not in tables:
            return

        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(companies)")).fetchall()}
        if "score" not in columns:
            connection.execute(text("ALTER TABLE companies ADD COLUMN score INTEGER DEFAULT 0"))
        if "status" not in columns:
            connection.execute(text("ALTER TABLE companies ADD COLUMN status TEXT DEFAULT 'lead'"))
        if "next_action" not in columns:
            connection.execute(text("ALTER TABLE companies ADD COLUMN next_action TEXT DEFAULT ''"))
