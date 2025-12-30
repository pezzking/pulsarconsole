"""Seed data for permissions and default roles."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.permission import Permission, PermissionAction, ResourceLevel
from app.models.role import Role
from app.models.role_permission import RolePermission


# Define all available permissions
PERMISSION_DEFINITIONS = [
    # Topic-level actions
    {
        "action": PermissionAction.produce,
        "resource_level": ResourceLevel.topic,
        "description": "Publish messages to a topic",
    },
    {
        "action": PermissionAction.consume,
        "resource_level": ResourceLevel.topic,
        "description": "Consume messages from a topic",
    },
    # Namespace-level actions
    {
        "action": PermissionAction.functions,
        "resource_level": ResourceLevel.namespace,
        "description": "Manage Pulsar Functions in a namespace",
    },
    {
        "action": PermissionAction.sources,
        "resource_level": ResourceLevel.namespace,
        "description": "Manage Pulsar IO sources in a namespace",
    },
    {
        "action": PermissionAction.sinks,
        "resource_level": ResourceLevel.namespace,
        "description": "Manage Pulsar IO sinks in a namespace",
    },
    {
        "action": PermissionAction.packages,
        "resource_level": ResourceLevel.namespace,
        "description": "Manage packages in a namespace",
    },
    # Administrative actions - Cluster level
    {
        "action": PermissionAction.admin,
        "resource_level": ResourceLevel.cluster,
        "description": "Full administrative access to the cluster",
    },
    {
        "action": PermissionAction.read,
        "resource_level": ResourceLevel.cluster,
        "description": "Read cluster configuration and status",
    },
    # Administrative actions - Tenant level
    {
        "action": PermissionAction.admin,
        "resource_level": ResourceLevel.tenant,
        "description": "Full administrative access to a tenant",
    },
    {
        "action": PermissionAction.read,
        "resource_level": ResourceLevel.tenant,
        "description": "Read tenant configuration and metadata",
    },
    {
        "action": PermissionAction.write,
        "resource_level": ResourceLevel.tenant,
        "description": "Create and modify tenant resources",
    },
    # Administrative actions - Namespace level
    {
        "action": PermissionAction.admin,
        "resource_level": ResourceLevel.namespace,
        "description": "Full administrative access to a namespace",
    },
    {
        "action": PermissionAction.read,
        "resource_level": ResourceLevel.namespace,
        "description": "Read namespace configuration and topics",
    },
    {
        "action": PermissionAction.write,
        "resource_level": ResourceLevel.namespace,
        "description": "Create and modify namespace resources",
    },
    # Administrative actions - Topic level
    {
        "action": PermissionAction.admin,
        "resource_level": ResourceLevel.topic,
        "description": "Full administrative access to a topic",
    },
    {
        "action": PermissionAction.read,
        "resource_level": ResourceLevel.topic,
        "description": "Read topic metadata and statistics",
    },
    {
        "action": PermissionAction.write,
        "resource_level": ResourceLevel.topic,
        "description": "Modify topic configuration",
    },
]


# Default system roles with their permissions
# Permission patterns use: action:resource_level:resource_pattern
# resource_pattern can be:
#   - None (all resources)
#   - "*" (all at that level)
#   - "tenant/*" (all in tenant)
#   - "tenant/namespace/*" (all in namespace)
#   - "tenant/namespace/topic" (specific topic)
DEFAULT_ROLES = {
    "superuser": {
        "description": "Full system access - all permissions on all resources",
        "is_system": True,
        "permissions": [
            # All admin permissions
            (PermissionAction.admin, ResourceLevel.cluster, "*"),
            (PermissionAction.admin, ResourceLevel.tenant, "*"),
            (PermissionAction.admin, ResourceLevel.namespace, "*"),
            # All read/write permissions
            (PermissionAction.read, ResourceLevel.cluster, "*"),
            (PermissionAction.read, ResourceLevel.tenant, "*"),
            (PermissionAction.read, ResourceLevel.namespace, "*"),
            (PermissionAction.read, ResourceLevel.topic, "*"),
            (PermissionAction.write, ResourceLevel.tenant, "*"),
            (PermissionAction.write, ResourceLevel.namespace, "*"),
            (PermissionAction.write, ResourceLevel.topic, "*"),
            # All topic operations
            (PermissionAction.produce, ResourceLevel.topic, "*"),
            (PermissionAction.consume, ResourceLevel.topic, "*"),
            # All namespace operations
            (PermissionAction.functions, ResourceLevel.namespace, "*"),
            (PermissionAction.sources, ResourceLevel.namespace, "*"),
            (PermissionAction.sinks, ResourceLevel.namespace, "*"),
            (PermissionAction.packages, ResourceLevel.namespace, "*"),
        ],
    },
    "admin": {
        "description": "Administrative access to tenants and namespaces",
        "is_system": True,
        "permissions": [
            (PermissionAction.admin, ResourceLevel.tenant, "*"),
            (PermissionAction.admin, ResourceLevel.namespace, "*"),
            (PermissionAction.read, ResourceLevel.cluster, "*"),
            (PermissionAction.read, ResourceLevel.tenant, "*"),
            (PermissionAction.read, ResourceLevel.namespace, "*"),
            (PermissionAction.read, ResourceLevel.topic, "*"),
            (PermissionAction.write, ResourceLevel.tenant, "*"),
            (PermissionAction.write, ResourceLevel.namespace, "*"),
            (PermissionAction.write, ResourceLevel.topic, "*"),
            (PermissionAction.produce, ResourceLevel.topic, "*"),
            (PermissionAction.consume, ResourceLevel.topic, "*"),
            (PermissionAction.functions, ResourceLevel.namespace, "*"),
            (PermissionAction.sources, ResourceLevel.namespace, "*"),
            (PermissionAction.sinks, ResourceLevel.namespace, "*"),
            (PermissionAction.packages, ResourceLevel.namespace, "*"),
        ],
    },
    "operator": {
        "description": "Operational access - read all, manage topics and messages",
        "is_system": True,
        "permissions": [
            (PermissionAction.read, ResourceLevel.cluster, "*"),
            (PermissionAction.read, ResourceLevel.tenant, "*"),
            (PermissionAction.read, ResourceLevel.namespace, "*"),
            (PermissionAction.read, ResourceLevel.topic, "*"),
            (PermissionAction.write, ResourceLevel.topic, "*"),
            (PermissionAction.produce, ResourceLevel.topic, "*"),
            (PermissionAction.consume, ResourceLevel.topic, "*"),
        ],
    },
    "developer": {
        "description": "Developer access - read all, produce and consume messages",
        "is_system": True,
        "permissions": [
            (PermissionAction.read, ResourceLevel.cluster, "*"),
            (PermissionAction.read, ResourceLevel.tenant, "*"),
            (PermissionAction.read, ResourceLevel.namespace, "*"),
            (PermissionAction.read, ResourceLevel.topic, "*"),
            (PermissionAction.produce, ResourceLevel.topic, "*"),
            (PermissionAction.consume, ResourceLevel.topic, "*"),
        ],
    },
    "viewer": {
        "description": "Read-only access to all resources",
        "is_system": True,
        "permissions": [
            (PermissionAction.read, ResourceLevel.cluster, "*"),
            (PermissionAction.read, ResourceLevel.tenant, "*"),
            (PermissionAction.read, ResourceLevel.namespace, "*"),
            (PermissionAction.read, ResourceLevel.topic, "*"),
        ],
    },
}


async def seed_permissions(session: AsyncSession) -> dict[str, Permission]:
    """
    Seed the permissions table with all available permissions.

    Returns a dict mapping "action:resource_level" to Permission objects.
    """
    permissions: dict[str, Permission] = {}

    for perm_def in PERMISSION_DEFINITIONS:
        action = perm_def["action"]
        resource_level = perm_def["resource_level"]
        key = f"{action.value}:{resource_level.value}"

        # Check if permission already exists
        result = await session.execute(
            select(Permission).where(
                Permission.action == action,
                Permission.resource_level == resource_level
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            permissions[key] = existing
        else:
            permission = Permission(
                action=action,
                resource_level=resource_level,
                description=perm_def["description"],
            )
            session.add(permission)
            permissions[key] = permission

    await session.flush()
    return permissions


async def seed_default_roles(
    session: AsyncSession,
    environment_id: UUID,
    permissions: dict[str, Permission]
) -> dict[str, Role]:
    """
    Seed default system roles for an environment.

    Args:
        session: Database session
        environment_id: The environment to create roles for
        permissions: Dict of permissions from seed_permissions()

    Returns:
        Dict mapping role name to Role objects
    """
    roles: dict[str, Role] = {}

    for role_name, role_def in DEFAULT_ROLES.items():
        # Check if role already exists
        result = await session.execute(
            select(Role).where(
                Role.environment_id == environment_id,
                Role.name == role_name
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            roles[role_name] = existing
            continue

        # Create the role
        role = Role(
            environment_id=environment_id,
            name=role_name,
            description=role_def["description"],
            is_system=True,
        )
        session.add(role)
        await session.flush()

        # Add permissions to the role
        for action, resource_level, resource_pattern in role_def["permissions"]:
            # Handle both enum objects and strings for backward compatibility/flexibility
            action_val = action.value if hasattr(action, "value") else action
            resource_level_val = resource_level.value if hasattr(resource_level, "value") else resource_level
            perm_key = f"{action_val}:{resource_level_val}"
            
            if perm_key in permissions:
                role_permission = RolePermission(
                    role_id=role.id,
                    permission_id=permissions[perm_key].id,
                    resource_pattern=resource_pattern,
                )
                session.add(role_permission)

        roles[role_name] = role

    await session.flush()
    return roles


async def seed_rbac_data(session: AsyncSession, environment_id: UUID) -> None:
    """
    Seed all RBAC data for an environment.

    This includes:
    - All permission definitions
    - Default system roles with their permissions

    Args:
        session: Database session
        environment_id: The environment to set up RBAC for
    """
    permissions = await seed_permissions(session)
    await seed_default_roles(session, environment_id, permissions)
    await session.commit()
