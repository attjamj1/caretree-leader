from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./amazing_race.db")

if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    connect_args = {"sslmode": "require"}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from models import models  # noqa
    Base.metadata.create_all(bind=engine)
    # Safe migrations — add columns that may not exist yet
    _safe_migrate()
    print("Database tables created.")


def _safe_migrate():
    """Add new columns to existing tables without breaking anything."""
    from sqlalchemy import text, inspect
    inspector = inspect(engine)
    migrations = [
        ("projects",  "user_id",              "VARCHAR"),
        ("projects",  "live_token",           "VARCHAR"),
        ("teams",     "member_numbers",       "JSON"),
        ("stations",  "chain_clue",           "TEXT DEFAULT ''"),
        ("stations",  "chain_media_url",      "VARCHAR DEFAULT ''"),
        ("stations",  "chain_hint",           "TEXT DEFAULT ''"),
        ("stations",  "chain_photo_required", "BOOLEAN DEFAULT FALSE"),
        ("progress",  "awaiting_chain",       "BOOLEAN DEFAULT FALSE"),
        ("projects",  "finish_message",       "TEXT DEFAULT ''"),
    ]
    with engine.connect() as conn:
        for table, col, typ in migrations:
            try:
                existing = {c["name"] for c in inspector.get_columns(table)}
            except Exception:
                continue
            if col not in existing:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ}"))
                    conn.commit()
                    print(f"Migration: added column {table}.{col}")
                except Exception as e:
                    print(f"Migration warning ({table}.{col}): {e}")