"""remove_delivery_fee_and_free_delivery_threshold

Revision ID: e8f9a1b2c3d4
Revises: d1810b6eed17
Create Date: 2025-09-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8f9a1b2c3d4'
down_revision = 'd1810b6eed17'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Сначала пересоздаём view без этих полей
    op.execute("DROP VIEW IF EXISTS fprice_lsd_order")
    
    op.execute("""
        CREATE VIEW fprice_lsd_order AS
        SELECT DISTINCT ON (oi.order_id, oi.id)
            oi.order_id,
            oi.id AS order_item_id,
            oi.product_name AS requested_product,
            c.display_name AS delivery_service,
            c.name AS lsd_name,
            s.found_name,
            s.found_unit,
            s.found_quantity,
            s.base_unit,
            s.base_quantity,
            s.price,
            s.fprice,
            s.tprice,
            s.product_url,
            s.search_query,
            s.match_score,
            oi.requested_quantity,
            oi.requested_unit,
            oi.requested_quantity / NULLIF(s.base_quantity, 0) AS order_quantity_in_items,
            c.min_order_amount
        FROM lsd_stocks s
        JOIN lsd_configs c ON c.id = s.lsd_config_id
        JOIN order_items oi ON oi.id = s.order_item_id
        WHERE s.match_score > 0.6
        ORDER BY oi.order_id, oi.id, s.fprice, s.match_score DESC
    """)
    
    # Теперь удаляем поля из таблицы
    op.drop_column('lsd_configs', 'delivery_fee')
    op.drop_column('lsd_configs', 'free_delivery_threshold')


def downgrade() -> None:
    # Возвращаем поля
    op.add_column('lsd_configs', sa.Column('free_delivery_threshold', sa.NUMERIC(precision=10, scale=2), nullable=True))
    op.add_column('lsd_configs', sa.Column('delivery_fee', sa.NUMERIC(precision=10, scale=2), nullable=True))
    
    # Пересоздаём view с этими полями
    op.execute("DROP VIEW IF EXISTS fprice_lsd_order")
    
    op.execute("""
        CREATE VIEW fprice_lsd_order AS
        SELECT DISTINCT ON (oi.order_id, oi.id)
            oi.order_id,
            oi.id AS order_item_id,
            oi.product_name AS requested_product,
            c.display_name AS delivery_service,
            c.name AS lsd_name,
            s.found_name,
            s.found_unit,
            s.found_quantity,
            s.base_unit,
            s.base_quantity,
            s.price,
            s.fprice,
            s.tprice,
            s.product_url,
            s.search_query,
            s.match_score,
            oi.requested_quantity,
            oi.requested_unit,
            oi.requested_quantity / NULLIF(s.base_quantity, 0) AS order_quantity_in_items,
            c.min_order_amount,
            c.delivery_fee,
            c.free_delivery_threshold
        FROM lsd_stocks s
        JOIN lsd_configs c ON c.id = s.lsd_config_id
        JOIN order_items oi ON oi.id = s.order_item_id
        WHERE s.match_score > 0.6
        ORDER BY oi.order_id, oi.id, s.fprice, s.match_score DESC
    """)
