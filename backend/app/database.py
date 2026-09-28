from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import settings

_engine_kwargs = {"pool_pre_ping": True}

if settings.database_url.startswith("sqlite"):
    # check_same_thread: needed because TestClient calls the app from a
    # worker thread. StaticPool: makes every checkout reuse the *same*
    # underlying connection, which is required for ":memory:" (each new
    # sqlite3 connection otherwise gets its own empty in-memory DB) and
    # is also what avoids flaky "readonly database" errors seen with a
    # pooled, file-based sqlite DB that gets deleted between test runs.
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["poolclass"] = StaticPool

engine = create_engine(settings.database_url, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
