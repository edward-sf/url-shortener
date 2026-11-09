import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from url_shortener.models import APIKey, Link


@pytest.mark.parametrize("attempt", [1, 2])
async def test_committed_rows_do_not_leak_between_tests(
    db_session: AsyncSession,
    attempt: int,
) -> None:
    db_session.add(APIKey(prefix="sk_isolated", key_hash="a" * 64))
    await db_session.commit()

    count = await db_session.scalar(select(func.count()).select_from(APIKey))

    assert count == 1


async def test_deleting_api_key_removes_its_links(db_session: AsyncSession) -> None:
    api_key = APIKey(prefix="sk_cascade", key_hash="a" * 64)
    db_session.add(api_key)
    await db_session.flush()
    key_id = api_key.id

    db_session.add(Link(code="abc1234", target_url="https://example.com", api_key_id=key_id))
    await db_session.flush()

    link_count = select(func.count()).select_from(Link).where(Link.api_key_id == key_id)

    assert await db_session.scalar(link_count) == 1
    await db_session.execute(delete(APIKey).where(APIKey.id == key_id))
    assert await db_session.scalar(link_count) == 0
