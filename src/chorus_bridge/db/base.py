from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session


Base = declarative_base()


class DatabaseSessionManager:
    """Manages SQLAlchemy database sessions and engine lifecycle."""

    def __init__(self, database_url: str) -> None:
        """Initializes the DatabaseSessionManager.

        Args:
            database_url: The SQLAlchemy-compatible URL for the database connection.
        """
        self._engine = create_engine(database_url)
        self._session_factory = sessionmaker(
            autocommit=False, autoflush=False, bind=self._engine
        )

    def create_all(self) -> None:
        """Creates all database tables defined in the Base metadata."""
        Base.metadata.create_all(self._engine, checkfirst=True)

    def dispose(self) -> None:
        """Disposes of the database engine, closing all connections."""
        self._engine.dispose()

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Provides a transactional SQLAlchemy session.

        Yields:
            A SQLAlchemy Session object.

        Raises:
            Exception: If any error occurs during the session, a rollback is performed.
        """
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
