"""Service for managing notification channels."""

import json
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import decrypt_value, encrypt_value, mask_sensitive
from app.models.notification_channel import ChannelType, NotificationChannel
from app.models.notification_delivery import DeliveryStatus, NotificationDelivery
from app.repositories.notification_channel import NotificationChannelRepository
from app.repositories.notification_delivery import NotificationDeliveryRepository

logger = get_logger(__name__)


# Fields to mask in config responses
SENSITIVE_FIELDS = {"smtp_password", "webhook_url", "url"}


class NotificationChannelService:
    """Service for notification channel management."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.channel_repo = NotificationChannelRepository(session)
        self.delivery_repo = NotificationDeliveryRepository(session)

    async def get_channel(self, channel_id: UUID) -> NotificationChannel | None:
        """Get a channel by ID."""
        return await self.channel_repo.get_by_id(channel_id)

    async def get_channel_by_name(self, name: str) -> NotificationChannel | None:
        """Get a channel by name."""
        return await self.channel_repo.get_by_name(name)

    async def list_channels(self) -> list[NotificationChannel]:
        """List all channels."""
        return await self.channel_repo.get_all(limit=100)

    async def create_channel(
        self,
        name: str,
        channel_type: ChannelType,
        config: dict[str, Any],
        is_enabled: bool = True,
        severity_filter: list[str] | None = None,
        type_filter: list[str] | None = None,
        created_by_id: UUID | None = None,
    ) -> NotificationChannel:
        """Create a new notification channel."""
        # Encrypt the entire config as JSON
        config_json = json.dumps(config)
        config_encrypted = encrypt_value(config_json)

        channel = await self.channel_repo.create(
            name=name,
            channel_type=channel_type.value,
            config_encrypted=config_encrypted,
            is_enabled=is_enabled,
            severity_filter=severity_filter,
            type_filter=type_filter,
            created_by_id=created_by_id,
        )

        logger.info(
            "Notification channel created",
            channel_id=str(channel.id),
            name=name,
            type=channel_type.value,
        )

        return channel

    async def update_channel(
        self,
        channel_id: UUID,
        name: str | None = None,
        config: dict[str, Any] | None = None,
        is_enabled: bool | None = None,
        severity_filter: list[str] | None = None,
        type_filter: list[str] | None = None,
    ) -> NotificationChannel | None:
        """Update a notification channel."""
        updates: dict[str, Any] = {}

        if name is not None:
            updates["name"] = name
        if config is not None:
            config_json = json.dumps(config)
            updates["config_encrypted"] = encrypt_value(config_json)
        if is_enabled is not None:
            updates["is_enabled"] = is_enabled
        if severity_filter is not None:
            updates["severity_filter"] = severity_filter
        if type_filter is not None:
            updates["type_filter"] = type_filter

        if not updates:
            return await self.channel_repo.get_by_id(channel_id)

        channel = await self.channel_repo.update(channel_id, **updates)

        if channel:
            logger.info(
                "Notification channel updated",
                channel_id=str(channel_id),
                updates=list(updates.keys()),
            )

        return channel

    async def delete_channel(self, channel_id: UUID) -> bool:
        """Delete a notification channel."""
        deleted = await self.channel_repo.delete(channel_id)
        if deleted:
            logger.info("Notification channel deleted", channel_id=str(channel_id))
        return deleted

    def get_decrypted_config(self, channel: NotificationChannel) -> dict[str, Any]:
        """Get decrypted config for a channel."""
        if not channel.config_encrypted:
            return {}
        decrypted = decrypt_value(channel.config_encrypted)
        return json.loads(decrypted)

    def get_masked_config(self, channel: NotificationChannel) -> dict[str, Any]:
        """Get config with sensitive fields masked."""
        config = self.get_decrypted_config(channel)
        masked: dict[str, Any] = {}

        for key, value in config.items():
            if key in SENSITIVE_FIELDS and isinstance(value, str):
                masked[key] = mask_sensitive(value)
            elif key == "headers" and isinstance(value, dict):
                # Mask header values (likely contain API keys)
                masked[key] = {
                    k: mask_sensitive(v) if isinstance(v, str) else v
                    for k, v in value.items()
                }
            else:
                masked[key] = value

        return masked

    async def get_matching_channels(
        self,
        severity: str,
        notification_type: str,
    ) -> list[NotificationChannel]:
        """Get enabled channels matching notification severity and type."""
        return await self.channel_repo.get_matching_channels(
            severity=severity,
            notification_type=notification_type,
        )

    async def create_delivery_record(
        self,
        notification_id: UUID,
        channel_id: UUID,
    ) -> NotificationDelivery:
        """Create a delivery record for a notification/channel pair."""
        return await self.delivery_repo.create(
            notification_id=notification_id,
            channel_id=channel_id,
            status=DeliveryStatus.PENDING.value,
        )

    async def get_deliveries_for_notification(
        self,
        notification_id: UUID,
    ) -> list[NotificationDelivery]:
        """Get all delivery records for a notification."""
        return await self.delivery_repo.get_for_notification(notification_id)

    async def get_deliveries_for_channel(
        self,
        channel_id: UUID,
        limit: int = 100,
    ) -> list[NotificationDelivery]:
        """Get recent delivery records for a channel."""
        return await self.delivery_repo.get_for_channel(channel_id, limit=limit)

    async def mark_delivery_sent(self, delivery_id: UUID) -> bool:
        """Mark a delivery as successfully sent."""
        return await self.delivery_repo.mark_sent(delivery_id)

    async def mark_delivery_failed(self, delivery_id: UUID, error: str) -> bool:
        """Mark a delivery as failed."""
        return await self.delivery_repo.mark_failed(delivery_id, error)
