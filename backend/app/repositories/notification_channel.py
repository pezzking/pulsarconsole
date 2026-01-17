"""Repository for notification channel data access."""


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_channel import ChannelType, NotificationChannel
from app.repositories.base import BaseRepository


class NotificationChannelRepository(BaseRepository[NotificationChannel]):
    """Repository for notification channel operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(NotificationChannel, session)

    async def get_by_name(self, name: str) -> NotificationChannel | None:
        """Get channel by name."""
        result = await self.session.execute(
            select(NotificationChannel).where(NotificationChannel.name == name)
        )
        return result.scalar_one_or_none()

    async def get_by_type(self, channel_type: ChannelType) -> list[NotificationChannel]:
        """Get all channels of a specific type."""
        result = await self.session.execute(
            select(NotificationChannel).where(
                NotificationChannel.channel_type == channel_type.value
            )
        )
        return list(result.scalars().all())

    async def get_enabled_channels(self) -> list[NotificationChannel]:
        """Get all enabled channels."""
        result = await self.session.execute(
            select(NotificationChannel).where(NotificationChannel.is_enabled.is_(True))
        )
        return list(result.scalars().all())

    async def get_matching_channels(
        self,
        severity: str,
        notification_type: str,
    ) -> list[NotificationChannel]:
        """Get enabled channels that match the given severity and type filters."""
        # First get all enabled channels
        channels = await self.get_enabled_channels()

        # Filter in Python for JSONB contains logic
        matching = []
        for channel in channels:
            # Check severity filter (null means all)
            if (
                channel.severity_filter is not None
                and severity not in channel.severity_filter
            ):
                continue

            # Check type filter (null means all)
            if (
                channel.type_filter is not None
                and notification_type not in channel.type_filter
            ):
                continue

            matching.append(channel)

        return matching
