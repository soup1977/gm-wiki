"""add campaign is_public flag

Revision ID: 99127a9ff03e
Revises: c517384fc662
Create Date: 2026-03-11 16:23:38.278814

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '99127a9ff03e'
down_revision = 'c517384fc662'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_public', sa.Boolean(), nullable=True))


def downgrade():
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.drop_column('is_public')
