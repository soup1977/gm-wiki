"""Add users table and campaign.user_id

Revision ID: 8ba278f50b96
Revises: f6a7b8c9d0e1
Create Date: 2026-02-27 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '8ba278f50b96'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('password_hash', sa.String(length=256), nullable=False),
        sa.Column('is_admin', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username')
    )
    with op.batch_alter_table('campaigns') as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_campaigns_user_id', 'users', ['user_id'], ['id'])


def downgrade():
    with op.batch_alter_table('campaigns') as batch_op:
        batch_op.drop_constraint('fk_campaigns_user_id', type_='foreignkey')
        batch_op.drop_column('user_id')
    op.drop_table('users')
