from datetime import datetime

from sqlalchemy import ForeignKey, Identity, Index, String, Text, false, func, text
from sqlalchemy.orm import Mapped, mapped_column

from url_shortener.models.base import Base


class Link(Base):
    """Model for shortened links."""

    __tablename__ = "links"
    __table_args__ = (
        Index(
            "ix_links_api_key_id_created_at_id",
            "api_key_id",
            text("created_at DESC"),
            text("id DESC"),
        ),
        Index(
            "ix_links_expires_at",
            "expires_at",
            postgresql_where=text("expires_at IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    is_custom: Mapped[bool] = mapped_column(server_default=false())
    target_url: Mapped[str] = mapped_column(Text)
    api_key_id: Mapped[int] = mapped_column(ForeignKey("api_keys.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime | None]
