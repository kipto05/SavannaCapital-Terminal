"""create_notifications_tables

Revision ID: 20250617_01
Revises: 11a232827345
Create Date: 2026-06-17 02:49:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '20250617_01'
down_revision: str | Sequence[str] | None = '11a232827345'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create notifications table
    op.create_table('notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('data', postgresql.JSON(), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMPTZ(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('expires_at', postgresql.TIMESTAMPTZ(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)

    # Create notification_recipients table
    op.create_table('notification_recipients',
        sa.Column('notification_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_read', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
        sa.Column('read_at', postgresql.TIMESTAMPTZ(), nullable=True),
        sa.Column('delivered_at', postgresql.TIMESTAMPTZ(), nullable=True),
        sa.Column('email_sent_at', postgresql.TIMESTAMPTZ(), nullable=True),
        sa.ForeignKeyConstraint(['notification_id'], ['notifications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('notification_id', 'user_id')
    )
    op.create_index(op.f('ix_notification_recipients_user_id_is_read'), 'notification_recipients', ['user_id', 'is_read'], unique=False)
    op.create_index(op.f('ix_notification_recipients_notification_id'), 'notification_recipients', ['notification_id'], unique=False)

    # Create notification_settings table
    op.create_table('notification_settings',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('in_app_enabled', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
        sa.Column('email_enabled', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('user_id', 'event_type')
    )
    op.create_index(op.f('ix_notification_settings_user_id'), 'notification_settings', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop notification_recipients indexes
    op.drop_index(op.f('ix_notification_recipients_notification_id'), table_name='notification_recipients')
    op.drop_index(op.f('ix_notification_recipients_user_id_is_read'), table_name='notification_recipients')

    # Drop notification_recipients table
    op.drop_table('notification_recipients')

    # Drop notification_settings index and table
    op.drop_index(op.f('ix_notification_settings_user_id'), table_name='notification_settings')
    op.drop_table('notification_settings')

    # Drop notifications index and table
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_table('notifications')
