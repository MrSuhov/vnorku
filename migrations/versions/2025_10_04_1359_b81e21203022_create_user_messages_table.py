"""create_user_messages_table

Revision ID: b81e21203022
Revises: 5c66a10c830c
Create Date: 2025-10-04 13:59:51.274865

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b81e21203022'
down_revision = '5c66a10c830c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Создаём таблицу user_messages для логирования всех отправленных сообщений
    op.create_table(
        'user_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('chat_id', sa.String(), nullable=False),
        sa.Column('message_text', sa.Text(), nullable=False),
        sa.Column('parse_mode', sa.String(), nullable=True),
        sa.Column('disable_web_page_preview', sa.Boolean(), nullable=True),
        sa.Column('reply_to_message_id', sa.Integer(), nullable=True),
        sa.Column('response_status', sa.Integer(), nullable=True),
        sa.Column('response_body', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE')
    )
    
    # Индексы для быстрого поиска
    op.create_index('ix_user_messages_order_id', 'user_messages', ['order_id'])
    op.create_index('ix_user_messages_created_at', 'user_messages', ['created_at'])
    op.create_index('ix_user_messages_chat_id', 'user_messages', ['chat_id'])


def downgrade() -> None:
    op.drop_index('ix_user_messages_chat_id')
    op.drop_index('ix_user_messages_created_at')
    op.drop_index('ix_user_messages_order_id')
    op.drop_table('user_messages')
