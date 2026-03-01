"""Add story_arc_id FK to encounters

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa


revision = 'j0k1l2m3n4o5'
down_revision = 'i9j0k1l2m3n4'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite doesn't support ALTER TABLE with FK constraints; add as plain Integer column.
    # SQLAlchemy enforces the relationship at the Python layer.
    op.add_column('encounters', sa.Column('story_arc_id', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('encounters', 'story_arc_id')
