"""Add include_world_loot to icrpg_worlds

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa

revision = 'n4o5p6q7r8s9'
down_revision = 'm3n4o5p6q7r8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('icrpg_worlds') as batch_op:
        batch_op.add_column(sa.Column('include_world_loot', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('icrpg_worlds') as batch_op:
        batch_op.drop_column('include_world_loot')
