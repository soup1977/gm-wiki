"""add adventure_quest_link table

Revision ID: 9d89987dd62c
Revises: e73a0ac1d119
Create Date: 2026-03-11 15:18:02.847571

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9d89987dd62c'
down_revision = 'e73a0ac1d119'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('adventure_quest_link',
        sa.Column('adventure_id', sa.Integer(), nullable=False),
        sa.Column('quest_id',     sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['adventure_id'], ['adventure.id'], ),
        sa.ForeignKeyConstraint(['quest_id'],     ['quests.id'],   ),
        sa.PrimaryKeyConstraint('adventure_id', 'quest_id')
    )


def downgrade():
    op.drop_table('adventure_quest_link')
