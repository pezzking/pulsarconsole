"""RBAC Synchronization Service.

This service handles bidirectional synchronization between Console RBAC
(roles and permissions stored in the database) and Pulsar permissions
(stored on the Pulsar broker).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.environment import Environment, RBACSyncMode
from app.models.permission import PermissionAction, ResourceLevel
from app.services.pulsar_auth import PulsarAuthService

logger = get_logger(__name__)


class SyncDirection(str, Enum):
    """Direction of RBAC synchronization."""

    CONSOLE_TO_PULSAR = "console_to_pulsar"
    PULSAR_TO_CONSOLE = "pulsar_to_console"


@dataclass
class SyncChange:
    """Represents a single change in the sync operation."""

    action: str  # "add", "remove", "update"
    resource_type: str  # "namespace", "topic"
    resource_id: str
    role: str
    permissions: list[str]
    source: str  # "console" or "pulsar"


@dataclass
class SyncPreview:
    """Preview of changes that would be made during sync."""

    direction: SyncDirection
    changes: list[SyncChange] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return len(self.changes) > 0

    @property
    def can_proceed(self) -> bool:
        return len(self.errors) == 0


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    changes_applied: int
    changes_failed: int
    details: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class RbacSyncService:
    """Service for synchronizing RBAC between Console and Pulsar.

    This service provides:
    - Dry-run mode for previewing changes
    - Bidirectional sync (Console → Pulsar, Pulsar → Console)
    - Diff view between Console and Pulsar state
    - Per-environment sync configuration
    """

    def __init__(
        self,
        session: AsyncSession,
        pulsar_auth: PulsarAuthService,
        environment: Environment,
    ) -> None:
        """Initialize the RBAC sync service.

        Args:
            session: Database session for Console RBAC operations
            pulsar_auth: Pulsar auth service for Pulsar operations
            environment: Current environment configuration
        """
        self.session = session
        self.pulsar_auth = pulsar_auth
        self.environment = environment

    # -------------------------------------------------------------------------
    # Console RBAC Operations
    # -------------------------------------------------------------------------

    async def get_console_permissions(
        self,
        tenant: str,
        namespace: str,
    ) -> dict[str, list[str]]:
        """Get permissions from Console RBAC for a namespace.

        Returns:
            Dict mapping role names to their permissions
        """
        from app.repositories.role import RoleRepository
        from app.repositories.permission import PermissionRepository

        role_repo = RoleRepository(self.session)
        perm_repo = PermissionRepository(self.session)

        # Get all roles for this environment
        roles = await role_repo.get_by_environment(self.environment.id)

        permissions: dict[str, list[str]] = {}

        for role in roles:
            # Get permissions for this role on this namespace
            role_perms = await perm_repo.get_by_role_and_resource(
                role_id=role.id,
                resource_level=ResourceLevel.NAMESPACE,
                resource_path=f"{tenant}/{namespace}",
            )

            if role_perms:
                actions = [p.action.value for p in role_perms]
                if actions:
                    permissions[role.name] = actions

        return permissions

    async def set_console_permission(
        self,
        tenant: str,
        namespace: str,
        role_name: str,
        actions: list[str],
    ) -> None:
        """Set permissions in Console RBAC for a role on a namespace.

        Creates the role if it doesn't exist.
        """
        from app.repositories.role import RoleRepository
        from app.repositories.permission import PermissionRepository

        role_repo = RoleRepository(self.session)
        perm_repo = PermissionRepository(self.session)

        # Get or create role
        role = await role_repo.get_by_name_and_environment(
            role_name, self.environment.id
        )
        if not role:
            role = await role_repo.create(
                name=role_name,
                environment_id=self.environment.id,
                description=f"Auto-created from Pulsar sync",
            )

        # Clear existing permissions for this resource
        await perm_repo.delete_by_role_and_resource(
            role_id=role.id,
            resource_level=ResourceLevel.NAMESPACE,
            resource_path=f"{tenant}/{namespace}",
        )

        # Add new permissions
        for action_str in actions:
            try:
                action = PermissionAction(action_str)
                await perm_repo.create(
                    role_id=role.id,
                    action=action,
                    resource_level=ResourceLevel.NAMESPACE,
                    resource_path=f"{tenant}/{namespace}",
                )
            except ValueError:
                logger.warning(
                    "Skipping unknown action during sync",
                    action=action_str,
                    role=role_name,
                )

    async def remove_console_permission(
        self,
        tenant: str,
        namespace: str,
        role_name: str,
    ) -> None:
        """Remove all permissions for a role on a namespace in Console."""
        from app.repositories.role import RoleRepository
        from app.repositories.permission import PermissionRepository

        role_repo = RoleRepository(self.session)
        perm_repo = PermissionRepository(self.session)

        role = await role_repo.get_by_name_and_environment(
            role_name, self.environment.id
        )
        if role:
            await perm_repo.delete_by_role_and_resource(
                role_id=role.id,
                resource_level=ResourceLevel.NAMESPACE,
                resource_path=f"{tenant}/{namespace}",
            )

    # -------------------------------------------------------------------------
    # Diff & Preview
    # -------------------------------------------------------------------------

    async def get_diff(
        self,
        tenant: str,
        namespace: str,
    ) -> dict[str, Any]:
        """Get the difference between Console and Pulsar permissions.

        Returns:
            Dict with:
            - only_in_console: Permissions only in Console
            - only_in_pulsar: Permissions only in Pulsar
            - different: Permissions that exist in both but differ
            - same: Permissions that are the same
        """
        console_perms = await self.get_console_permissions(tenant, namespace)
        pulsar_perms = await self.pulsar_auth.get_namespace_permissions(tenant, namespace)

        # Convert Pulsar perms to dict
        pulsar_dict = {p.role: p.actions for p in pulsar_perms}

        only_in_console: dict[str, list[str]] = {}
        only_in_pulsar: dict[str, list[str]] = {}
        different: dict[str, dict[str, list[str]]] = {}
        same: dict[str, list[str]] = {}

        # Check console permissions
        for role, actions in console_perms.items():
            if role not in pulsar_dict:
                only_in_console[role] = actions
            elif set(actions) != set(pulsar_dict[role]):
                different[role] = {
                    "console": actions,
                    "pulsar": pulsar_dict[role],
                }
            else:
                same[role] = actions

        # Check pulsar permissions
        for role, actions in pulsar_dict.items():
            if role not in console_perms:
                only_in_pulsar[role] = actions

        return {
            "only_in_console": only_in_console,
            "only_in_pulsar": only_in_pulsar,
            "different": different,
            "same": same,
            "total_console": len(console_perms),
            "total_pulsar": len(pulsar_dict),
        }

    async def preview_sync(
        self,
        tenant: str,
        namespace: str,
        direction: SyncDirection | None = None,
    ) -> SyncPreview:
        """Preview what changes would be made during sync.

        Args:
            tenant: Tenant name
            namespace: Namespace name
            direction: Sync direction (defaults to environment setting)

        Returns:
            SyncPreview with list of changes that would be made
        """
        # Determine direction
        if direction is None:
            if self.environment.rbac_sync_mode == RBACSyncMode.sync_to_pulsar:
                direction = SyncDirection.CONSOLE_TO_PULSAR
            elif self.environment.rbac_sync_mode == RBACSyncMode.read_from_pulsar:
                direction = SyncDirection.PULSAR_TO_CONSOLE
            else:
                return SyncPreview(
                    direction=SyncDirection.CONSOLE_TO_PULSAR,
                    errors=["RBAC sync is not enabled for this environment"],
                )

        diff = await self.get_diff(tenant, namespace)
        changes: list[SyncChange] = []
        warnings: list[str] = []

        if direction == SyncDirection.CONSOLE_TO_PULSAR:
            # Add permissions that only exist in Console
            for role, actions in diff["only_in_console"].items():
                changes.append(
                    SyncChange(
                        action="add",
                        resource_type="namespace",
                        resource_id=f"{tenant}/{namespace}",
                        role=role,
                        permissions=actions,
                        source="console",
                    )
                )

            # Remove permissions that only exist in Pulsar
            for role, actions in diff["only_in_pulsar"].items():
                changes.append(
                    SyncChange(
                        action="remove",
                        resource_type="namespace",
                        resource_id=f"{tenant}/{namespace}",
                        role=role,
                        permissions=actions,
                        source="pulsar",
                    )
                )
                warnings.append(
                    f"Role '{role}' exists only in Pulsar and will be removed"
                )

            # Update permissions that differ
            for role, perms in diff["different"].items():
                changes.append(
                    SyncChange(
                        action="update",
                        resource_type="namespace",
                        resource_id=f"{tenant}/{namespace}",
                        role=role,
                        permissions=perms["console"],
                        source="console",
                    )
                )

        else:  # PULSAR_TO_CONSOLE
            # Add permissions that only exist in Pulsar
            for role, actions in diff["only_in_pulsar"].items():
                changes.append(
                    SyncChange(
                        action="add",
                        resource_type="namespace",
                        resource_id=f"{tenant}/{namespace}",
                        role=role,
                        permissions=actions,
                        source="pulsar",
                    )
                )

            # Remove permissions that only exist in Console
            for role, actions in diff["only_in_console"].items():
                changes.append(
                    SyncChange(
                        action="remove",
                        resource_type="namespace",
                        resource_id=f"{tenant}/{namespace}",
                        role=role,
                        permissions=actions,
                        source="console",
                    )
                )
                warnings.append(
                    f"Role '{role}' exists only in Console and will be removed"
                )

            # Update permissions that differ
            for role, perms in diff["different"].items():
                changes.append(
                    SyncChange(
                        action="update",
                        resource_type="namespace",
                        resource_id=f"{tenant}/{namespace}",
                        role=role,
                        permissions=perms["pulsar"],
                        source="pulsar",
                    )
                )

        return SyncPreview(
            direction=direction,
            changes=changes,
            warnings=warnings,
        )

    # -------------------------------------------------------------------------
    # Sync Operations
    # -------------------------------------------------------------------------

    async def sync_namespace(
        self,
        tenant: str,
        namespace: str,
        direction: SyncDirection | None = None,
        dry_run: bool = False,
    ) -> SyncResult:
        """Synchronize RBAC for a namespace.

        Args:
            tenant: Tenant name
            namespace: Namespace name
            direction: Sync direction (defaults to environment setting)
            dry_run: If True, only preview changes without applying

        Returns:
            SyncResult with success status and details
        """
        preview = await self.preview_sync(tenant, namespace, direction)

        if not preview.can_proceed:
            return SyncResult(
                success=False,
                changes_applied=0,
                changes_failed=0,
                errors=preview.errors,
            )

        if dry_run or not preview.has_changes:
            return SyncResult(
                success=True,
                changes_applied=0,
                changes_failed=0,
                details=[
                    f"Dry run: {len(preview.changes)} changes would be made"
                ] if dry_run else ["No changes needed"],
            )

        # Apply changes
        applied = 0
        failed = 0
        details: list[str] = []
        errors: list[str] = []

        for change in preview.changes:
            try:
                if preview.direction == SyncDirection.CONSOLE_TO_PULSAR:
                    await self._apply_to_pulsar(change, tenant, namespace)
                else:
                    await self._apply_to_console(change, tenant, namespace)

                applied += 1
                details.append(
                    f"{change.action.capitalize()} {change.role}: {change.permissions}"
                )
            except Exception as e:
                failed += 1
                errors.append(f"Failed to {change.action} {change.role}: {e}")
                logger.error(
                    "RBAC sync change failed",
                    change=change,
                    error=str(e),
                )

        await self.session.commit()

        return SyncResult(
            success=failed == 0,
            changes_applied=applied,
            changes_failed=failed,
            details=details,
            errors=errors,
        )

    async def _apply_to_pulsar(
        self,
        change: SyncChange,
        tenant: str,
        namespace: str,
    ) -> None:
        """Apply a sync change to Pulsar."""
        if change.action == "add" or change.action == "update":
            await self.pulsar_auth.grant_namespace_permission(
                tenant=tenant,
                namespace=namespace,
                role=change.role,
                actions=change.permissions,
            )
        elif change.action == "remove":
            await self.pulsar_auth.revoke_namespace_permission(
                tenant=tenant,
                namespace=namespace,
                role=change.role,
            )

    async def _apply_to_console(
        self,
        change: SyncChange,
        tenant: str,
        namespace: str,
    ) -> None:
        """Apply a sync change to Console."""
        if change.action == "add" or change.action == "update":
            await self.set_console_permission(
                tenant=tenant,
                namespace=namespace,
                role_name=change.role,
                actions=change.permissions,
            )
        elif change.action == "remove":
            await self.remove_console_permission(
                tenant=tenant,
                namespace=namespace,
                role_name=change.role,
            )

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    async def sync_all_namespaces(
        self,
        tenant: str,
        direction: SyncDirection | None = None,
        dry_run: bool = False,
    ) -> dict[str, SyncResult]:
        """Synchronize RBAC for all namespaces in a tenant.

        Args:
            tenant: Tenant name
            direction: Sync direction
            dry_run: If True, only preview changes

        Returns:
            Dict mapping namespace names to their sync results
        """
        results: dict[str, SyncResult] = {}

        try:
            # Get all namespaces (need to access pulsar_admin through pulsar_auth)
            namespaces = await self.pulsar_auth.pulsar.get_namespaces(tenant)
        except Exception as e:
            logger.error("Failed to get namespaces for sync", tenant=tenant, error=str(e))
            return {
                "_error": SyncResult(
                    success=False,
                    changes_applied=0,
                    changes_failed=0,
                    errors=[f"Failed to get namespaces: {e}"],
                )
            }

        for ns_full in namespaces:
            # Extract namespace name from full path (tenant/namespace)
            namespace = ns_full.split("/")[-1] if "/" in ns_full else ns_full

            try:
                result = await self.sync_namespace(tenant, namespace, direction, dry_run)
                results[namespace] = result
            except Exception as e:
                results[namespace] = SyncResult(
                    success=False,
                    changes_applied=0,
                    changes_failed=0,
                    errors=[str(e)],
                )

        return results
