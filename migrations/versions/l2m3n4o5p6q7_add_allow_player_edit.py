"""Add allow_player_edit toggle to ICRPG character sheets

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa

revision = 'l2m3n4o5p6q7'
down_revision = 'k1l2m3n4o5p6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('icrpg_character_sheets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('allow_player_edit', sa.Boolean(),
                                       server_default='0', nullable=True))


def downgrade():
    with op.batch_alter_table('icrpg_character_sheets', schema=None) as batch_op:
        batch_op.drop_column('allow_player_edit')
