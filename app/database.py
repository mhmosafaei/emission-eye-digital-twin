from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_current_database_url: str | None = None


def get_database_url() -> str:
    return get_settings().database_url


def init_db(database_url: str | None = None) -> Engine:
    global _engine, _session_factory, _current_database_url

    database_url = database_url or get_database_url()
    if _engine is not None and _session_factory is not None and _current_database_url == database_url:
        return _engine

    if _engine is not None:
        _engine.dispose()

    if database_url.startswith("sqlite:///"):
        sqlite_path = Path(database_url.removeprefix("sqlite:///"))
        if sqlite_path.parent:
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    _engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
        future=True,
    )
    _session_factory = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )
    _current_database_url = database_url

    from . import models  # noqa: F401

    Base.metadata.create_all(_engine)
    return _engine


def dispose_db() -> None:
    global _engine, _session_factory, _current_database_url
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
    _current_database_url = None


def get_session() -> Session:
    init_db()
    assert _session_factory is not None
    return _session_factory()


def get_db() -> Generator[Session, None, None]:
    session = get_session()
    try:
        yield session
    finally:
        session.close()
