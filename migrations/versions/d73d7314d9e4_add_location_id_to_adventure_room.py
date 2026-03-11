"""add location_id to adventure_room

Revision ID: d73d7314d9e4
Revises: 9d89987dd62c
Create Date: 2026-03-11 15:26:37.283648

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd73d7314d9e4'
down_revision = '9d89987dd62c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('adventure_room', schema=None) as batch_op:
        batch_op.add_column(sa.Column('location_id', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('adventure_room', schema=None) as batch_op:
        batch_op.drop_column('location_id')
