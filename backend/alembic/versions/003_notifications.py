"""Notifications table.

Creates the notifications table for system alerts and messages.

Revision ID: 003
Revises: 002
Create Date: 2025-12-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create notifications table."""
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", sa.String(50), nullable=False, index=True),
        sa.Column("severity", sa.String(20), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(512), nullable=True),
        sa.Column("extra_data", postgresql.JSONB, nullable=True),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_dismissed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create indexes
    op.create_index(
        "idx_notification_unread",
        "notifications",
        ["is_read", "is_dismissed"],
    )
    op.create_index(
        "idx_notification_type_severity",
        "notifications",
        ["type", "severity"],
    )
    op.create_index(
        "idx_notification_created_desc",
        "notifications",
        [sa.text("created_at DESC")],
    )


def downgrade() -> None:
    """Drop notifications table."""
    op.drop_index("idx_notification_created_desc", table_name="notifications")
    op.drop_index("idx_notification_type_severity", table_name="notifications")
    op.drop_index("idx_notification_unread", table_name="notifications")
    op.drop_table("notifications")
