import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from url_shortener.repos import api_keys as api_keys_repo

HASH = "a" * 64


async def test_create_returns_persisted_key(db_session: AsyncSession) -> None:
    api_key = await api_keys_repo.create(db_session, prefix="sk_abcdefgh", key_hash=HASH)

    assert api_key.id is not None
    assert api_key.prefix == "sk_abcdefgh"
    assert api_key.key_hash == HASH
    assert api_key.created_at is not None
    assert api_key.created_at.tzinfo is not None
    assert api_key.last_used_at is None
    assert api_key.revoked_at is None


async def test_create_rejects_duplicate_prefix(db_session: AsyncSession) -> None:
    await api_keys_repo.create(db_session, prefix="sk_abcdefgh", key_hash=HASH)

    with pytest.raises(IntegrityError):
        await api_keys_repo.create(db_session, prefix="sk_abcdefgh", key_hash="b" * 64)


async def test_get_by_prefix_finds_key(db_session: AsyncSession) -> None:
    created = await api_keys_repo.create(db_session, prefix="sk_abcdefgh", key_hash=HASH)

    found = await api_keys_repo.get_by_prefix(db_session, "sk_abcdefgh")

    assert found is not None
    assert found.id == created.id


async def test_get_by_prefix_returns_none_for_unknown_prefix(db_session: AsyncSession) -> None:
    assert await api_keys_repo.get_by_prefix(db_session, prefix="sk_missing0") is None


async def test_revoke_sets_revoked_at(db_session: AsyncSession) -> None:
    api_key = await api_keys_repo.create(db_session, prefix="sk_abcdefgh", key_hash=HASH)

    assert await api_keys_repo.revoke(db_session, api_key.id) is True

    await db_session.refresh(api_key)
    assert api_key.revoked_at is not None


async def test_revoke_twice_reports_false(db_session: AsyncSession) -> None:
    api_key = await api_keys_repo.create(db_session, prefix="sk_abcdefgh", key_hash=HASH)
    await api_keys_repo.revoke(db_session, api_key.id)

    assert await api_keys_repo.revoke(db_session, api_key.id) is False


async def test_revoke_unknown_key_reports_false(db_session: AsyncSession) -> None:
    assert await api_keys_repo.revoke(db_session, api_key_id=999_999) is False
