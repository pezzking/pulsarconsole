"""add visibility and ownership to environment

Revision ID: bec3b9a65fc5
Revises: 003
Create Date: 2025-12-28 19:10:40.814753+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "bec3b9a65fc5"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.add_column(
        "environments",
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "environments",
        sa.Column("created_by_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_environments_created_by_id_users",
        "environments",
        "users",
        ["created_by_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_constraint("fk_environments_created_by_id_users", "environments", type_="foreignkey")
    op.drop_column("environments", "created_by_id")
    op.drop_column("environments", "is_shared")
