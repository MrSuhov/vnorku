from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config.settings import settings
import os

# Базовый класс для всех моделей
Base = declarative_base()

# Определяем application_name из переменной окружения или имени сервиса
SERVICE_NAME = os.getenv("SERVICE_NAME", "korzinka-unknown")

# Async engine для основной работы
async_engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.debug,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={"server_settings": {"application_name": SERVICE_NAME}}
)

# Sync engine для миграций
sync_engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_recycle=3600
)

# Session makers
AsyncSessionLocal = sessionmaker(
    async_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=sync_engine
)


async def get_async_session() -> AsyncSession:
    """Dependency для получения async сессии"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_sync_session():
    """Dependency для получения sync сессии"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
