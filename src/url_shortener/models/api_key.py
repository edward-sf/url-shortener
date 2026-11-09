from datetime import datetime

from sqlalchemy import CHAR, Identity, String, func
from sqlalchemy.orm import Mapped, mapped_column

from url_shortener.models.base import Base


class APIKey(Base):
    """Model for API keys."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    prefix: Mapped[str] = mapped_column(String(16), unique=True)
    key_hash: Mapped[str] = mapped_column(CHAR(64))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_used_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]
