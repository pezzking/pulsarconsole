"""Pulsar Authentication and Authorization API routes.

These endpoints are for managing Pulsar broker authentication/authorization,
including namespace and topic permissions, and broker configuration.
"""

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.deps import (
    AuditSvc,
    CurrentSuperuser,
    PulsarAuthSvc,
    RequestInfo,
)
from app.models.audit import ActionType, ResourceType
from app.schemas import SuccessResponse


router = APIRouter(prefix="/pulsar-auth", tags=["Pulsar Authentication"])


# =============================================================================
# Request/Response Schemas
# =============================================================================


class AuthStatusResponse(BaseModel):
    """Response for auth status endpoint."""

    authentication_enabled: bool = Field(description="Whether authentication is enabled")
    authorization_enabled: bool = Field(description="Whether authorization is enabled")
    authentication_providers: list[str] = Field(
        default_factory=list, description="Configured auth providers"
    )
    super_user_roles: list[str] = Field(
        default_factory=list, description="Configured superuser roles"
    )
    authorization_provider: str | None = Field(
        default=None, description="Authorization provider class"
    )
    raw_config: dict[str, Any] = Field(
        default_factory=dict, description="Raw auth configuration"
    )


class AuthValidationResponse(BaseModel):
    """Response for pre-flight validation."""

    can_proceed: bool = Field(description="Whether it's safe to proceed")
    warnings: list[str] = Field(default_factory=list, description="Warning messages")
    errors: list[str] = Field(default_factory=list, description="Error messages")
    current_config: dict[str, Any] = Field(
        default_factory=dict, description="Current auth configuration"
    )


class PermissionInfo(BaseModel):
    """Permission information for a role."""

    role: str = Field(description="Role name")
    actions: list[str] = Field(description="Granted actions")


class PermissionsResponse(BaseModel):
    """Response for permissions list."""

    permissions: list[PermissionInfo] = Field(default_factory=list)
    total: int = Field(default=0)


class GrantPermissionRequest(BaseModel):
    """Request to grant permissions."""

    role: str = Field(description="Role to grant permissions to")
    actions: list[str] = Field(
        description="Actions to grant (produce, consume, functions, etc.)"
    )


class BrokerConfigResponse(BaseModel):
    """Response for broker configuration."""

    config_values: dict[str, str] = Field(
        default_factory=dict, description="Current dynamic config values"
    )
    available_configs: list[str] = Field(
        default_factory=list, description="Available config names"
    )


class UpdateConfigRequest(BaseModel):
    """Request to update broker configuration."""

    value: str = Field(description="Configuration value")


class PermissionsSummaryResponse(BaseModel):
    """Response for permissions summary."""

    namespace_permissions: list[PermissionInfo] = Field(default_factory=list)
    topic_permissions: dict[str, list[PermissionInfo]] = Field(default_factory=dict)


# =============================================================================
# Auth Status Endpoints
# =============================================================================


@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status(
    service: PulsarAuthSvc,
    _user: CurrentSuperuser,
) -> AuthStatusResponse:
    """Get current authentication/authorization status from broker.

    Requires superuser privileges.
    """
    status = await service.get_auth_status()

    return AuthStatusResponse(
        authentication_enabled=status.get("authenticationEnabled", False),
        authorization_enabled=status.get("authorizationEnabled", False),
        authentication_providers=status.get("authenticationProviders", []),
        super_user_roles=status.get("superUserRoles", []),
        authorization_provider=status.get("authorizationProvider"),
        raw_config=status,
    )


@router.get("/validate", response_model=AuthValidationResponse)
async def validate_auth_setup(
    service: PulsarAuthSvc,
    _user: CurrentSuperuser,
) -> AuthValidationResponse:
    """Validate that authentication can be safely enabled.

    Performs pre-flight checks:
    - Verify Console has valid superuser access
    - Check if superUserRoles are configured
    - Check for existing tenant admins

    Requires superuser privileges.
    """
    result = await service.validate_auth_can_be_enabled()

    return AuthValidationResponse(
        can_proceed=result.can_proceed,
        warnings=result.warnings,
        errors=result.errors,
        current_config=result.current_config,
    )


# =============================================================================
# Namespace Permission Endpoints
# =============================================================================


@router.get(
    "/namespaces/{tenant}/{namespace}/permissions",
    response_model=PermissionsResponse,
)
async def get_namespace_permissions(
    tenant: str,
    namespace: str,
    service: PulsarAuthSvc,
    _user: CurrentSuperuser,
) -> PermissionsResponse:
    """Get all permissions for a namespace.

    Requires superuser privileges.
    """
    perms = await service.get_namespace_permissions(tenant, namespace)
    return PermissionsResponse(
        permissions=[
            PermissionInfo(role=p.role, actions=p.actions) for p in perms
        ],
        total=len(perms),
    )


@router.post(
    "/namespaces/{tenant}/{namespace}/permissions",
    response_model=SuccessResponse,
)
async def grant_namespace_permission(
    tenant: str,
    namespace: str,
    data: GrantPermissionRequest,
    service: PulsarAuthSvc,
    audit: AuditSvc,
    request_info: RequestInfo,
    _user: CurrentSuperuser,
) -> SuccessResponse:
    """Grant permissions to a role on a namespace.

    Valid actions: produce, consume, functions, packages, sinks, sources

    Requires superuser privileges.
    """
    await service.grant_namespace_permission(
        tenant=tenant,
        namespace=namespace,
        role=data.role,
        actions=data.actions,
    )

    # Audit log
    await audit.log_event(
        action=ActionType.UPDATE,
        resource_type=ResourceType.NAMESPACE,
        resource_id=f"{tenant}/{namespace}",
        details={
            "operation": "grant_permission",
            "role": data.role,
            "actions": data.actions,
        },
        **request_info,
    )

    return SuccessResponse(
        message=f"Granted {data.actions} to role '{data.role}' on {tenant}/{namespace}"
    )


@router.delete(
    "/namespaces/{tenant}/{namespace}/permissions/{role}",
    response_model=SuccessResponse,
)
async def revoke_namespace_permission(
    tenant: str,
    namespace: str,
    role: str,
    service: PulsarAuthSvc,
    audit: AuditSvc,
    request_info: RequestInfo,
    _user: CurrentSuperuser,
) -> SuccessResponse:
    """Revoke all permissions from a role on a namespace.

    Requires superuser privileges.
    """
    await service.revoke_namespace_permission(tenant, namespace, role)

    # Audit log
    await audit.log_event(
        action=ActionType.DELETE,
        resource_type=ResourceType.NAMESPACE,
        resource_id=f"{tenant}/{namespace}",
        details={
            "operation": "revoke_permission",
            "role": role,
        },
        **request_info,
    )

    return SuccessResponse(
        message=f"Revoked all permissions from role '{role}' on {tenant}/{namespace}"
    )


# =============================================================================
# Topic Permission Endpoints
# =============================================================================


@router.get(
    "/topics/{tenant}/{namespace}/{topic}/permissions",
    response_model=PermissionsResponse,
)
async def get_topic_permissions(
    tenant: str,
    namespace: str,
    topic: str,
    service: PulsarAuthSvc,
    _user: CurrentSuperuser,
    persistent: bool = Query(default=True, description="Persistent topic"),
) -> PermissionsResponse:
    """Get all permissions for a topic.

    Requires superuser privileges.
    """
    perms = await service.get_topic_permissions(
        tenant, namespace, topic, persistent
    )
    return PermissionsResponse(
        permissions=[
            PermissionInfo(role=p.role, actions=p.actions) for p in perms
        ],
        total=len(perms),
    )


@router.post(
    "/topics/{tenant}/{namespace}/{topic}/permissions",
    response_model=SuccessResponse,
)
async def grant_topic_permission(
    tenant: str,
    namespace: str,
    topic: str,
    data: GrantPermissionRequest,
    service: PulsarAuthSvc,
    audit: AuditSvc,
    request_info: RequestInfo,
    _user: CurrentSuperuser,
    persistent: bool = Query(default=True, description="Persistent topic"),
) -> SuccessResponse:
    """Grant permissions to a role on a topic.

    Valid actions: produce, consume

    Requires superuser privileges.
    """
    await service.grant_topic_permission(
        tenant=tenant,
        namespace=namespace,
        topic=topic,
        role=data.role,
        actions=data.actions,
        persistent=persistent,
    )

    # Audit log
    topic_type = "persistent" if persistent else "non-persistent"
    await audit.log_event(
        action=ActionType.UPDATE,
        resource_type=ResourceType.TOPIC,
        resource_id=f"{topic_type}://{tenant}/{namespace}/{topic}",
        details={
            "operation": "grant_permission",
            "role": data.role,
            "actions": data.actions,
        },
        **request_info,
    )

    return SuccessResponse(
        message=f"Granted {data.actions} to role '{data.role}' on topic {topic}"
    )


@router.delete(
    "/topics/{tenant}/{namespace}/{topic}/permissions/{role}",
    response_model=SuccessResponse,
)
async def revoke_topic_permission(
    tenant: str,
    namespace: str,
    topic: str,
    role: str,
    service: PulsarAuthSvc,
    audit: AuditSvc,
    request_info: RequestInfo,
    _user: CurrentSuperuser,
    persistent: bool = Query(default=True, description="Persistent topic"),
) -> SuccessResponse:
    """Revoke all permissions from a role on a topic.

    Requires superuser privileges.
    """
    await service.revoke_topic_permission(
        tenant, namespace, topic, role, persistent
    )

    # Audit log
    topic_type = "persistent" if persistent else "non-persistent"
    await audit.log_event(
        action=ActionType.DELETE,
        resource_type=ResourceType.TOPIC,
        resource_id=f"{topic_type}://{tenant}/{namespace}/{topic}",
        details={
            "operation": "revoke_permission",
            "role": role,
        },
        **request_info,
    )

    return SuccessResponse(
        message=f"Revoked all permissions from role '{role}' on topic {topic}"
    )


# =============================================================================
# Broker Configuration Endpoints
# =============================================================================


@router.get("/broker/config", response_model=BrokerConfigResponse)
async def get_broker_config(
    service: PulsarAuthSvc,
    _user: CurrentSuperuser,
) -> BrokerConfigResponse:
    """Get all dynamic broker configuration values.

    Requires superuser privileges.
    """
    config_values = await service.get_all_dynamic_config()
    available_configs = await service.get_dynamic_config_names()

    return BrokerConfigResponse(
        config_values=config_values,
        available_configs=available_configs,
    )


@router.post("/broker/config/{config_name}", response_model=SuccessResponse)
async def update_broker_config(
    config_name: str,
    data: UpdateConfigRequest,
    service: PulsarAuthSvc,
    audit: AuditSvc,
    request_info: RequestInfo,
    _user: CurrentSuperuser,
) -> SuccessResponse:
    """Update a dynamic broker configuration.

    Warning: Some config changes require broker restart to take effect.

    Requires superuser privileges.
    """
    await service.update_dynamic_config(config_name, data.value)

    # Audit log
    await audit.log_event(
        action=ActionType.UPDATE,
        resource_type=ResourceType.BROKER,
        resource_id=f"config/{config_name}",
        details={
            "config_name": config_name,
            "new_value": data.value,
        },
        **request_info,
    )

    return SuccessResponse(
        message=f"Updated broker config '{config_name}' to '{data.value}'"
    )


@router.delete("/broker/config/{config_name}", response_model=SuccessResponse)
async def delete_broker_config(
    config_name: str,
    service: PulsarAuthSvc,
    audit: AuditSvc,
    request_info: RequestInfo,
    _user: CurrentSuperuser,
) -> SuccessResponse:
    """Delete/reset a dynamic broker configuration to default.

    Requires superuser privileges.
    """
    await service.delete_dynamic_config(config_name)

    # Audit log
    await audit.log_event(
        action=ActionType.DELETE,
        resource_type=ResourceType.BROKER,
        resource_id=f"config/{config_name}",
        details={
            "config_name": config_name,
            "operation": "reset_to_default",
        },
        **request_info,
    )

    return SuccessResponse(message=f"Reset broker config '{config_name}' to default")


# =============================================================================
# Summary Endpoints
# =============================================================================


@router.get(
    "/namespaces/{tenant}/{namespace}/permissions/summary",
    response_model=PermissionsSummaryResponse,
)
async def get_permissions_summary(
    tenant: str,
    namespace: str,
    service: PulsarAuthSvc,
    _user: CurrentSuperuser,
) -> PermissionsSummaryResponse:
    """Get a summary of all permissions for a namespace and its topics.

    Requires superuser privileges.
    """
    summary = await service.get_all_permissions_summary(tenant, namespace)

    return PermissionsSummaryResponse(
        namespace_permissions=[
            PermissionInfo(**p) for p in summary["namespace_permissions"]
        ],
        topic_permissions={
            topic: [PermissionInfo(**p) for p in perms]
            for topic, perms in summary["topic_permissions"].items()
        },
    )


# =============================================================================
# RBAC Sync Endpoints
# =============================================================================


class SyncChangeInfo(BaseModel):
    """Information about a single sync change."""

    action: str = Field(description="add, remove, or update")
    resource_type: str = Field(description="namespace or topic")
    resource_id: str = Field(description="Resource identifier")
    role: str = Field(description="Role name")
    permissions: list[str] = Field(description="Permissions involved")
    source: str = Field(description="console or pulsar")


class SyncPreviewResponse(BaseModel):
    """Response for sync preview."""

    direction: str = Field(description="Sync direction")
    changes: list[SyncChangeInfo] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    can_proceed: bool = Field(description="Whether sync can proceed")
    has_changes: bool = Field(description="Whether there are changes to apply")


class SyncDiffResponse(BaseModel):
    """Response for permission diff."""

    only_in_console: dict[str, list[str]] = Field(default_factory=dict)
    only_in_pulsar: dict[str, list[str]] = Field(default_factory=dict)
    different: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    same: dict[str, list[str]] = Field(default_factory=dict)
    total_console: int = Field(default=0)
    total_pulsar: int = Field(default=0)


class SyncResultResponse(BaseModel):
    """Response for sync operation."""

    success: bool = Field(description="Whether sync was successful")
    changes_applied: int = Field(default=0)
    changes_failed: int = Field(default=0)
    details: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class SyncRequest(BaseModel):
    """Request for sync operation."""

    direction: str | None = Field(
        default=None,
        description="Sync direction: console_to_pulsar or pulsar_to_console",
    )
    dry_run: bool = Field(default=True, description="Preview only, don't apply changes")


@router.get(
    "/rbac-sync/namespaces/{tenant}/{namespace}/diff",
    response_model=SyncDiffResponse,
)
async def get_rbac_diff(
    tenant: str,
    namespace: str,
    service: PulsarAuthSvc,
    db: "DbSession",
    _user: CurrentSuperuser,
) -> SyncDiffResponse:
    """Get the difference between Console and Pulsar permissions.

    Shows which permissions exist only in Console, only in Pulsar,
    are different, or are the same.

    Requires superuser privileges.
    """
    from app.services.rbac_sync import RbacSyncService
    from app.repositories.environment import EnvironmentRepository

    env_repo = EnvironmentRepository(db)
    environment = await env_repo.get_active()

    if not environment:
        return SyncDiffResponse()

    sync_service = RbacSyncService(db, service, environment)
    diff = await sync_service.get_diff(tenant, namespace)

    return SyncDiffResponse(**diff)


@router.get(
    "/rbac-sync/namespaces/{tenant}/{namespace}/preview",
    response_model=SyncPreviewResponse,
)
async def preview_rbac_sync(
    tenant: str,
    namespace: str,
    service: PulsarAuthSvc,
    db: "DbSession",
    _user: CurrentSuperuser,
    direction: str | None = Query(
        default=None,
        description="Sync direction: console_to_pulsar or pulsar_to_console",
    ),
) -> SyncPreviewResponse:
    """Preview what changes would be made during RBAC sync.

    Does not apply any changes, only shows what would happen.

    Requires superuser privileges.
    """
    from app.services.rbac_sync import RbacSyncService, SyncDirection
    from app.repositories.environment import EnvironmentRepository

    env_repo = EnvironmentRepository(db)
    environment = await env_repo.get_active()

    if not environment:
        return SyncPreviewResponse(
            direction="none",
            errors=["No active environment"],
            can_proceed=False,
            has_changes=False,
        )

    sync_service = RbacSyncService(db, service, environment)

    sync_direction = None
    if direction:
        sync_direction = SyncDirection(direction)

    preview = await sync_service.preview_sync(tenant, namespace, sync_direction)

    return SyncPreviewResponse(
        direction=preview.direction.value,
        changes=[
            SyncChangeInfo(
                action=c.action,
                resource_type=c.resource_type,
                resource_id=c.resource_id,
                role=c.role,
                permissions=c.permissions,
                source=c.source,
            )
            for c in preview.changes
        ],
        warnings=preview.warnings,
        errors=preview.errors,
        can_proceed=preview.can_proceed,
        has_changes=preview.has_changes,
    )


@router.post(
    "/rbac-sync/namespaces/{tenant}/{namespace}",
    response_model=SyncResultResponse,
)
async def sync_rbac(
    tenant: str,
    namespace: str,
    data: SyncRequest,
    service: PulsarAuthSvc,
    db: "DbSession",
    audit: AuditSvc,
    request_info: RequestInfo,
    _user: CurrentSuperuser,
) -> SyncResultResponse:
    """Synchronize RBAC between Console and Pulsar for a namespace.

    Use dry_run=true to preview changes without applying them.

    Requires superuser privileges.
    """
    from app.services.rbac_sync import RbacSyncService, SyncDirection
    from app.repositories.environment import EnvironmentRepository

    env_repo = EnvironmentRepository(db)
    environment = await env_repo.get_active()

    if not environment:
        return SyncResultResponse(
            success=False,
            errors=["No active environment"],
        )

    sync_service = RbacSyncService(db, service, environment)

    sync_direction = None
    if data.direction:
        sync_direction = SyncDirection(data.direction)

    result = await sync_service.sync_namespace(
        tenant, namespace, sync_direction, data.dry_run
    )

    # Audit log if not dry run
    if not data.dry_run and result.changes_applied > 0:
        await audit.log_event(
            action=ActionType.UPDATE,
            resource_type=ResourceType.NAMESPACE,
            resource_id=f"{tenant}/{namespace}",
            details={
                "operation": "rbac_sync",
                "direction": data.direction or "auto",
                "changes_applied": result.changes_applied,
            },
            **request_info,
        )

    return SyncResultResponse(
        success=result.success,
        changes_applied=result.changes_applied,
        changes_failed=result.changes_failed,
        details=result.details,
        errors=result.errors,
    )


# Import DbSession for type hint
from app.api.deps import DbSession
