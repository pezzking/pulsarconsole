"""Notification delivery tracking model."""

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.notification import Notification
    from app.models.notification_channel import NotificationChannel


class DeliveryStatus(str, Enum):
    """Status of a notification delivery."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class NotificationDelivery(Base):
    """Tracks delivery of notifications to external channels."""

    __tablename__ = "notification_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    notification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notification_channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default=DeliveryStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    notification: Mapped["Notification"] = relationship(
        "Notification",
        foreign_keys=[notification_id],
    )
    channel: Mapped["NotificationChannel"] = relationship(
        "NotificationChannel",
        foreign_keys=[channel_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "notification_id",
            "channel_id",
            name="uq_delivery_notification_channel",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationDelivery(notification={self.notification_id}, "
            f"channel={self.channel_id}, "
            f"status='{self.status}')>"
        )
