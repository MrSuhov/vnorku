"""recreate_fprice_lsd_order_view_with_correct_logic

Revision ID: 10b5cc8ecb13
Revises: f05448bfddb0
Create Date: 2025-09-25 11:54:53.731583

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '10b5cc8ecb13'
down_revision = 'f05448bfddb0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Удаляем старый view
    op.execute("DROP VIEW IF EXISTS fprice_lsd_order")
    
    # Создаем новый view с правильной логикой
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
        WHERE s.match_score > 0.0
        ORDER BY 
            oi.order_id,
            oi.id,
            s.fprice ASC,
            s.match_score DESC
    """)


def downgrade() -> None:
    # Восстанавливаем старый view
    op.execute("DROP VIEW IF EXISTS fprice_lsd_order")
    
    op.execute("""
        CREATE VIEW fprice_lsd_order AS
        SELECT DISTINCT ON (s.search_query) 
            c.display_name AS delivery_service,
            s.found_name,
            s.found_unit,
            s.found_quantity,
            s.price,
            s.fprice,
            s.product_url,
            s.search_query,
            s.match_score,
            s.base_unit,
            s.base_quantity,
            s.min_order_amount,
            oi.requested_quantity / NULLIF(s.base_quantity, 0) AS order_quantity,
            oi.order_id
        FROM lsd_stocks s
        JOIN lsd_configs c ON c.id = s.lsd_config_id
        JOIN order_items oi ON oi.id = s.order_item_id
        WHERE s.match_score > 0.8
        ORDER BY s.search_query, s.fprice, s.match_score DESC, s.min_order_amount DESC
    """)
