"""add_adventure_entity_linking_and_session_log

Revision ID: bc2cdb4934d6
Revises: 4fe4af6006d0
Create Date: 2026-03-11 09:37:21.824709

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bc2cdb4934d6'
down_revision = '4fe4af6006d0'
branch_labels = None
depends_on = None


def upgrade():
    # New table: track what happened in each room per session
    op.create_table('adventure_room_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('room_id', sa.Integer(), nullable=False),
        sa.Column('visited', sa.Boolean(), nullable=True),
        sa.Column('gm_notes', sa.Text(), nullable=True),
        sa.Column('creatures_defeated', sa.Boolean(), nullable=True),
        sa.Column('loot_taken', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Adventure: planning notes (free Markdown)
    with op.batch_alter_table('adventure', schema=None) as batch_op:
        batch_op.add_column(sa.Column('planning_notes', sa.Text(), nullable=True))

    # AdventureRoom: persistent cleared state
    with op.batch_alter_table('adventure_room', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_cleared', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('cleared_notes', sa.Text(), nullable=True))

    # Entity adventure_id FKs (all nullable — existing records unaffected)
    with op.batch_alter_table('encounters', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adventure_id', sa.Integer(), nullable=True))

    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adventure_id', sa.Integer(), nullable=True))

    with op.batch_alter_table('locations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adventure_id', sa.Integer(), nullable=True))

    with op.batch_alter_table('npcs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adventure_id', sa.Integer(), nullable=True))

    with op.batch_alter_table('quests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adventure_id', sa.Integer(), nullable=True))

    # Session: link to adventure (set when started from runner)
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adventure_id', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.drop_column('adventure_id')

    with op.batch_alter_table('quests', schema=None) as batch_op:
        batch_op.drop_column('adventure_id')

    with op.batch_alter_table('npcs', schema=None) as batch_op:
        batch_op.drop_column('adventure_id')

    with op.batch_alter_table('locations', schema=None) as batch_op:
        batch_op.drop_column('adventure_id')

    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.drop_column('adventure_id')

    with op.batch_alter_table('encounters', schema=None) as batch_op:
        batch_op.drop_column('adventure_id')

    with op.batch_alter_table('adventure_room', schema=None) as batch_op:
        batch_op.drop_column('cleared_notes')
        batch_op.drop_column('is_cleared')

    with op.batch_alter_table('adventure', schema=None) as batch_op:
        batch_op.drop_column('planning_notes')

    op.drop_table('adventure_room_log')
