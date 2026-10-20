"""add thinking and sources to messages

Revision ID: c3d9f1a2b4e6
Revises: 9796c818ec00
Create Date: 2026-10-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d9f1a2b4e6'
down_revision: Union[str, Sequence[str], None] = '9796c818ec00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('messages', sa.Column('thinking', sa.Text(), nullable=True))
    op.add_column('messages', sa.Column('sources', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('messages', 'sources')
    op.drop_column('messages', 'thinking')
