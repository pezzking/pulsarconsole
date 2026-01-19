"""Add notification channels and delivery tracking.

Revision ID: 008_notification_channels
Revises: 007_oidc_group_mappings
Create Date: 2025-01-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "008_notification_channels"
down_revision: Union[str, None] = "007_oidc_group_mappings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create notification_channels and notification_deliveries tables."""
    # Create notification_channels table
    op.create_table(
        "notification_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("channel_type", sa.String(50), nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("severity_filter", postgresql.JSONB, nullable=True),
        sa.Column("type_filter", postgresql.JSONB, nullable=True),
        sa.Column("config_encrypted", sa.Text, nullable=False),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_notification_channel_type",
        "notification_channels",
        ["channel_type"],
    )
    op.create_index(
        "idx_notification_channel_enabled",
        "notification_channels",
        ["is_enabled"],
    )

    # Create notification_deliveries table
    op.create_table(
        "notification_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "notification_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notifications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "channel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notification_channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "notification_id",
            "channel_id",
            name="uq_delivery_notification_channel",
        ),
    )
    op.create_index(
        "idx_delivery_notification",
        "notification_deliveries",
        ["notification_id"],
    )
    op.create_index(
        "idx_delivery_channel",
        "notification_deliveries",
        ["channel_id"],
    )
    op.create_index(
        "idx_delivery_status",
        "notification_deliveries",
        ["status"],
    )


def downgrade() -> None:
    """Drop notification_deliveries and notification_channels tables."""
    op.drop_index("idx_delivery_status", table_name="notification_deliveries")
    op.drop_index("idx_delivery_channel", table_name="notification_deliveries")
    op.drop_index("idx_delivery_notification", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")

    op.drop_index("idx_notification_channel_enabled", table_name="notification_channels")
    op.drop_index("idx_notification_channel_type", table_name="notification_channels")
    op.drop_table("notification_channels")
