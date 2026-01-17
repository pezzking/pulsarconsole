"""Celery tasks for notification delivery to external channels."""

import asyncio
from uuid import UUID

from celery import shared_task

from app.core.database import worker_session_factory
from app.core.logging import get_logger
from app.repositories.notification import NotificationRepository
from app.repositories.notification_channel import NotificationChannelRepository
from app.repositories.notification_delivery import NotificationDeliveryRepository
from app.services.notification_channel import NotificationChannelService
from app.services.notification_dispatcher import NotificationDispatcher

logger = get_logger(__name__)


def _run_async(coro):
    """Run async coroutine in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _deliver_notification_async(
    notification_id: str,
    channel_id: str,
    delivery_id: str,
) -> dict:
    """Async implementation of notification delivery."""
    async with worker_session_factory() as session:
        try:
            # Load entities
            notification_repo = NotificationRepository(session)
            channel_repo = NotificationChannelRepository(session)
            delivery_repo = NotificationDeliveryRepository(session)
            channel_service = NotificationChannelService(session)

            notification = await notification_repo.get_by_id(UUID(notification_id))
            channel = await channel_repo.get_by_id(UUID(channel_id))

            if not notification:
                logger.error("Notification not found", notification_id=notification_id)
                return {"success": False, "error": "Notification not found"}

            if not channel:
                logger.error("Channel not found", channel_id=channel_id)
                return {"success": False, "error": "Channel not found"}

            # Get decrypted config
            config = channel_service.get_decrypted_config(channel)

            # Dispatch
            dispatcher = NotificationDispatcher()
            result = await dispatcher.dispatch(channel, config, notification)

            # Update delivery record
            if result.success:
                await delivery_repo.mark_sent(UUID(delivery_id))
                logger.info(
                    "Notification delivered",
                    notification_id=notification_id,
                    channel=channel.name,
                    channel_type=channel.channel_type,
                    latency_ms=result.latency_ms,
                )
            else:
                await delivery_repo.mark_failed(
                    UUID(delivery_id),
                    result.error or "Unknown error",
                )
                logger.warning(
                    "Notification delivery failed",
                    notification_id=notification_id,
                    channel=channel.name,
                    channel_type=channel.channel_type,
                    error=result.error,
                )

            await session.commit()
            return {"success": result.success, "error": result.error}

        except Exception as e:
            logger.error(
                "Delivery task error",
                notification_id=notification_id,
                channel_id=channel_id,
                error=str(e),
            )
            await session.rollback()
            raise


@shared_task(
    bind=True,
    name="deliver_notification",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
)
def deliver_notification(
    self,
    notification_id: str,
    channel_id: str,
    delivery_id: str,
) -> dict:
    """
    Deliver a notification to an external channel.

    Args:
        notification_id: UUID of the notification
        channel_id: UUID of the channel
        delivery_id: UUID of the delivery record

    Returns:
        Result dict with success status
    """
    logger.info(
        "Delivering notification",
        notification_id=notification_id,
        channel_id=channel_id,
        attempt=self.request.retries + 1,
    )

    try:
        result = _run_async(
            _deliver_notification_async(
                notification_id,
                channel_id,
                delivery_id,
            )
        )
        return result
    except Exception as e:
        logger.error(
            "Notification delivery failed, will retry",
            notification_id=notification_id,
            channel_id=channel_id,
            error=str(e),
            attempt=self.request.retries + 1,
        )
        raise


async def _dispatch_to_channels_async(notification_id: str) -> int:
    """Find matching channels and create delivery tasks."""
    async with worker_session_factory() as session:
        try:
            notification_repo = NotificationRepository(session)
            channel_service = NotificationChannelService(session)

            notification = await notification_repo.get_by_id(UUID(notification_id))
            if not notification:
                logger.warning(
                    "Notification not found for dispatch",
                    notification_id=notification_id,
                )
                return 0

            # Get matching channels
            channels = await channel_service.get_matching_channels(
                severity=notification.severity,
                notification_type=notification.type,
            )

            if not channels:
                logger.debug(
                    "No matching channels for notification",
                    notification_id=notification_id,
                    severity=notification.severity,
                    type=notification.type,
                )
                return 0

            # Create delivery records and dispatch tasks
            count = 0
            for channel in channels:
                try:
                    delivery = await channel_service.create_delivery_record(
                        notification_id=notification.id,
                        channel_id=channel.id,
                    )
                    await session.flush()

                    # Dispatch Celery task
                    deliver_notification.delay(
                        str(notification.id),
                        str(channel.id),
                        str(delivery.id),
                    )
                    count += 1

                    logger.debug(
                        "Queued notification delivery",
                        notification_id=notification_id,
                        channel=channel.name,
                        delivery_id=str(delivery.id),
                    )
                except Exception as e:
                    logger.error(
                        "Failed to queue delivery for channel",
                        notification_id=notification_id,
                        channel=channel.name,
                        error=str(e),
                    )

            await session.commit()
            return count

        except Exception as e:
            logger.error(
                "Failed to dispatch notification to channels",
                notification_id=notification_id,
                error=str(e),
            )
            await session.rollback()
            return 0


@shared_task(name="dispatch_notification_to_channels")
def dispatch_notification_to_channels(notification_id: str) -> dict:
    """
    Dispatch a notification to all matching channels.

    This is called after a notification is created to queue delivery tasks.

    Args:
        notification_id: UUID of the notification to dispatch

    Returns:
        Result dict with count of channels queued
    """
    count = _run_async(_dispatch_to_channels_async(notification_id))
    if count > 0:
        logger.info(
            "Dispatched notification to channels",
            notification_id=notification_id,
            channels_queued=count,
        )
    return {"notification_id": notification_id, "channels_queued": count}
