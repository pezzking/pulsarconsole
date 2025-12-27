"""Alert checking tasks for generating notifications."""

import asyncio
from celery import shared_task

from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.services.environment import EnvironmentService
from app.services.notification import NotificationService
from app.models.notification import NotificationType, NotificationSeverity

logger = get_logger(__name__)


async def _check_consumer_disconnects() -> int:
    """Check for subscriptions with no consumers."""
    count = 0
    async with async_session_factory() as session:
        try:
            env_service = EnvironmentService(session)
            pulsar = await env_service.get_pulsar_client()
            notification_service = NotificationService(session, pulsar)

            # Get all tenants
            tenants = await pulsar.list_tenants()

            for tenant in tenants:
                namespaces = await pulsar.list_namespaces(tenant)
                for ns in namespaces:
                    ns_name = ns.split("/")[-1] if "/" in ns else ns
                    topics = await pulsar.list_topics(tenant, ns_name)

                    for topic_info in topics:
                        topic_name = topic_info.get("name", "")
                        if not topic_name:
                            continue

                        try:
                            subs = await pulsar.list_subscriptions(topic_name)
                            for sub in subs:
                                sub_name = sub.get("name", "")
                                consumer_count = sub.get("consumer_count", 0)
                                backlog = sub.get("msg_backlog", 0)
                                is_durable = sub.get("is_durable", True)

                                # Only alert for durable subscriptions with no consumers
                                if is_durable and consumer_count == 0:
                                    # Determine severity based on backlog
                                    if backlog > 10000:
                                        severity = NotificationSeverity.CRITICAL
                                    elif backlog > 1000:
                                        severity = NotificationSeverity.WARNING
                                    else:
                                        severity = NotificationSeverity.INFO

                                    notification = await notification_service.create_notification(
                                        type=NotificationType.CONSUMER_DISCONNECT,
                                        severity=severity,
                                        title=f"No consumers on {sub_name}",
                                        message=f"Subscription '{sub_name}' on topic '{topic_name}' "
                                                f"has no active consumers. Backlog: {backlog:,} messages.",
                                        resource_type="subscription",
                                        resource_id=f"{topic_name}/{sub_name}",
                                        extra_data={
                                            "topic": topic_name,
                                            "subscription": sub_name,
                                            "backlog": backlog,
                                        },
                                    )
                                    if notification:
                                        count += 1

                        except Exception as e:
                            logger.warning(
                                "Failed to check subscriptions for topic",
                                topic=topic_name,
                                error=str(e),
                            )

            await session.commit()
            await pulsar.close()

        except Exception as e:
            logger.error("Failed to check consumer disconnects", error=str(e))
            await session.rollback()

    return count


async def _check_broker_health() -> int:
    """Check broker health status."""
    count = 0
    async with async_session_factory() as session:
        try:
            env_service = EnvironmentService(session)
            pulsar = await env_service.get_pulsar_client()
            notification_service = NotificationService(session, pulsar)

            brokers = await pulsar.list_brokers()

            for broker in brokers:
                broker_url = broker.get("url", "unknown")

                # Check if broker is healthy
                try:
                    is_healthy = await pulsar.check_broker_health(broker_url)
                    if not is_healthy:
                        notification = await notification_service.create_notification(
                            type=NotificationType.BROKER_HEALTH,
                            severity=NotificationSeverity.CRITICAL,
                            title=f"Broker unhealthy: {broker_url}",
                            message=f"Broker '{broker_url}' is not responding or in unhealthy state.",
                            resource_type="broker",
                            resource_id=broker_url,
                            extra_data={"broker_url": broker_url},
                        )
                        if notification:
                            count += 1
                except Exception:
                    # Broker unreachable
                    notification = await notification_service.create_notification(
                        type=NotificationType.BROKER_HEALTH,
                        severity=NotificationSeverity.CRITICAL,
                        title=f"Broker unreachable: {broker_url}",
                        message=f"Broker '{broker_url}' is not reachable.",
                        resource_type="broker",
                        resource_id=broker_url,
                        extra_data={"broker_url": broker_url},
                    )
                    if notification:
                        count += 1

            await session.commit()
            await pulsar.close()

        except Exception as e:
            logger.error("Failed to check broker health", error=str(e))
            await session.rollback()

    return count


async def _check_storage_warnings() -> int:
    """Check for topics with high storage usage."""
    count = 0
    async with async_session_factory() as session:
        try:
            env_service = EnvironmentService(session)
            pulsar = await env_service.get_pulsar_client()
            notification_service = NotificationService(session, pulsar)

            # Get all tenants
            tenants = await pulsar.list_tenants()

            for tenant in tenants:
                namespaces = await pulsar.list_namespaces(tenant)
                for ns in namespaces:
                    ns_name = ns.split("/")[-1] if "/" in ns else ns
                    topics = await pulsar.list_topics(tenant, ns_name)

                    for topic_info in topics:
                        topic_name = topic_info.get("name", "")
                        storage_bytes = topic_info.get("storage_size", 0)
                        storage_mb = storage_bytes / (1024 * 1024)

                        # Check storage thresholds
                        if storage_mb >= 500:
                            severity = NotificationSeverity.CRITICAL
                        elif storage_mb >= 100:
                            severity = NotificationSeverity.WARNING
                        else:
                            continue

                        notification = await notification_service.create_notification(
                            type=NotificationType.STORAGE_WARNING,
                            severity=severity,
                            title=f"High storage: {topic_name.split('/')[-1]}",
                            message=f"Topic '{topic_name}' is using {storage_mb:.1f} MB of storage.",
                            resource_type="topic",
                            resource_id=topic_name,
                            extra_data={
                                "topic": topic_name,
                                "storage_mb": round(storage_mb, 2),
                                "storage_bytes": storage_bytes,
                            },
                        )
                        if notification:
                            count += 1

            await session.commit()
            await pulsar.close()

        except Exception as e:
            logger.error("Failed to check storage warnings", error=str(e))
            await session.rollback()

    return count


@shared_task(name="check_alerts")
def check_alerts() -> dict:
    """Run all alert checks."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        consumer_count = loop.run_until_complete(_check_consumer_disconnects())
        broker_count = loop.run_until_complete(_check_broker_health())
        storage_count = loop.run_until_complete(_check_storage_warnings())

        total = consumer_count + broker_count + storage_count

        logger.info(
            "Alert check completed",
            consumer_disconnects=consumer_count,
            broker_health=broker_count,
            storage_warnings=storage_count,
            total=total,
        )

        return {
            "consumer_disconnects": consumer_count,
            "broker_health": broker_count,
            "storage_warnings": storage_count,
            "total": total,
        }

    finally:
        loop.close()


@shared_task(name="cleanup_old_notifications")
def cleanup_old_notifications(days: int = 30) -> int:
    """Clean up old notifications."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        async def _cleanup():
            async with async_session_factory() as session:
                notification_service = NotificationService(session)
                count = await notification_service.cleanup_old_notifications(days)
                await session.commit()
                return count

        count = loop.run_until_complete(_cleanup())
        logger.info("Cleaned up old notifications", count=count, days=days)
        return count

    finally:
        loop.close()
