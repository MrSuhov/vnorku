"""add_over_order_percent_to_lsd_stocks

Revision ID: 22abe6600c94
Revises: 7d28f7404733
Create Date: 2025-09-27 13:41:03.524273

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '22abe6600c94'
down_revision = '7d28f7404733'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поле over_order_percent в таблицу lsd_stocks
    op.add_column('lsd_stocks', sa.Column('over_order_percent', sa.Integer(), nullable=True))
    
    # Обновляем существующие записи значениями от пользователей
    op.execute("""
        UPDATE lsd_stocks 
        SET over_order_percent = users.over_order_percent
        FROM orders
        JOIN users ON orders.user_id = users.id
        WHERE lsd_stocks.order_id = orders.id
    """)


def downgrade() -> None:
    # Удаляем поле при откате миграции
    op.drop_column('lsd_stocks', 'over_order_percent')
