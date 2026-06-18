"""create notifications tables

Revision ID: 20260617_01
Revises: ce6c64e55d52
Create Date: 2026-06-17 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = '20260617_01'
down_revision: str | Sequence[str] | None = 'ce6c64e55d52'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create notifications table
    op.create_table('notifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)

    # Create notification_settings table
    op.create_table('notification_settings',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('email_enabled', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
        sa.Column('push_enabled', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
        sa.Column('sound_enabled', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
        sa.Column('quiet_hours_start', sa.Time(), nullable=True),
        sa.Column('quiet_hours_end', sa.Time(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id')
    )
    op.create_index(op.f('ix_notification_settings_user_id'), 'notification_settings', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop notification_settings index and table
    op.drop_index(op.f('ix_notification_settings_user_id'), table_name='notification_settings')
    op.drop_table('notification_settings')

    # Drop notifications indexes and table
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_table('notifications')
