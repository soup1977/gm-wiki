"""add adventure_pc_link table

Revision ID: c517384fc662
Revises: 8de76c379d9e
Create Date: 2026-03-11 16:20:20.902592

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c517384fc662'
down_revision = '8de76c379d9e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('adventure_pc_link',
        sa.Column('adventure_id', sa.Integer(), nullable=False),
        sa.Column('pc_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['adventure_id'], ['adventure.id'], ),
        sa.ForeignKeyConstraint(['pc_id'], ['player_characters.id'], ),
        sa.PrimaryKeyConstraint('adventure_id', 'pc_id')
    )


def downgrade():
    op.drop_table('adventure_pc_link')
