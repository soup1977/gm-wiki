"""Add ICRPG catalog models (worlds, life forms, types, abilities, loot, spells,
milestone paths) and character sheet models (sheet, char loot, char abilities).

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa


revision = 'k1l2m3n4o5p6'
down_revision = 'j0k1l2m3n4o5'
branch_labels = None
depends_on = None


def upgrade():
    # ── Catalog tables ──────────────────────────────────────────

    op.create_table('icrpg_worlds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_builtin', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('icrpg_life_forms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('world_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('bonuses', sa.JSON(), nullable=True),
        sa.Column('is_builtin', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['world_id'], ['icrpg_worlds.id']),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('icrpg_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('world_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_builtin', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['world_id'], ['icrpg_worlds.id']),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('icrpg_abilities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('type_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('ability_kind', sa.String(length=20), nullable=False),
        sa.Column('is_builtin', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=True, server_default='0'),
        sa.ForeignKeyConstraint(['type_id'], ['icrpg_types.id']),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('icrpg_spells',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('spell_type', sa.String(length=50), nullable=True),
        sa.Column('casting_stat', sa.String(length=10), nullable=True),
        sa.Column('level', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('target', sa.String(length=100), nullable=True),
        sa.Column('duration', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_builtin', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('icrpg_loot_defs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('world_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('loot_type', sa.String(length=50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('effects', sa.JSON(), nullable=True),
        sa.Column('slot_cost', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('coin_cost', sa.Integer(), nullable=True),
        sa.Column('is_starter', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('is_builtin', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['world_id'], ['icrpg_worlds.id']),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('icrpg_starting_loot',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('type_id', sa.Integer(), nullable=False),
        sa.Column('loot_def_id', sa.Integer(), nullable=True),
        sa.Column('spell_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['type_id'], ['icrpg_types.id']),
        sa.ForeignKeyConstraint(['loot_def_id'], ['icrpg_loot_defs.id']),
        sa.ForeignKeyConstraint(['spell_id'], ['icrpg_spells.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('icrpg_milestone_paths',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tiers', sa.JSON(), nullable=True),
        sa.Column('is_builtin', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # ── Character sheet tables ──────────────────────────────────

    op.create_table('icrpg_character_sheets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pc_id', sa.Integer(), nullable=False),
        sa.Column('world_id', sa.Integer(), nullable=True),
        sa.Column('life_form_id', sa.Integer(), nullable=True),
        sa.Column('type_id', sa.Integer(), nullable=True),
        sa.Column('story', sa.String(length=500), nullable=True),
        sa.Column('stat_str', sa.Integer(), server_default='0'),
        sa.Column('stat_dex', sa.Integer(), server_default='0'),
        sa.Column('stat_con', sa.Integer(), server_default='0'),
        sa.Column('stat_int', sa.Integer(), server_default='0'),
        sa.Column('stat_wis', sa.Integer(), server_default='0'),
        sa.Column('stat_cha', sa.Integer(), server_default='0'),
        sa.Column('effort_basic', sa.Integer(), server_default='0'),
        sa.Column('effort_weapons', sa.Integer(), server_default='0'),
        sa.Column('effort_guns', sa.Integer(), server_default='0'),
        sa.Column('effort_magic', sa.Integer(), server_default='0'),
        sa.Column('effort_ultimate', sa.Integer(), server_default='0'),
        sa.Column('hearts_max', sa.Integer(), server_default='1'),
        sa.Column('hp_current', sa.Integer(), server_default='10'),
        sa.Column('hero_coin', sa.Boolean(), server_default='0'),
        sa.Column('dying_timer', sa.Integer(), server_default='0'),
        sa.Column('nat20_count', sa.Integer(), server_default='0'),
        sa.Column('mastery_count', sa.Integer(), server_default='0'),
        sa.Column('coin', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['pc_id'], ['player_characters.id']),
        sa.ForeignKeyConstraint(['world_id'], ['icrpg_worlds.id']),
        sa.ForeignKeyConstraint(['life_form_id'], ['icrpg_life_forms.id']),
        sa.ForeignKeyConstraint(['type_id'], ['icrpg_types.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pc_id')
    )

    op.create_table('icrpg_char_loot',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sheet_id', sa.Integer(), nullable=False),
        sa.Column('loot_def_id', sa.Integer(), nullable=True),
        sa.Column('spell_id', sa.Integer(), nullable=True),
        sa.Column('slot', sa.String(length=20), server_default='carried'),
        sa.Column('custom_name', sa.String(length=200), nullable=True),
        sa.Column('custom_desc', sa.Text(), nullable=True),
        sa.Column('display_order', sa.Integer(), server_default='0'),
        sa.ForeignKeyConstraint(['sheet_id'], ['icrpg_character_sheets.id']),
        sa.ForeignKeyConstraint(['loot_def_id'], ['icrpg_loot_defs.id']),
        sa.ForeignKeyConstraint(['spell_id'], ['icrpg_spells.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('icrpg_char_abilities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sheet_id', sa.Integer(), nullable=False),
        sa.Column('ability_id', sa.Integer(), nullable=True),
        sa.Column('custom_name', sa.String(length=200), nullable=True),
        sa.Column('custom_desc', sa.Text(), nullable=True),
        sa.Column('ability_kind', sa.String(length=20), nullable=True),
        sa.Column('display_order', sa.Integer(), server_default='0'),
        sa.ForeignKeyConstraint(['sheet_id'], ['icrpg_character_sheets.id']),
        sa.ForeignKeyConstraint(['ability_id'], ['icrpg_abilities.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('icrpg_char_abilities')
    op.drop_table('icrpg_char_loot')
    op.drop_table('icrpg_character_sheets')
    op.drop_table('icrpg_milestone_paths')
    op.drop_table('icrpg_starting_loot')
    op.drop_table('icrpg_loot_defs')
    op.drop_table('icrpg_spells')
    op.drop_table('icrpg_abilities')
    op.drop_table('icrpg_types')
    op.drop_table('icrpg_life_forms')
    op.drop_table('icrpg_worlds')
