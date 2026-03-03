"""Add activity_log table

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa

revision = 'o5p6q7r8s9t0'
down_revision = 'n4o5p6q7r8s9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('activity_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('campaign_id', sa.Integer(), sa.ForeignKey('campaigns.id'), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('entity_name', sa.String(200), nullable=False),
        sa.Column('details', sa.String(200), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_activity_log_timestamp', 'activity_log', ['timestamp'])
    op.create_index('ix_activity_log_campaign_id', 'activity_log', ['campaign_id'])


def downgrade():
    op.drop_index('ix_activity_log_campaign_id')
    op.drop_index('ix_activity_log_timestamp')
    op.drop_table('activity_log')
