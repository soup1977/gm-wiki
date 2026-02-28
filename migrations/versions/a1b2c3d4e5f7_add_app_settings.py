"""Add app_settings table for database-backed configuration

Revision ID: a1b2c3d4e5f7
Revises: 8ba278f50b96
Create Date: 2026-02-27 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import os

revision = 'a1b2c3d4e5f7'
down_revision = '8ba278f50b96'
branch_labels = None
depends_on = None


def upgrade():
    # Create the settings table
    settings = op.create_table('app_settings',
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('key')
    )

    # Seed default values
    defaults = [
        {'key': 'ai_provider', 'value': 'none'},
        {'key': 'ollama_url', 'value': 'http://localhost:11434'},
        {'key': 'ollama_model', 'value': 'llama3.1'},
        {'key': 'anthropic_api_key', 'value': ''},
        {'key': 'sd_url', 'value': ''},
    ]

    # If ANTHROPIC_API_KEY was set in the environment, migrate it
    env_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if env_key:
        for d in defaults:
            if d['key'] == 'ai_provider':
                d['value'] = 'anthropic'
            if d['key'] == 'anthropic_api_key':
                d['value'] = env_key

    op.bulk_insert(settings, defaults)


def downgrade():
    op.drop_table('app_settings')
