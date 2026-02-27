"""Add encounters and encounter_monster tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-27 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('encounters',
        sa.Column('id',             sa.Integer(),     nullable=False),
        sa.Column('campaign_id',    sa.Integer(),     nullable=False),
        sa.Column('session_id',     sa.Integer(),     nullable=True),
        sa.Column('name',           sa.String(200),   nullable=False),
        sa.Column('encounter_type', sa.String(50),    nullable=True),
        sa.Column('status',         sa.String(50),    nullable=True),
        sa.Column('description',    sa.Text(),        nullable=True),
        sa.Column('gm_notes',       sa.Text(),        nullable=True),
        sa.Column('loot_table_id',  sa.Integer(),     nullable=True),
        sa.ForeignKeyConstraint(['campaign_id'],   ['campaigns.id']),
        sa.ForeignKeyConstraint(['session_id'],    ['sessions.id']),
        sa.ForeignKeyConstraint(['loot_table_id'], ['random_tables.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_encounters_campaign_id', 'encounters', ['campaign_id'])
    op.create_index('ix_encounters_session_id',  'encounters', ['session_id'])

    op.create_table('encounter_monster',
        sa.Column('id',                sa.Integer(), nullable=False),
        sa.Column('encounter_id',      sa.Integer(), nullable=False),
        sa.Column('bestiary_entry_id', sa.Integer(), nullable=False),
        sa.Column('count',             sa.Integer(), nullable=False),
        sa.Column('notes',             sa.String(200), nullable=True),
        sa.ForeignKeyConstraint(['encounter_id'],      ['encounters.id']),
        sa.ForeignKeyConstraint(['bestiary_entry_id'], ['bestiary_entries.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('encounter_monster')
    op.drop_index('ix_encounters_session_id',  table_name='encounters')
    op.drop_index('ix_encounters_campaign_id', table_name='encounters')
    op.drop_table('encounters')
