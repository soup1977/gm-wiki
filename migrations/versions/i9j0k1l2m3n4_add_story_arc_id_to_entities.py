"""Add story_arc_id FK to npcs, locations, quests, items

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa


revision = 'i9j0k1l2m3n4'
down_revision = 'h8i9j0k1l2m3'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite doesn't support ALTER TABLE with FK constraints; add as plain Integer columns.
    # SQLAlchemy enforces the relationship at the Python layer.
    op.add_column('npcs',      sa.Column('story_arc_id', sa.Integer(), nullable=True))
    op.add_column('locations', sa.Column('story_arc_id', sa.Integer(), nullable=True))
    op.add_column('quests',    sa.Column('story_arc_id', sa.Integer(), nullable=True))
    op.add_column('items',     sa.Column('story_arc_id', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('items',     'story_arc_id')
    op.drop_column('quests',    'story_arc_id')
    op.drop_column('locations', 'story_arc_id')
    op.drop_column('npcs',      'story_arc_id')
