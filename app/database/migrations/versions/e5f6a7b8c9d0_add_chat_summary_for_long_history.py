"""add chat summary for long history

Revision ID: e5f6a7b8c9d0
Revises: c3d9f1a2b4e6
Create Date: 2026-10-19 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'c3d9f1a2b4e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('chats', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('chats', sa.Column('summary_upto', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chats', 'summary_upto')
    op.drop_column('chats', 'summary')
