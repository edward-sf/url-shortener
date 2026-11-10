from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from url_shortener.models import APIKey


async def create(session: AsyncSession, *, prefix: str, key_hash: str) -> APIKey:
    """Insert a key row and return it with its database-generated fields filled in."""
    api_key = APIKey(prefix=prefix, key_hash=key_hash)
    session.add(api_key)
    await session.flush()
    return api_key


async def get_by_prefix(session: AsyncSession, prefix: str) -> APIKey | None:
    """Find a key by its public prefix, whether or not it has been revoked."""
    return await session.scalar(select(APIKey).where(APIKey.prefix == prefix))


async def revoke(session: AsyncSession, api_key_id: int) -> bool:
    """Revoke a key. Return False if it doesn't exist or was already revoked."""
    revoked_id = await session.scalar(
        update(APIKey)
        .where(APIKey.id == api_key_id, APIKey.revoked_at.is_(None))
        .values(revoked_at=func.now())
        .returning(APIKey.id)
    )
    return revoked_id is not None
