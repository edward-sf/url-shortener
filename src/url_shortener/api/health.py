from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint to verify that the service is running."""
    return {"status": "ok"}
