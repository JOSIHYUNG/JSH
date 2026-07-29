from collections.abc import Generator
from pathlib import Path

from sqlalchemy import event, text
from sqlmodel import Session, create_engine

from app.core.config import get_settings


settings = get_settings()
if settings.database_path is not None:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
settings.storage_root.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)


@event.listens_for(engine, "connect")
def configure_sqlite(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def init_database() -> None:
    with engine.begin() as connection:
        connection.execute(text("SELECT 1"))
