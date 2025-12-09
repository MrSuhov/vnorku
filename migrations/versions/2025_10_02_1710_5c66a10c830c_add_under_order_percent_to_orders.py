"""add_under_order_percent_to_orders

Revision ID: 5c66a10c830c
Revises: 479ab2667c0b
Create Date: 2025-10-02 17:10:48.082044

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5c66a10c830c'
down_revision = '479ab2667c0b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поле under_order_percent в таблицу orders
    op.add_column('orders', sa.Column('under_order_percent', sa.Integer(), nullable=True))
    
    # Обновляем существующие заказы значением 10% (default)
    op.execute("UPDATE orders SET under_order_percent = 10 WHERE under_order_percent IS NULL")


def downgrade() -> None:
    # Удаляем поле при откате миграции
    op.drop_column('orders', 'under_order_percent')
