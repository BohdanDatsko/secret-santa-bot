from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings


def create_database(settings: Settings):
    engine = create_async_engine(
        settings.sqlalchemy_database_url,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
    return engine, async_sessionmaker(engine, expire_on_commit=False)
