"""Database configuration and session management."""

from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

from app.core.config import settings

_engine = None
_session_maker = None


def get_engine():
    """Get or create the engine."""
    global _engine, _session_maker

    if _engine is None:
        database_url = settings.database_url

        pool_kwargs = {}
        if settings.env == "test":
            pool_kwargs["poolclass"] = NullPool

        _engine = create_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            **pool_kwargs,
        )

        _session_maker = sessionmaker(
            bind=_engine,
            class_=Session,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    return _engine


@contextmanager
def get_session():
    """Get database session."""
    get_engine()  # Ensure engine is initialized

    with _session_maker() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def create_tables() -> None:
    """Create all database tables."""
    engine = get_engine()
    SQLModel.metadata.create_all(engine)


def clean_database() -> None:
    """Clean all tables before each test."""
    with get_session() as session:
        table_names = [
            f'"{table.name}"' for table in reversed(SQLModel.metadata.sorted_tables)
        ]
        if table_names:
            truncate_stmt = (
                "TRUNCATE " + ", ".join(table_names) + " RESTART IDENTITY CASCADE"
            )
            session.execute(text(truncate_stmt))


def close_db() -> None:
    """Close database connections."""
    global _engine, _session_maker

    if _engine:
        _engine.dispose()
        _engine = None
        _session_maker = None
