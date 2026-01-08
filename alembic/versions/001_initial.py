"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_user_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_user_id'),
    )
    op.create_index('ix_users_telegram_user_id', 'users', ['telegram_user_id'])
    
    # Create templates table
    op.create_table(
        'templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('target_chat_id', sa.String(128), nullable=False),
        sa.Column('frequency_hours', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('in_progress', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_templates_user_id', 'templates', ['user_id'])
    op.create_index('ix_template_user_active', 'templates', ['user_id', 'is_active'])
    op.create_index('ix_template_scheduler', 'templates', ['is_active', 'in_progress', 'last_run_at'])
    
    # Create template_sources table
    op.create_table(
        'template_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('source_identifier', sa.String(128), nullable=False),
        sa.Column('source_chat_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['template_id'], ['templates.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create run_logs table
    op.create_table(
        'run_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(32), nullable=False, server_default='pending'),
        sa.Column('messages_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['template_id'], ['templates.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_run_logs_template_id', 'run_logs', ['template_id'])
    op.create_index('ix_runlog_template_status', 'run_logs', ['template_id', 'status'])
    
    # Create bot_chats table
    op.create_table(
        'bot_chats',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(256), nullable=True),
        sa.Column('username', sa.String(128), nullable=True),
        sa.Column('chat_type', sa.String(32), nullable=False),
        sa.Column('access_hash', sa.BigInteger(), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', 'user_id'),
    )


def downgrade() -> None:
    op.drop_table('bot_chats')
    op.drop_index('ix_runlog_template_status', table_name='run_logs')
    op.drop_index('ix_run_logs_template_id', table_name='run_logs')
    op.drop_table('run_logs')
    op.drop_table('template_sources')
    op.drop_index('ix_template_scheduler', table_name='templates')
    op.drop_index('ix_template_user_active', table_name='templates')
    op.drop_index('ix_templates_user_id', table_name='templates')
    op.drop_table('templates')
    op.drop_index('ix_users_telegram_user_id', table_name='users')
    op.drop_table('users')







