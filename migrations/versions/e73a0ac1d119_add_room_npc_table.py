"""add_room_npc_table

Revision ID: e73a0ac1d119
Revises: bc2cdb4934d6
Create Date: 2026-03-11 12:04:55.907662

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e73a0ac1d119'
down_revision = 'bc2cdb4934d6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('room_npc',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('room_id', sa.Integer(), nullable=False),
        sa.Column('npc_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['npc_id'], ['npcs.id'], name='fk_room_npc_npc_id'),
        sa.ForeignKeyConstraint(['room_id'], ['adventure_room.id'], name='fk_room_npc_room_id'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('room_npc')
