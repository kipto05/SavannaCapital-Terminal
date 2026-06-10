"""add_raw_password_to_accounts

Revision ID: f23152f474a8
Revises: 7f3e2a1b9c4d
Create Date: 2026-06-10 23:55:45.149887

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f23152f474a8'
down_revision: Union[str, Sequence[str], None] = '7f3e2a1b9c4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: raw_password + account_type enum."""
    # Step 1: create enum type
    op.execute("CREATE TYPE accounttype AS ENUM ('live', 'demo')")

    # Step 2: drop old server_default so ALTER TYPE doesn't choke on the cast
    op.execute("ALTER TABLE accounts ALTER COLUMN account_type DROP DEFAULT")

    # Step 3: cast column to new enum (lower() matches 'demo'/'live' values)
    op.execute("ALTER TABLE accounts ALTER COLUMN account_type TYPE accounttype USING LOWER(account_type)::accounttype")

    # Step 4: set new enum-compatible default
    op.execute("ALTER TABLE accounts ALTER COLUMN account_type SET DEFAULT 'demo'::accounttype")

    # Step 5: add raw_password for MT5 terminal credentials (never returned in API)
    op.add_column('accounts',
        sa.Column('raw_password', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('accounts', 'raw_password')

    op.execute("ALTER TABLE accounts ALTER COLUMN account_type DROP DEFAULT")
    op.execute("ALTER TABLE accounts ALTER COLUMN account_type TYPE VARCHAR(8) USING account_type::VARCHAR(8)")
    op.execute("ALTER TABLE accounts ALTER COLUMN account_type SET DEFAULT 'demo'::character varying")
    op.execute("DROP TYPE accounttype")
