"""add optimization timestamps to orders

Revision ID: optimization_timestamps
Revises: 
Create Date: 2025-09-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'optimization_timestamps'
down_revision = None  # Укажи предыдущую ревизию если нужно
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем timestamp поля для отслеживания этапов оптимизации
    op.add_column('orders', 
        sa.Column('optimization_started_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column('orders', 
        sa.Column('optimization_completed_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column('orders', 
        sa.Column('results_sent_at', sa.DateTime(timezone=True), nullable=True)
    )
    
    # Создаём индексы для быстрого поиска
    op.create_index('idx_orders_optimization_started', 
                    'orders', 
                    ['optimization_started_at'])
    op.create_index('idx_orders_optimization_completed', 
                    'orders', 
                    ['optimization_completed_at'])


def downgrade():
    # Удаляем индексы
    op.drop_index('idx_orders_optimization_completed', table_name='orders')
    op.drop_index('idx_orders_optimization_started', table_name='orders')
    
    # Удаляем колонки
    op.drop_column('orders', 'results_sent_at')
    op.drop_column('orders', 'optimization_completed_at')
    op.drop_column('orders', 'optimization_started_at')
