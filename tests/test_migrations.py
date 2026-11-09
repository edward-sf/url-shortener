import asyncio

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

APP_TABLES = {"api_keys", "links", "clicks"}


async def get_table_names(database_url: str) -> set[str]:
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        names = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
    await engine.dispose()
    return set(names)


def test_migrations_round_trip(
    alembic_config: Config,
    migrated_database: None,
    test_database_url: str,
) -> None:
    assert asyncio.run(get_table_names(test_database_url)) >= APP_TABLES

    command.downgrade(alembic_config, "base")
    assert asyncio.run(get_table_names(test_database_url)).isdisjoint(APP_TABLES)

    command.upgrade(alembic_config, "head")
    assert asyncio.run(get_table_names(test_database_url)) >= APP_TABLES

    command.check(alembic_config)
