"""add_requested_fields_to_lsd_stocks

Revision ID: 2f648f05f770
Revises: 253b37d14e65
Create Date: 2025-09-27 14:09:XX

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '2f648f05f770'
down_revision = '253b37d14e65'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поля requested_quantity и requested_unit в таблицу lsd_stocks
    op.add_column('lsd_stocks', sa.Column('requested_quantity', sa.Numeric(10, 3), nullable=True))
    op.add_column('lsd_stocks', sa.Column('requested_unit', sa.String(20), nullable=True))
    
    # Обновляем существующие записи значениями из order_items
    op.execute("""
        UPDATE lsd_stocks 
        SET requested_quantity = order_items.requested_quantity,
            requested_unit = order_items.requested_unit
        FROM order_items
        WHERE lsd_stocks.order_item_id = order_items.id
    """)


def downgrade() -> None:
    # Удаляем поля при откате миграции
    op.drop_column('lsd_stocks', 'requested_unit')
    op.drop_column('lsd_stocks', 'requested_quantity')
