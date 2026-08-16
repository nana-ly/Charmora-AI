from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from core.config import DatabaseConfig


@dataclass(frozen=True)
class DatabaseRuntime:
    engine: Engine
    session_factory: sessionmaker[Session]

    def session(self) -> Iterator[Session]:
        with self.session_factory() as db_session:
            yield db_session

    def check_connection(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def check_migration(self, expected_revision: str) -> None:
        with self.engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != expected_revision:
            raise RuntimeError(
                f"database migration mismatch: expected {expected_revision}, got {revision or 'none'}"
            )


def create_database_runtime(config: DatabaseConfig) -> DatabaseRuntime:
    engine = create_engine(
        config.url,
        pool_pre_ping=True,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        pool_timeout=config.pool_timeout_seconds,
        echo=config.echo,
    )
    return DatabaseRuntime(
        engine=engine,
        session_factory=sessionmaker(
            bind=engine,
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
        ),
    )
