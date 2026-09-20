"""
Database engine/session setup.

DATABASE_URL is read from the environment - never hard-coded. For local
Postgres: postgresql+psycopg2://user:pass@host:port/dbname

Tests do not use this module: they build their own in-memory SQLite engine
directly, so the test suite never needs a live Postgres instance or a real
DATABASE_URL to run.
"""
from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_engine(database_url: Optional[str] = None):
    url = database_url or DATABASE_URL
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Configure it via environment variable "
            "(see backend/.env.example) - never hard-code credentials in source."
        )
    return create_engine(url, future=True)


def get_sessionmaker(database_url: Optional[str] = None):
    engine = get_engine(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db(engine) -> None:
    """Create tables if they don't exist.

    Interim bootstrap until Alembic migrations are wired up in a later
    "DB bootstrap" phase. Safe to call repeatedly.
    """
    Base.metadata.create_all(bind=engine)
