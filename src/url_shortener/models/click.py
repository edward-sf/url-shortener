from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from url_shortener.models.base import Base


class Click(Base):
    """Model for clicks on shortened links."""

    __tablename__ = "clicks"
    __table_args__ = (
        CheckConstraint(
            "device_category IN ('desktop', 'mobile', 'tablet', 'bot', 'other')",
            name="device_category",
        ),
        Index(
            "ix_clicks_link_id_clicked_at",
            "link_id",
            "clicked_at",
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("links.id", ondelete="CASCADE"))

    clicked_at: Mapped[datetime] = mapped_column(server_default=func.now())
    referrer_domain: Mapped[str | None] = mapped_column(String(255))
    device_category: Mapped[str] = mapped_column(String(16))
