"""add user role, campaign memberships, room is_revealed

Revision ID: 8de76c379d9e
Revises: 153c414b7346
Create Date: 2026-03-11 16:06:27.270269

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8de76c379d9e'
down_revision = '153c414b7346'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('campaign_memberships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=True),
        sa.Column('joined_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('campaign_id', 'user_id', name='uq_campaign_member')
    )
    with op.batch_alter_table('adventure_room', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_revealed', sa.Boolean(), nullable=True))

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('role')

    with op.batch_alter_table('adventure_room', schema=None) as batch_op:
        batch_op.drop_column('is_revealed')

    op.drop_table('campaign_memberships')
