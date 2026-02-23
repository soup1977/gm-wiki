"""Add BestiaryEntry and MonsterInstance models

Revision ID: a1b2c3d4e5f6
Revises: 8698824ea5c9
Create Date: 2026-02-22 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '8698824ea5c9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('bestiary_entries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('system', sa.String(length=50), nullable=True),
    sa.Column('cr_level', sa.String(length=20), nullable=True),
    sa.Column('stat_block', sa.Text(), nullable=False),
    sa.Column('image_path', sa.String(length=255), nullable=True),
    sa.Column('source', sa.String(length=100), nullable=True),
    sa.Column('visible_to_players', sa.Boolean(), nullable=True),
    sa.Column('tags', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('monster_instances',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('bestiary_entry_id', sa.Integer(), nullable=False),
    sa.Column('campaign_id', sa.Integer(), nullable=False),
    sa.Column('instance_name', sa.String(length=100), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('promoted_to_npc_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['bestiary_entry_id'], ['bestiary_entries.id'], ),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.ForeignKeyConstraint(['promoted_to_npc_id'], ['npcs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('session_monsters',
    sa.Column('session_id', sa.Integer(), nullable=False),
    sa.Column('monster_instance_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['monster_instance_id'], ['monster_instances.id'], ),
    sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ),
    sa.PrimaryKeyConstraint('session_id', 'monster_instance_id')
    )


def downgrade():
    op.drop_table('session_monsters')
    op.drop_table('monster_instances')
    op.drop_table('bestiary_entries')
