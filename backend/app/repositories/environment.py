"""Environment repository for data access."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_value, encrypt_value
from app.models.environment import AuthMode, Environment, RBACSyncMode
from app.repositories.base import BaseRepository


class EnvironmentRepository(BaseRepository[Environment]):
    """Repository for environment configuration operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Environment, session)

    async def get_by_name(self, name: str) -> Environment | None:
        """Get environment by name."""
        result = await self.session.execute(
            select(Environment).where(Environment.name == name)
        )
        return result.scalar_one_or_none()

    async def create_with_encryption(
        self,
        name: str,
        admin_url: str,
        auth_mode: AuthMode = AuthMode.none,
        token: str | None = None,
        superuser_token: str | None = None,
        ca_bundle_ref: str | None = None,
        rbac_enabled: bool = False,
        rbac_sync_mode: RBACSyncMode = RBACSyncMode.console_only,
    ) -> Environment:
        """Create environment with encrypted tokens."""
        encrypted_token = encrypt_value(token) if token else None
        encrypted_superuser_token = encrypt_value(superuser_token) if superuser_token else None

        return await self.create(
            name=name,
            admin_url=admin_url,
            auth_mode=auth_mode,
            token_encrypted=encrypted_token,
            superuser_token_encrypted=encrypted_superuser_token,
            ca_bundle_ref=ca_bundle_ref,
            rbac_enabled=rbac_enabled,
            rbac_sync_mode=rbac_sync_mode,
        )

    async def update_with_encryption(
        self,
        name: str,
        admin_url: str | None = None,
        auth_mode: AuthMode | None = None,
        token: str | None = None,
        superuser_token: str | None = None,
        ca_bundle_ref: str | None = None,
        rbac_enabled: bool | None = None,
        rbac_sync_mode: RBACSyncMode | None = None,
    ) -> Environment | None:
        """Update environment with encrypted tokens."""
        env = await self.get_by_name(name)
        if env is None:
            return None

        if admin_url is not None:
            env.admin_url = admin_url
        if auth_mode is not None:
            env.auth_mode = auth_mode
        if token is not None:
            env.token_encrypted = encrypt_value(token)
        if superuser_token is not None:
            env.superuser_token_encrypted = encrypt_value(superuser_token)
        if ca_bundle_ref is not None:
            env.ca_bundle_ref = ca_bundle_ref
        if rbac_enabled is not None:
            env.rbac_enabled = rbac_enabled
        if rbac_sync_mode is not None:
            env.rbac_sync_mode = rbac_sync_mode

        await self.session.flush()
        await self.session.refresh(env)
        return env

    def get_decrypted_token(self, environment: Environment) -> str | None:
        """Get decrypted token from environment."""
        if environment.token_encrypted:
            return decrypt_value(environment.token_encrypted)
        return None

    def get_decrypted_superuser_token(self, environment: Environment) -> str | None:
        """Get decrypted superuser token from environment.

        Falls back to regular token if superuser token is not set.
        """
        if environment.superuser_token_encrypted:
            return decrypt_value(environment.superuser_token_encrypted)
        # Fallback to regular token
        return self.get_decrypted_token(environment)

    async def delete_by_name(self, name: str) -> bool:
        """Delete environment by name."""
        env = await self.get_by_name(name)
        if env is None:
            return False

        await self.session.delete(env)
        await self.session.flush()
        return True

    async def get_active(self) -> Environment | None:
        """Get the active environment."""
        result = await self.session.execute(
            select(Environment).where(Environment.is_active == True)
        )
        return result.scalar_one_or_none()

    async def set_active(self, name: str) -> Environment | None:
        """Set an environment as active (deactivates all others)."""
        env = await self.get_by_name(name)
        if env is None:
            return None

        # Deactivate all environments
        await self.session.execute(
            update(Environment).values(is_active=False)
        )

        # Activate the specified environment
        env.is_active = True
        await self.session.flush()
        await self.session.refresh(env)
        return env
