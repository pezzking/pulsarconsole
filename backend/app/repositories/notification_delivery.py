"""Repository for notification delivery tracking."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_delivery import DeliveryStatus, NotificationDelivery
from app.repositories.base import BaseRepository


class NotificationDeliveryRepository(BaseRepository[NotificationDelivery]):
    """Repository for notification delivery operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(NotificationDelivery, session)

    async def get_for_notification(
        self,
        notification_id: UUID,
    ) -> list[NotificationDelivery]:
        """Get all delivery records for a notification."""
        result = await self.session.execute(
            select(NotificationDelivery)
            .where(NotificationDelivery.notification_id == notification_id)
            .order_by(NotificationDelivery.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_for_channel(
        self,
        channel_id: UUID,
        limit: int = 100,
    ) -> list[NotificationDelivery]:
        """Get recent delivery records for a channel."""
        result = await self.session.execute(
            select(NotificationDelivery)
            .where(NotificationDelivery.channel_id == channel_id)
            .order_by(NotificationDelivery.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_pending(self, max_attempts: int = 3) -> list[NotificationDelivery]:
        """Get pending deliveries that haven't exceeded max attempts."""
        result = await self.session.execute(
            select(NotificationDelivery).where(
                and_(
                    NotificationDelivery.status == DeliveryStatus.PENDING.value,
                    NotificationDelivery.attempts < max_attempts,
                )
            )
        )
        return list(result.scalars().all())

    async def mark_sent(self, delivery_id: UUID) -> bool:
        """Mark a delivery as sent."""
        result = await self.session.execute(
            update(NotificationDelivery)
            .where(NotificationDelivery.id == delivery_id)
            .values(
                status=DeliveryStatus.SENT.value,
                attempts=NotificationDelivery.attempts + 1,
                last_attempt_at=datetime.now(UTC),
                error_message=None,
            )
        )
        return result.rowcount > 0

    async def mark_failed(self, delivery_id: UUID, error: str) -> bool:
        """Mark a delivery as failed with error message."""
        result = await self.session.execute(
            update(NotificationDelivery)
            .where(NotificationDelivery.id == delivery_id)
            .values(
                status=DeliveryStatus.FAILED.value,
                attempts=NotificationDelivery.attempts + 1,
                last_attempt_at=datetime.now(UTC),
                error_message=error,
            )
        )
        return result.rowcount > 0

    async def increment_attempt(self, delivery_id: UUID) -> bool:
        """Increment attempt count without changing status."""
        result = await self.session.execute(
            update(NotificationDelivery)
            .where(NotificationDelivery.id == delivery_id)
            .values(
                attempts=NotificationDelivery.attempts + 1,
                last_attempt_at=datetime.now(UTC),
            )
        )
        return result.rowcount > 0

    async def reset_to_pending(self, delivery_id: UUID) -> bool:
        """Reset a failed delivery to pending for retry."""
        result = await self.session.execute(
            update(NotificationDelivery)
            .where(NotificationDelivery.id == delivery_id)
            .values(
                status=DeliveryStatus.PENDING.value,
                error_message=None,
            )
        )
        return result.rowcount > 0
