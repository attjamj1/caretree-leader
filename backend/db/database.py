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
    with engine.connect() as conn:
        inspector = inspect(engine)
        existing = {col["name"] for col in inspector.get_columns("projects")}
        to_add = {
            "user_id": "VARCHAR",
            "live_token": "VARCHAR",
        }
        for col, typ in to_add.items():
            if col not in existing:
                try:
                    conn.execute(text(f"ALTER TABLE projects ADD COLUMN {col} {typ}"))
                    conn.commit()
                    print(f"Migration: added column projects.{col}")
                except Exception as e:
                    print(f"Migration warning ({col}): {e}")