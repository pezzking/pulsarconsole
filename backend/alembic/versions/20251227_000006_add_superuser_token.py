"""Add superuser_token_encrypted to environments table.

This column stores an encrypted superuser token for Pulsar auth management
operations (enable/disable auth, manage permissions). This can be different
from the regular auth token.

Revision ID: 20251227_000006
Revises: 20251227_000005
Create Date: 2024-12-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20251227_000006"
down_revision: Union[str, None] = "20251227_000005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add superuser_token_encrypted column to environments table."""
    op.add_column(
        "environments",
        sa.Column(
            "superuser_token_encrypted",
            sa.Text(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove superuser_token_encrypted column from environments table."""
    op.drop_column("environments", "superuser_token_encrypted")
