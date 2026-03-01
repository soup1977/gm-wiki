"""Add is_player_visible, milestones, progress_pct to adventure_site

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-02-28
"""
from alembic import op
import sqlalchemy as sa


revision = 'h8i9j0k1l2m3'
down_revision = 'g7h8i9j0k1l2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('adventure_site', sa.Column('is_player_visible', sa.Boolean(), nullable=True, server_default='0'))
    op.add_column('adventure_site', sa.Column('milestones', sa.Text(), nullable=True))
    op.add_column('adventure_site', sa.Column('progress_pct', sa.Integer(), nullable=True, server_default='0'))


def downgrade():
    op.drop_column('adventure_site', 'progress_pct')
    op.drop_column('adventure_site', 'milestones')
    op.drop_column('adventure_site', 'is_player_visible')
