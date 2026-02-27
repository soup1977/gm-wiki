"""Add backstory and gm_hooks to player_characters

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-02-27 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('player_characters', sa.Column('backstory', sa.Text(), nullable=True))
    op.add_column('player_characters', sa.Column('gm_hooks', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('player_characters', 'gm_hooks')
    op.drop_column('player_characters', 'backstory')
