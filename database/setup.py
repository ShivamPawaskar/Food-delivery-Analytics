"""Create the configured PostgreSQL database and initialize its schema."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from config.settings import DATABASE_URL
from database.connection import get_engine, test_connection

DATABASE_NAME = "food_delivery_analytics"


def create_database(url: str | None = None, database_name: str = DATABASE_NAME) -> None:
    url = url or os.getenv("DATABASE_URL") or DATABASE_URL
    if not url:
        raise RuntimeError("Set DATABASE_URL before database setup.")
    parsed = make_url(url)
    admin_engine = create_engine(parsed.set(database="postgres"), pool_pre_ping=True)
    try:
        with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": database_name}).scalar()
            if not exists:
                identifier = admin_engine.dialect.identifier_preparer.quote(database_name)
                conn.exec_driver_sql(f"CREATE DATABASE {identifier}")
    finally:
        admin_engine.dispose()


def initialize_schema(engine=None) -> None:
    owned = engine is None
    engine = engine or get_engine()
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    try:
        with engine.begin() as conn:
            for statement in schema.split(";"):
                statement = statement.strip()
                if statement:
                    conn.exec_driver_sql(statement)
    finally:
        if owned:
            engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create-database", action="store_true", help="Create food_delivery_analytics if absent")
    args = parser.parse_args()
    if args.create_database:
        create_database()
    engine = get_engine()
    try:
        initialize_schema(engine)
        print(test_connection(engine))
        print("Schema initialized successfully.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
