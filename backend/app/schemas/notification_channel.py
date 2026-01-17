"""Notification channel schemas."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

# =============================================================================
# Channel Configuration Schemas
# =============================================================================


class EmailConfig(BaseModel):
    """Email channel configuration."""

    smtp_host: str = Field(..., description="SMTP server hostname")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_user: str | None = Field(default=None, description="SMTP username")
    smtp_password: str | None = Field(default=None, description="SMTP password")
    smtp_use_tls: bool = Field(default=True, description="Use TLS/STARTTLS for SMTP")
    from_address: str = Field(..., description="From email address")
    from_name: str = Field(default="Pulsar Console", description="From display name")
    recipients: list[str] = Field(
        ...,
        min_length=1,
        description="List of recipient email addresses",
    )


class SlackConfig(BaseModel):
    """Slack channel configuration."""

    webhook_url: str = Field(..., description="Slack incoming webhook URL")
    channel: str | None = Field(
        default=None,
        description="Override channel (optional, uses webhook default)",
    )
    username: str = Field(default="Pulsar Console", description="Bot username")
    icon_emoji: str = Field(default=":bell:", description="Bot icon emoji")


class WebhookConfig(BaseModel):
    """Generic webhook configuration."""

    url: str = Field(..., description="Webhook URL")
    method: Literal["POST", "PUT"] = Field(default="POST", description="HTTP method")
    headers: dict[str, str] | None = Field(
        default=None,
        description="Custom HTTP headers",
    )
    include_metadata: bool = Field(
        default=True,
        description="Include full notification metadata in payload",
    )
    timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Request timeout in seconds",
    )


# =============================================================================
# Channel CRUD Schemas
# =============================================================================


class NotificationChannelBase(BaseModel):
    """Base notification channel schema."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique channel name",
    )
    is_enabled: bool = Field(default=True, description="Whether channel is enabled")
    severity_filter: list[str] | None = Field(
        default=None,
        description="Filter by severity (info, warning, critical). Null for all.",
    )
    type_filter: list[str] | None = Field(
        default=None,
        description="Filter by notification type. Null for all.",
    )


class NotificationChannelCreateEmail(NotificationChannelBase):
    """Create email channel request."""

    channel_type: Literal["email"] = "email"
    config: EmailConfig


class NotificationChannelCreateSlack(NotificationChannelBase):
    """Create Slack channel request."""

    channel_type: Literal["slack"] = "slack"
    config: SlackConfig


class NotificationChannelCreateWebhook(NotificationChannelBase):
    """Create webhook channel request."""

    channel_type: Literal["webhook"] = "webhook"
    config: WebhookConfig


# Union type for creating any channel
NotificationChannelCreate = (
    NotificationChannelCreateEmail
    | NotificationChannelCreateSlack
    | NotificationChannelCreateWebhook
)


class NotificationChannelUpdate(BaseModel):
    """Update notification channel request."""

    name: str | None = Field(default=None, max_length=255)
    is_enabled: bool | None = None
    severity_filter: list[str] | None = None
    type_filter: list[str] | None = None
    config: EmailConfig | SlackConfig | WebhookConfig | None = None


class NotificationChannelResponse(BaseModel):
    """Response schema for notification channel."""

    id: UUID
    name: str
    channel_type: str
    is_enabled: bool
    severity_filter: list[str] | None = None
    type_filter: list[str] | None = None
    config: dict[str, Any]  # Sensitive fields are masked
    created_by_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NotificationChannelListResponse(BaseModel):
    """List of notification channels response."""

    channels: list[NotificationChannelResponse]
    total: int


# =============================================================================
# Delivery Status Schemas
# =============================================================================


class NotificationDeliveryResponse(BaseModel):
    """Response for a notification delivery record."""

    id: UUID
    notification_id: UUID
    channel_id: UUID
    channel_name: str
    channel_type: str
    status: str
    attempts: int
    last_attempt_at: datetime | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationDeliveryListResponse(BaseModel):
    """List of delivery records response."""

    deliveries: list[NotificationDeliveryResponse]
    total: int


# =============================================================================
# Test Channel Schema
# =============================================================================


class TestChannelResponse(BaseModel):
    """Response from testing a notification channel."""

    success: bool
    message: str
    latency_ms: float | None = None
