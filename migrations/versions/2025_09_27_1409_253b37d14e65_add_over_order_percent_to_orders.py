"""add_over_order_percent_to_orders

Revision ID: 253b37d14e65
Revises: 845a67137d03
Create Date: 2025-09-27 14:09:XX

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '253b37d14e65'
down_revision = '845a67137d03'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поле over_order_percent в таблицу orders
    op.add_column('orders', sa.Column('over_order_percent', sa.Integer(), nullable=True))
    
    # Обновляем существующие заказы значениями от пользователей
    op.execute("""
        UPDATE orders 
        SET over_order_percent = users.over_order_percent
        FROM users
        WHERE orders.user_id = users.id
    """)


def downgrade() -> None:
    # Удаляем поле при откате миграции
    op.drop_column('orders', 'over_order_percent')
