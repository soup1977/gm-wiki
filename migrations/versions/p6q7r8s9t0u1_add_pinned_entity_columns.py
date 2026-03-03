"""Add pinned entity columns to sessions

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'p6q7r8s9t0u1'
down_revision = 'o5p6q7r8s9t0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pinned_location_ids', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('pinned_quest_ids', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('pinned_item_ids', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.drop_column('pinned_item_ids')
        batch_op.drop_column('pinned_quest_ids')
        batch_op.drop_column('pinned_location_ids')
