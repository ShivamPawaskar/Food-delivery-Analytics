"""Reusable SQLAlchemy engine, connection, transaction and health-check helpers."""
from __future__ import annotations

from contextlib import contextmanager
import os
from typing import Iterator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from config.settings import DATABASE_URL


def get_engine(url: str | None = None, *, pool_size: int = 5, max_overflow: int = 10) -> Engine:
    """Create an engine using DATABASE_URL (or an explicit URL for test sessions)."""
    url = url or os.getenv("DATABASE_URL") or DATABASE_URL
    if not url:
        raise RuntimeError("DATABASE_URL is not configured. Copy .env.example to .env and set PostgreSQL credentials.")
    return create_engine(url, pool_pre_ping=True, pool_size=pool_size, max_overflow=max_overflow, future=True)


@contextmanager
def connection(engine: Engine | None = None) -> Iterator:
    """Yield a managed connection and always return it to the pool."""
    owned = engine is None
    engine = engine or get_engine()
    try:
        with engine.connect() as conn:
            yield conn
    except SQLAlchemyError:
        raise
    finally:
        if owned:
            engine.dispose()


@contextmanager
def transaction(engine: Engine | None = None) -> Iterator:
    """Yield a transaction; SQLAlchemy commits on success and rolls back on exceptions."""
    owned = engine is None
    engine = engine or get_engine()
    try:
        with engine.begin() as conn:
            yield conn
    except SQLAlchemyError:
        raise
    finally:
        if owned:
            engine.dispose()


def test_connection(engine: Engine | None = None) -> dict:
    """Run a minimal health check and return server identity/version."""
    owned = engine is None
    engine = engine or get_engine()
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT current_database(), current_user, version()")).one()
            return {"database": row[0], "user": row[1], "version": row[2]}
    except SQLAlchemyError as exc:
        raise ConnectionError(f"PostgreSQL connection check failed: {exc.__class__.__name__}: {exc}") from exc
    finally:
        if owned:
            engine.dispose()


def close_engine(engine: Engine) -> None:
    """Dispose all pooled connections safely."""
    engine.dispose()
