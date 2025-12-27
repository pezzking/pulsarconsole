"""Pulsar Authentication and Authorization Management Service.

This service handles:
- Pulsar broker authentication status
- Namespace and topic permission management
- Pre-flight validation for auth operations
- Broker dynamic configuration for auth settings
"""

from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger
from app.services.pulsar_admin import PulsarAdminService

logger = get_logger(__name__)


@dataclass
class AuthValidationResult:
    """Result of pre-flight auth validation."""

    can_proceed: bool
    warnings: list[str]
    errors: list[str]
    current_config: dict[str, Any]


@dataclass
class PermissionInfo:
    """Permission information for a role."""

    role: str
    actions: list[str]


class PulsarAuthService:
    """Service for managing Pulsar authentication and authorization.

    This service provides a higher-level abstraction over PulsarAdminService
    for auth-related operations, including pre-flight validation and
    safety checks.
    """

    def __init__(self, pulsar_admin: PulsarAdminService) -> None:
        """Initialize with a PulsarAdminService instance.

        Args:
            pulsar_admin: PulsarAdminService instance (should use superuser token)
        """
        self.pulsar = pulsar_admin

    async def close(self) -> None:
        """Close the underlying Pulsar admin client."""
        await self.pulsar.close()

    # -------------------------------------------------------------------------
    # Auth Status
    # -------------------------------------------------------------------------

    async def get_auth_status(self) -> dict[str, Any]:
        """Get current authentication/authorization status from broker.

        Returns:
            Dict with auth configuration including:
            - authenticationEnabled: bool
            - authorizationEnabled: bool
            - authenticationProviders: list[str]
            - superUserRoles: list[str]
        """
        return await self.pulsar.get_auth_status()

    async def is_auth_enabled(self) -> bool:
        """Check if authentication is enabled on the broker."""
        status = await self.get_auth_status()
        return status.get("authenticationEnabled", False)

    async def is_authorization_enabled(self) -> bool:
        """Check if authorization is enabled on the broker."""
        status = await self.get_auth_status()
        return status.get("authorizationEnabled", False)

    # -------------------------------------------------------------------------
    # Pre-flight Validation
    # -------------------------------------------------------------------------

    async def validate_auth_can_be_enabled(self) -> AuthValidationResult:
        """Validate that authentication can be safely enabled.

        Performs pre-flight checks:
        1. Verify Console has valid superuser access
        2. Check if superUserRoles are configured
        3. Check for existing tenant admins

        Returns:
            AuthValidationResult with can_proceed flag, warnings, and errors
        """
        warnings: list[str] = []
        errors: list[str] = []
        current_config: dict[str, Any] = {}

        # 1. Try to get current auth status (validates connectivity)
        try:
            current_config = await self.get_auth_status()
        except Exception as e:
            errors.append(f"Cannot connect to Pulsar broker: {e}")
            return AuthValidationResult(
                can_proceed=False,
                warnings=warnings,
                errors=errors,
                current_config=current_config,
            )

        # 2. Check if already enabled
        if current_config.get("authenticationEnabled"):
            warnings.append("Authentication is already enabled on the broker")

        # 3. Check for superUserRoles
        super_user_roles = current_config.get("superUserRoles", [])
        if not super_user_roles:
            errors.append(
                "No superUserRoles configured on broker. "
                "You must configure superUserRoles in broker.conf before enabling auth."
            )

        # 4. Try to verify we have superuser access by listing tenants
        try:
            tenants = await self.pulsar.get_tenants()
            if not tenants:
                warnings.append("No tenants found. Consider creating tenants before enabling auth.")
        except Exception as e:
            errors.append(
                f"Cannot list tenants. Ensure your token has superuser privileges: {e}"
            )

        # 5. Check tenant admin roles
        try:
            public_tenant = await self.pulsar.get_tenant("public")
            admin_roles = public_tenant.get("adminRoles", [])
            if not admin_roles:
                warnings.append(
                    "Tenant 'public' has no admin roles. "
                    "Users may lose access to public namespace after enabling auth."
                )
        except Exception:
            # public tenant might not exist
            pass

        can_proceed = len(errors) == 0
        return AuthValidationResult(
            can_proceed=can_proceed,
            warnings=warnings,
            errors=errors,
            current_config=current_config,
        )

    # -------------------------------------------------------------------------
    # Namespace Permissions
    # -------------------------------------------------------------------------

    async def get_namespace_permissions(
        self,
        tenant: str,
        namespace: str,
    ) -> list[PermissionInfo]:
        """Get all permissions for a namespace.

        Returns:
            List of PermissionInfo with role and actions
        """
        permissions = await self.pulsar.get_namespace_permissions(tenant, namespace)
        return [
            PermissionInfo(role=role, actions=actions)
            for role, actions in permissions.items()
        ]

    async def grant_namespace_permission(
        self,
        tenant: str,
        namespace: str,
        role: str,
        actions: list[str],
    ) -> None:
        """Grant permissions to a role on a namespace.

        Args:
            tenant: Tenant name
            namespace: Namespace name
            role: Role to grant permissions to
            actions: List of actions (produce, consume, functions, packages, sinks, sources)
        """
        valid_actions = {"produce", "consume", "functions", "packages", "sinks", "sources"}
        invalid = set(actions) - valid_actions
        if invalid:
            raise ValueError(f"Invalid actions: {invalid}. Valid: {valid_actions}")

        await self.pulsar.grant_namespace_permission(tenant, namespace, role, actions)
        logger.info(
            "Granted namespace permission",
            tenant=tenant,
            namespace=namespace,
            role=role,
            actions=actions,
        )

    async def revoke_namespace_permission(
        self,
        tenant: str,
        namespace: str,
        role: str,
    ) -> None:
        """Revoke all permissions from a role on a namespace."""
        await self.pulsar.revoke_namespace_permission(tenant, namespace, role)
        logger.info(
            "Revoked namespace permission",
            tenant=tenant,
            namespace=namespace,
            role=role,
        )

    # -------------------------------------------------------------------------
    # Topic Permissions
    # -------------------------------------------------------------------------

    async def get_topic_permissions(
        self,
        tenant: str,
        namespace: str,
        topic: str,
        persistent: bool = True,
    ) -> list[PermissionInfo]:
        """Get all permissions for a topic.

        Returns:
            List of PermissionInfo with role and actions
        """
        permissions = await self.pulsar.get_topic_permissions(
            tenant, namespace, topic, persistent
        )
        return [
            PermissionInfo(role=role, actions=actions)
            for role, actions in permissions.items()
        ]

    async def grant_topic_permission(
        self,
        tenant: str,
        namespace: str,
        topic: str,
        role: str,
        actions: list[str],
        persistent: bool = True,
    ) -> None:
        """Grant permissions to a role on a topic.

        Args:
            tenant: Tenant name
            namespace: Namespace name
            topic: Topic name
            role: Role to grant permissions to
            actions: List of actions (produce, consume)
            persistent: Whether the topic is persistent
        """
        valid_actions = {"produce", "consume"}
        invalid = set(actions) - valid_actions
        if invalid:
            raise ValueError(f"Invalid actions for topic: {invalid}. Valid: {valid_actions}")

        await self.pulsar.grant_topic_permission(
            tenant, namespace, topic, role, actions, persistent
        )
        logger.info(
            "Granted topic permission",
            tenant=tenant,
            namespace=namespace,
            topic=topic,
            role=role,
            actions=actions,
        )

    async def revoke_topic_permission(
        self,
        tenant: str,
        namespace: str,
        topic: str,
        role: str,
        persistent: bool = True,
    ) -> None:
        """Revoke all permissions from a role on a topic."""
        await self.pulsar.revoke_topic_permission(tenant, namespace, topic, role, persistent)
        logger.info(
            "Revoked topic permission",
            tenant=tenant,
            namespace=namespace,
            topic=topic,
            role=role,
        )

    # -------------------------------------------------------------------------
    # Broker Configuration
    # -------------------------------------------------------------------------

    async def get_all_dynamic_config(self) -> dict[str, str]:
        """Get all dynamic broker configuration values."""
        return await self.pulsar.get_all_dynamic_config()

    async def get_dynamic_config_names(self) -> list[str]:
        """Get all available dynamic configuration names."""
        return await self.pulsar.get_dynamic_config_names()

    async def update_dynamic_config(
        self,
        config_name: str,
        config_value: str,
    ) -> None:
        """Update a dynamic broker configuration.

        Warning: Some config changes require broker restart.

        Args:
            config_name: Name of the configuration
            config_value: Value to set
        """
        await self.pulsar.update_dynamic_config(config_name, config_value)
        logger.info(
            "Updated broker dynamic config",
            config_name=config_name,
            config_value=config_value,
        )

    async def delete_dynamic_config(self, config_name: str) -> None:
        """Delete/reset a dynamic broker configuration to default."""
        await self.pulsar.delete_dynamic_config(config_name)
        logger.info("Deleted broker dynamic config", config_name=config_name)

    # -------------------------------------------------------------------------
    # High-level Auth Operations
    # -------------------------------------------------------------------------

    async def get_all_permissions_summary(
        self,
        tenant: str,
        namespace: str,
    ) -> dict[str, Any]:
        """Get a summary of all permissions for a namespace and its topics.

        Returns:
            Dict with namespace_permissions and topic_permissions
        """
        # Get namespace permissions
        ns_perms = await self.get_namespace_permissions(tenant, namespace)

        # Get topics and their permissions
        topic_perms: dict[str, list[PermissionInfo]] = {}
        try:
            topics = await self.pulsar.get_topics(tenant, namespace)
            for topic_full in topics:
                # Extract topic name from full path
                topic_name = topic_full.split("/")[-1]
                try:
                    perms = await self.get_topic_permissions(tenant, namespace, topic_name)
                    if perms:
                        topic_perms[topic_name] = perms
                except Exception:
                    # Topic might not have any explicit permissions
                    pass
        except Exception:
            pass

        return {
            "namespace_permissions": [
                {"role": p.role, "actions": p.actions} for p in ns_perms
            ],
            "topic_permissions": {
                topic: [{"role": p.role, "actions": p.actions} for p in perms]
                for topic, perms in topic_perms.items()
            },
        }
