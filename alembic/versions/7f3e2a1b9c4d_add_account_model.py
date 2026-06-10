"""Add Account model

Revision ID: 7f3e2a1b9c4d
Revises: cbbe6d2aea12
Create Date: 2026-06-10 19:48:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '7f3e2a1b9c4d'
down_revision: Union[str, Sequence[str], None] = 'cbbe6d2aea12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'accounts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('account_name', sa.String(length=64), nullable=False),
        sa.Column('broker', sa.String(length=32), nullable=False),
        sa.Column('server', sa.String(length=128), nullable=False),
        sa.Column('mt5_login', sa.Integer(), nullable=False),
        sa.Column('password_enc', sa.Text(), nullable=False),
        sa.Column('investor_password_enc', sa.Text(), nullable=True),
        sa.Column('account_type', sa.String(length=8), nullable=False, server_default='demo'),
        sa.Column('weight', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('colour', sa.String(length=16), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_connected', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_name', name='uq_accounts_name'),
        sa.UniqueConstraint('mt5_login', name='uq_accounts_mt5_login'),
        sa.CheckConstraint('weight >= 0.0 AND weight <= 2.0', name='ck_account_weight'),
    )
    op.create_index('ix_accounts_account_name', 'accounts', ['account_name'], unique=True)
    op.create_index('ix_accounts_mt5_login', 'accounts', ['mt5_login'], unique=True)
    op.create_index('ix_accounts_active', 'accounts', ['is_active'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_accounts_active', table_name='accounts')
    op.drop_index('ix_accounts_mt5_login', table_name='accounts')
    op.drop_index('ix_accounts_account_name', table_name='accounts')
    op.drop_table('accounts')
