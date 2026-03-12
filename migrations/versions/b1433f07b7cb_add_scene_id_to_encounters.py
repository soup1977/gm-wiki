"""Add scene_id to encounters

Revision ID: b1433f07b7cb
Revises: 99127a9ff03e
Create Date: 2026-03-11 19:12:13.999221

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1433f07b7cb'
down_revision = '99127a9ff03e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('encounters', schema=None) as batch_op:
        batch_op.add_column(sa.Column('scene_id', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('encounters', schema=None) as batch_op:
        batch_op.drop_column('scene_id')
