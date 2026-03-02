"""Add basic_loot_count to icrpg_worlds

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'm3n4o5p6q7r8'
down_revision = 'l2m3n4o5p6q7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('icrpg_worlds') as batch_op:
        batch_op.add_column(sa.Column('basic_loot_count', sa.Integer(), server_default='4'))


def downgrade():
    with op.batch_alter_table('icrpg_worlds') as batch_op:
        batch_op.drop_column('basic_loot_count')
