"""SQLAlchemy engine + session helpers, plus auto-seed and migration on import."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "app.db"
DB_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(DB_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def ensure_seeded() -> None:
    """Run data/seed.py if app.db is missing, otherwise just create any
    missing tables (additive migration — never drops data)."""
    if not DB_PATH.exists():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        from data import seed
        seed.main()
        return
    # Idempotent: create any tables in metadata that don't exist yet.
    from data import seed
    seed.metadata.create_all(engine)
