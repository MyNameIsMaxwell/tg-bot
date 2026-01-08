"""Add custom_prompt to templates

Revision ID: 002
Revises: 001
Create Date: 2024-12-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('templates', sa.Column('custom_prompt', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('templates', 'custom_prompt')






