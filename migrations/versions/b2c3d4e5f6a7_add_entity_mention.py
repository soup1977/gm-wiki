"""Add entity_mention table for shortcode back-references

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('entity_mention',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('campaign_id', sa.Integer(), nullable=False),
    sa.Column('source_type', sa.String(length=50), nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('target_type', sa.String(length=50), nullable=False),
    sa.Column('target_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_entity_mention_target', 'entity_mention',
                    ['target_type', 'target_id'], unique=False)
    op.create_index('ix_entity_mention_source', 'entity_mention',
                    ['source_type', 'source_id'], unique=False)


def downgrade():
    op.drop_index('ix_entity_mention_source', table_name='entity_mention')
    op.drop_index('ix_entity_mention_target', table_name='entity_mention')
    op.drop_table('entity_mention')
