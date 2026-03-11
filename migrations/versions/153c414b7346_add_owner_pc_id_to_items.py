"""add owner_pc_id to items

Revision ID: 153c414b7346
Revises: d73d7314d9e4
Create Date: 2026-03-11 15:50:11.751132

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '153c414b7346'
down_revision = 'd73d7314d9e4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('owner_pc_id', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.drop_column('owner_pc_id')
