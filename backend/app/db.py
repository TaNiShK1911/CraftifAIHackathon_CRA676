"""
db.py — SQLite engine, session factory, and table creation.
Uses WAL mode so the REST API can read while the ingest writes.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# Import models so SQLModel registers them before create_all
import app.models  # noqa: F401

_engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """Create all tables and enable WAL mode."""
    SQLModel.metadata.create_all(_engine)
    with _engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
        conn.commit()


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session."""
    with Session(_engine) as session:
        yield session


def get_engine():
    return _engine
