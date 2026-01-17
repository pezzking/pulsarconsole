"""Notification channel configuration model."""

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class ChannelType(str, Enum):
    """Types of notification channels."""

    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"


class NotificationChannel(BaseModel):
    """Configuration for external notification channels."""

    __tablename__ = "notification_channels"

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    channel_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    # Filtering - null means all
    severity_filter: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    type_filter: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Encrypted configuration JSON
    config_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Ownership
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    created_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by_id],
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationChannel(name='{self.name}', "
            f"type='{self.channel_type}', "
            f"enabled={self.is_enabled})>"
        )
