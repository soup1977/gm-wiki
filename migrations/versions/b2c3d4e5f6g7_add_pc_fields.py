"""Add race_or_ancestry, description, home_location_id, user_id to player_characters

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f7
Create Date: 2026-02-27
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6g7'
down_revision = 'a1b2c3d4e5f7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('player_characters') as batch_op:
        batch_op.add_column(sa.Column('race_or_ancestry', sa.String(200), nullable=True))
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('home_location_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_pc_home_location', 'locations', ['home_location_id'], ['id'])
        batch_op.create_foreign_key('fk_pc_user', 'users', ['user_id'], ['id'])


def downgrade():
    with op.batch_alter_table('player_characters') as batch_op:
        batch_op.drop_constraint('fk_pc_user', type_='foreignkey')
        batch_op.drop_constraint('fk_pc_home_location', type_='foreignkey')
        batch_op.drop_column('user_id')
        batch_op.drop_column('home_location_id')
        batch_op.drop_column('description')
        batch_op.drop_column('race_or_ancestry')
