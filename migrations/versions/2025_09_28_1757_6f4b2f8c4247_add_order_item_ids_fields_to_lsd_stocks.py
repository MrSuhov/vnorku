"""Add order_item_ids fields to lsd_stocks

Revision ID: 6f4b2f8c4247
Revises: 44b3acf35bf4
Create Date: 2025-09-28 17:57:39.577076

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6f4b2f8c4247'
down_revision = '44b3acf35bf4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем новые поля в таблицу lsd_stocks
    op.add_column('lsd_stocks', sa.Column('order_item_ids_quantity', sa.Integer(), nullable=True))
    op.add_column('lsd_stocks', sa.Column('order_item_ids_cost', sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    # Удаляем поля при откате миграции
    op.drop_column('lsd_stocks', 'order_item_ids_cost')
    op.drop_column('lsd_stocks', 'order_item_ids_quantity')
