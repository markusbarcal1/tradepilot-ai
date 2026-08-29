from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import REPOSITORY_ROOT, settings


class Base(DeclarativeBase):
    pass


def resolve_database_url(database_url: str) -> URL:
    """Resolve relative SQLite paths against the repository root."""
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite"):
        return url

    database = url.database
    if not database or database == ":memory:":
        return url

    database_path = Path(database)
    if not database_path.is_absolute():
        database_path = (REPOSITORY_ROOT / database_path).resolve()
    return url.set(database=str(database_path))


def create_database_engine(database_url: str = settings.database_url):
    url = resolve_database_url(database_url)
    connect_args = {"check_same_thread": False} if url.drivername == "sqlite" else {}
    return create_engine(url, connect_args=connect_args)


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(session_factory=None):
    factory = session_factory or SessionLocal
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_schema(database_engine=None):
    # Import registers all model tables on the shared metadata.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=database_engine or engine)
