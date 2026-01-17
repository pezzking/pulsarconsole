"""API routes for notification channel management."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentSuperuser, DbSession
from app.models.notification import Notification
from app.models.notification_channel import ChannelType
from app.schemas import SuccessResponse
from app.schemas.notification_channel import (
    NotificationChannelCreateEmail,
    NotificationChannelCreateSlack,
    NotificationChannelCreateWebhook,
    NotificationChannelListResponse,
    NotificationChannelResponse,
    NotificationChannelUpdate,
    NotificationDeliveryListResponse,
    NotificationDeliveryResponse,
    TestChannelResponse,
)
from app.services.notification_channel import NotificationChannelService
from app.services.notification_dispatcher import NotificationDispatcher

router = APIRouter(prefix="/notification-channels", tags=["Notification Channels"])


def _channel_to_response(
    channel,
    service: NotificationChannelService,
) -> NotificationChannelResponse:
    """Convert channel model to response."""
    return NotificationChannelResponse(
        id=channel.id,
        name=channel.name,
        channel_type=channel.channel_type,
        is_enabled=channel.is_enabled,
        severity_filter=channel.severity_filter,
        type_filter=channel.type_filter,
        config=service.get_masked_config(channel),
        created_by_id=channel.created_by_id,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
    )


@router.get("", response_model=NotificationChannelListResponse)
async def list_channels(
    _user: CurrentSuperuser,
    db: DbSession,
) -> NotificationChannelListResponse:
    """List all notification channels."""
    service = NotificationChannelService(db)
    channels = await service.list_channels()
    return NotificationChannelListResponse(
        channels=[_channel_to_response(c, service) for c in channels],
        total=len(channels),
    )


@router.get("/{channel_id}", response_model=NotificationChannelResponse)
async def get_channel(
    channel_id: UUID,
    _user: CurrentSuperuser,
    db: DbSession,
) -> NotificationChannelResponse:
    """Get a notification channel by ID."""
    service = NotificationChannelService(db)
    channel = await service.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return _channel_to_response(channel, service)


@router.post("", response_model=NotificationChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(
    data: NotificationChannelCreateEmail | NotificationChannelCreateSlack | NotificationChannelCreateWebhook,
    user: CurrentSuperuser,
    db: DbSession,
) -> NotificationChannelResponse:
    """Create a notification channel."""
    service = NotificationChannelService(db)

    # Check for duplicate name
    existing = await service.get_channel_by_name(data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Channel with name '{data.name}' already exists",
        )

    channel = await service.create_channel(
        name=data.name,
        channel_type=ChannelType(data.channel_type),
        config=data.config.model_dump(),
        is_enabled=data.is_enabled,
        severity_filter=data.severity_filter,
        type_filter=data.type_filter,
        created_by_id=user.id,
    )
    await db.commit()

    return _channel_to_response(channel, service)


@router.put("/{channel_id}", response_model=NotificationChannelResponse)
async def update_channel(
    channel_id: UUID,
    data: NotificationChannelUpdate,
    _user: CurrentSuperuser,
    db: DbSession,
) -> NotificationChannelResponse:
    """Update a notification channel."""
    service = NotificationChannelService(db)

    channel = await service.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Check name uniqueness if changing
    if data.name and data.name != channel.name:
        existing = await service.get_channel_by_name(data.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Channel with name '{data.name}' already exists",
            )

    config_dict = data.config.model_dump() if data.config else None

    updated = await service.update_channel(
        channel_id=channel_id,
        name=data.name,
        config=config_dict,
        is_enabled=data.is_enabled,
        severity_filter=data.severity_filter,
        type_filter=data.type_filter,
    )
    await db.commit()

    return _channel_to_response(updated, service)


@router.delete("/{channel_id}", response_model=SuccessResponse)
async def delete_channel(
    channel_id: UUID,
    _user: CurrentSuperuser,
    db: DbSession,
) -> SuccessResponse:
    """Delete a notification channel."""
    service = NotificationChannelService(db)
    deleted = await service.delete_channel(channel_id)
    await db.commit()

    if not deleted:
        raise HTTPException(status_code=404, detail="Channel not found")

    return SuccessResponse(message="Channel deleted")


@router.post("/{channel_id}/test", response_model=TestChannelResponse)
async def test_channel(
    channel_id: UUID,
    _user: CurrentSuperuser,
    db: DbSession,
) -> TestChannelResponse:
    """Test a notification channel by sending a test notification."""
    service = NotificationChannelService(db)
    channel = await service.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Create a test notification object (not persisted)
    test_notification = Notification(
        id=uuid4(),
        type="info",
        severity="info",
        title="Test Notification",
        message="This is a test notification from Pulsar Console to verify channel configuration.",
        resource_type="test",
        resource_id="test-channel",
        created_at=datetime.now(UTC),
    )

    config = service.get_decrypted_config(channel)
    dispatcher = NotificationDispatcher()
    result = await dispatcher.dispatch(channel, config, test_notification)

    return TestChannelResponse(
        success=result.success,
        message=(
            "Test notification sent successfully"
            if result.success
            else f"Failed: {result.error}"
        ),
        latency_ms=result.latency_ms,
    )


@router.get("/{channel_id}/deliveries", response_model=NotificationDeliveryListResponse)
async def list_channel_deliveries(
    channel_id: UUID,
    _user: CurrentSuperuser,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
) -> NotificationDeliveryListResponse:
    """List recent deliveries for a channel."""
    service = NotificationChannelService(db)

    channel = await service.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    deliveries = await service.get_deliveries_for_channel(channel_id, limit=limit)

    return NotificationDeliveryListResponse(
        deliveries=[
            NotificationDeliveryResponse(
                id=d.id,
                notification_id=d.notification_id,
                channel_id=d.channel_id,
                channel_name=channel.name,
                channel_type=channel.channel_type,
                status=d.status,
                attempts=d.attempts,
                last_attempt_at=d.last_attempt_at,
                error_message=d.error_message,
                created_at=d.created_at,
            )
            for d in deliveries
        ],
        total=len(deliveries),
    )
