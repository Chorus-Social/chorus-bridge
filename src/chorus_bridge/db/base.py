from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class DatabaseSessionManager:
    """Wrapper around SQLAlchemy session handling."""

    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(database_url, future=True)
        self._session_factory = sessionmaker(
            bind=self._engine,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )

    def create_all(self) -> None:
        Base.metadata.create_all(self._engine)

    def dispose(self) -> None:
        self._engine.dispose()

    @contextmanager
    def session(self) -> Iterator["Session"]:
        from sqlalchemy.orm import Session

        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
