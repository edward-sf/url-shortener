from fastapi import APIRouter
from sqlalchemy import text

from url_shortener.deps.database import DbSession

router = APIRouter()


@router.get("/health")
async def health(session: DbSession) -> dict[str, str]:
    """Verify that the service is running and can reach the database."""
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}
