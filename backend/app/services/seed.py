"""Seed service for creating default permissions and roles."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.permission import Permission, PermissionAction, ResourceLevel
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user_role import UserRole
from app.db.seed_data import (
    seed_rbac_data, 
    seed_permissions, 
    seed_default_roles, 
    PERMISSION_DEFINITIONS,
    DEFAULT_ROLES
)

logger = get_logger(__name__)


class SeedService:
    """Service for seeding default data."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._permission_cache: dict[tuple[PermissionAction, ResourceLevel], UUID] = {}

    async def seed_permissions(self) -> dict[tuple[PermissionAction, ResourceLevel], UUID]:
        """Create default permissions if they don't exist.

        Returns a mapping of (action, resource_level) -> permission_id
        """
        # Use the logic from seed_data.py but return the map SeedService expects
        perms = await seed_permissions(self.session)
        
        permission_map = {}
        for key, perm in perms.items():
            # key is "action:resource_level"
            action_str, level_str = key.split(":")
            action = PermissionAction(action_str)
            level = ResourceLevel(level_str)
            permission_map[(action, level)] = perm.id
            
        self._permission_cache = permission_map
        return permission_map

    async def seed_roles_for_environment(self, environment_id: UUID) -> dict[str, UUID]:
        """Create default roles for an environment if they don't exist.

        Returns a mapping of role_name -> role_id
        """
        # We use the existing seed_rbac_data logic which is more robust
        permissions = await seed_permissions(self.session)
        roles = await seed_default_roles(self.session, environment_id, permissions)
        
        return {name: role.id for name, role in roles.items()}

    async def seed_all_environments(self) -> None:
        """Seed roles for all existing environments."""
        from app.models.environment import Environment

        result = await self.session.execute(select(Environment))
        environments = result.scalars().all()

        # First seed permissions
        await self.seed_permissions()

        if not environments:
            logger.warning("No environments found. Roles can only be seeded once an environment is created.")
            return

        # Then seed roles for each environment
        for env in environments:
            await self.seed_roles_for_environment(env.id)
            logger.info("Seeded roles for environment", environment=env.name)

        await self.session.commit()
        logger.info(f"Seeded roles for {len(environments)} environments")

    async def get_superuser_role_id(self, environment_id: UUID) -> UUID | None:
        """Get the superuser role ID for an environment."""
        result = await self.session.execute(
            select(Role.id).where(
                Role.name == "superuser",
                Role.environment_id == environment_id,
            )
        )
        return result.scalar_one_or_none()

    async def assign_user_to_superuser_role(
        self, user_id: UUID, environment_id: UUID, assigned_by: UUID | None = None
    ) -> bool:
        """Assign a user to the superuser role for an environment.

        Returns True if assignment was created, False if already exists.
        """
        role_id = await self.get_superuser_role_id(environment_id)
        if not role_id:
            logger.warning(
                "Superuser role not found for environment",
                environment_id=str(environment_id),
            )
            return False

        # Check if assignment exists
        result = await self.session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id,
            )
        )
        if result.scalar_one_or_none():
            return False  # Already assigned

        user_role = UserRole(
            user_id=user_id,
            role_id=role_id,
            assigned_by=assigned_by,
        )
        self.session.add(user_role)
        await self.session.flush()
        logger.info(
            "Assigned user to superuser role",
            user_id=str(user_id),
            environment_id=str(environment_id),
        )
        return True

    async def assign_user_to_superuser_role_all_environments(
        self, user_id: UUID
    ) -> int:
        """Assign a user to the superuser role for ALL environments.

        Returns the number of assignments created.
        """
        from app.models.environment import Environment

        result = await self.session.execute(select(Environment.id))
        environment_ids = result.scalars().all()

        count = 0
        for env_id in environment_ids:
            if await self.assign_user_to_superuser_role(user_id, env_id):
                count += 1

        return count
