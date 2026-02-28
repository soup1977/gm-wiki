"""Add adventure_site, adventure_site_session, adventure_site_tags tables

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-02-28
"""
from alembic import op
import sqlalchemy as sa


revision = 'g7h8i9j0k1l2'
down_revision = 'f6g7h8i9j0k1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('adventure_site',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('subtitle', sa.String(length=300), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('estimated_sessions', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('adventure_site_session',
        sa.Column('adventure_site_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['adventure_site_id'], ['adventure_site.id']),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id']),
        sa.PrimaryKeyConstraint('adventure_site_id', 'session_id')
    )

    op.create_table('adventure_site_tags',
        sa.Column('adventure_site_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['adventure_site_id'], ['adventure_site.id']),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id']),
        sa.PrimaryKeyConstraint('adventure_site_id', 'tag_id')
    )


def downgrade():
    op.drop_table('adventure_site_tags')
    op.drop_table('adventure_site_session')
    op.drop_table('adventure_site')
