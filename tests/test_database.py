import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from url_shortener.models import APIKey


@pytest.mark.parametrize("attempt", [1, 2])
async def test_committed_rows_do_not_leak_between_tests(
    db_session: AsyncSession,
    attempt: int,
) -> None:
    db_session.add(APIKey(prefix="sk_isolated", key_hash="a" * 64))
    await db_session.commit()

    count = await db_session.scalar(select(func.count()).select_from(APIKey))

    assert count == 1
