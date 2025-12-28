"""Environment configuration schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema


class EnvironmentBase(BaseSchema):
    """Base environment schema."""

    name: str = Field(..., min_length=1, max_length=64, description="Environment name")
    admin_url: str = Field(..., description="Pulsar admin URL")


class EnvironmentCreate(EnvironmentBase):
    """Schema for creating an environment."""

    auth_mode: Literal["none", "token", "oidc", "tls"] = Field(
        default="none", description="Authentication mode"
    )
    oidc_mode: Literal["none", "console_only", "passthrough"] = Field(
        default="none", description="OIDC operation mode"
    )
    token: str | None = Field(default=None, description="Authentication token")
    superuser_token: str | None = Field(
        default=None,
        description="Superuser token for auth management (if different from regular token)",
    )
    ca_bundle_ref: str | None = Field(
        default=None, description="CA bundle reference for TLS"
    )
    rbac_enabled: bool = Field(
        default=False, description="Enable RBAC for this environment"
    )
    rbac_sync_mode: Literal["console_only", "sync_to_pulsar", "read_from_pulsar"] = Field(
        default="console_only", description="RBAC synchronization mode"
    )
    validate_connectivity: bool = Field(
        default=True, description="Test connectivity before saving"
    )

    @field_validator("token")
    @classmethod
    def validate_token(cls, v: str | None, info) -> str | None:
        """Validate token is provided when auth_mode is token."""
        if info.data.get("auth_mode") == "token" and not v:
            raise ValueError("Token is required when auth_mode is 'token'")
        return v


class EnvironmentUpdate(BaseSchema):
    """Schema for updating an environment."""

    admin_url: str | None = Field(default=None, description="Pulsar admin URL")
    auth_mode: Literal["none", "token", "oidc", "tls"] | None = Field(
        default=None, description="Authentication mode"
    )
    oidc_mode: Literal["none", "console_only", "passthrough"] | None = Field(
        default=None, description="OIDC operation mode"
    )
    token: str | None = Field(default=None, description="Authentication token")
    superuser_token: str | None = Field(
        default=None,
        description="Superuser token for auth management (if different from regular token)",
    )
    ca_bundle_ref: str | None = Field(
        default=None, description="CA bundle reference for TLS"
    )
    rbac_enabled: bool | None = Field(
        default=None, description="Enable RBAC for this environment"
    )
    rbac_sync_mode: Literal["console_only", "sync_to_pulsar", "read_from_pulsar"] | None = Field(
        default=None, description="RBAC synchronization mode"
    )
    validate_connectivity: bool = Field(
        default=True, description="Test connectivity before saving"
    )


class EnvironmentResponse(EnvironmentBase):
    """Environment response schema."""

    id: UUID
    auth_mode: str
    oidc_mode: str = Field(default="none", description="OIDC operation mode")
    has_token: bool = Field(description="Whether token is configured")
    has_superuser_token: bool = Field(
        default=False, description="Whether superuser token is configured"
    )
    ca_bundle_ref: str | None = None
    is_active: bool = Field(default=False, description="Whether this is the active environment")
    rbac_enabled: bool = Field(default=False, description="Whether RBAC is enabled")
    rbac_sync_mode: str = Field(
        default="console_only", description="RBAC synchronization mode"
    )
    created_at: datetime
    updated_at: datetime | None = None


class EnvironmentListResponse(BaseSchema):
    """Response schema for listing environments."""

    environments: list[EnvironmentResponse]
    total: int


class EnvironmentTestRequest(BaseSchema):
    """Schema for testing environment connectivity."""

    admin_url: str = Field(..., description="Pulsar admin URL to test")
    token: str | None = Field(default=None, description="Authentication token")


class EnvironmentTestResponse(BaseSchema):
    """Schema for environment connectivity test result."""

    success: bool
    message: str
    latency_ms: float | None = None
