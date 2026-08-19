from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
if settings.is_sqlite:
    Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    echo=settings.sql_echo,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if settings.is_sqlite else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_schema() -> None:
    # 导入模型以确保 metadata 完整。
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
