"""Add factions table and faction_id to npcs, locations, quests

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-27 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('factions',
        sa.Column('id',          sa.Integer(),    nullable=False),
        sa.Column('campaign_id', sa.Integer(),    nullable=False),
        sa.Column('name',        sa.String(200),  nullable=False),
        sa.Column('description', sa.Text(),       nullable=True),
        sa.Column('disposition', sa.String(50),   nullable=True),
        sa.Column('gm_notes',    sa.Text(),       nullable=True),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_factions_campaign_id', 'factions', ['campaign_id'])

    op.add_column('npcs',      sa.Column('faction_id', sa.Integer(), nullable=True))
    op.add_column('locations', sa.Column('faction_id', sa.Integer(), nullable=True))
    op.add_column('quests',    sa.Column('faction_id', sa.Integer(), nullable=True))

    # SQLite doesn't support ADD CONSTRAINT after creation, so we skip explicit FK
    # constraints here — SQLAlchemy handles this at the ORM level.


def downgrade():
    op.drop_column('quests',    'faction_id')
    op.drop_column('locations', 'faction_id')
    op.drop_column('npcs',      'faction_id')
    op.drop_index('ix_factions_campaign_id', table_name='factions')
    op.drop_table('factions')
