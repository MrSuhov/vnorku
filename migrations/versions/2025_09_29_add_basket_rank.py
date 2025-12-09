"""add basket_rank to basket_analyses

Revision ID: basket_rank_field
Revises: 
Create Date: 2025-09-29

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'basket_rank_field'
down_revision = None  # Укажи предыдущую ревизию если нужно
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем колонку basket_rank
    op.add_column('basket_analyses', 
        sa.Column('basket_rank', sa.Integer(), nullable=True)
    )
    
    # Создаём индекс для быстрой сортировки
    op.create_index('idx_basket_analyses_order_rank', 
                    'basket_analyses', 
                    ['order_id', 'basket_rank'])


def downgrade():
    # Удаляем индекс
    op.drop_index('idx_basket_analyses_order_rank', table_name='basket_analyses')
    
    # Удаляем колонку
    op.drop_column('basket_analyses', 'basket_rank')
