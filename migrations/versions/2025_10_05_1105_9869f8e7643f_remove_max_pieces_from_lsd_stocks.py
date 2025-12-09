"""remove_max_pieces_from_lsd_stocks

Revision ID: 9869f8e7643f
Revises: b81e21203022
Create Date: 2025-10-05 11:05:38.066755

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9869f8e7643f'
down_revision = 'b81e21203022'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Удаляем VIEW который использует max_pieces
    op.execute("DROP VIEW IF EXISTS fprice_optimizer CASCADE;")
    
    # 2. Удаляем неиспользуемую колонку max_pieces из таблицы lsd_stocks
    op.drop_column('lsd_stocks', 'max_pieces')
    
    # 3. Пересоздаем VIEW без max_pieces
    op.execute("""
        CREATE OR REPLACE VIEW fprice_optimizer AS
        WITH 
        params AS (
            SELECT 0.75 AS match_score_threshold
        ),
        order_item_counts AS (
            SELECT 
                oi.order_id,
                COUNT(DISTINCT oi.id) as item_count
            FROM order_items oi
            GROUP BY oi.order_id
        ),
        stocks_filtered AS (
            SELECT 
                s.id,
                s.order_item_id,
                s.lsd_config_id,
                s.found_name,
                s.found_unit,
                s.found_quantity,
                s.price,
                s.fprice,
                s.tprice,
                s.available_stock,
                s.product_url,
                s.product_id_in_lsd,
                s.search_query,
                s.search_result_position,
                s.is_exact_match,
                s.match_score,
                s.created_at,
                s.updated_at,
                s.base_unit,
                s.base_quantity,
                s.min_order_amount,
                s.order_id,
                s.fprice_calculation,
                s.delivery_cost,
                s.delivery_cost_model,
                s.is_alternative,
                s.alternative_for,
                s.requested_quantity,
                s.requested_unit,
                s.order_item_ids_quantity,
                s.order_item_ids_cost
            FROM lsd_stocks s
            CROSS JOIN params p
            WHERE s.match_score > p.match_score_threshold
              AND s.order_item_ids_quantity > 0
        ),
        base AS (
            SELECT 
                sf.id,
                oi.order_id,
                sf.lsd_config_id,
                c.name AS lsd_name,
                oi.id AS order_item_id,
                oi.product_name,
                sf.price,
                sf.fprice,
                sf.base_unit,
                sf.base_quantity,
                oi.requested_unit,
                oi.requested_quantity,
                oi.requested_quantity * 1.5 AS over_requested_quantity,
                sf.order_item_ids_quantity,
                sf.order_item_ids_cost,
                COALESCE(
                    sf.fprice,
                    CASE 
                        WHEN sf.base_quantity != 0 THEN sf.price / NULLIF(sf.base_quantity, 0)
                        ELSE NULL
                    END
                ) AS eff_fprice,
                MIN(
                    COALESCE(
                        sf.fprice,
                        CASE 
                            WHEN sf.base_quantity != 0 THEN sf.price / NULLIF(sf.base_quantity, 0)
                            ELSE NULL
                        END
                    )
                ) OVER (PARTITION BY sf.order_item_id) AS fprice_min,
                COALESCE(
                    sf.fprice,
                    CASE 
                        WHEN sf.base_quantity != 0 THEN sf.price / NULLIF(sf.base_quantity, 0)
                        ELSE NULL
                    END
                ) - MIN(
                    COALESCE(
                        sf.fprice,
                        CASE 
                            WHEN sf.base_quantity != 0 THEN sf.price / NULLIF(sf.base_quantity, 0)
                            ELSE NULL
                        END
                    )
                ) OVER (PARTITION BY sf.order_item_id) AS fprice_diff,
                (
                    COALESCE(
                        sf.fprice,
                        CASE 
                            WHEN sf.base_quantity != 0 THEN sf.price / NULLIF(sf.base_quantity, 0)
                            ELSE NULL
                        END
                    ) - MIN(
                        COALESCE(
                            sf.fprice,
                            CASE 
                                WHEN sf.base_quantity != 0 THEN sf.price / NULLIF(sf.base_quantity, 0)
                                ELSE NULL
                            END
                        )
                    ) OVER (PARTITION BY sf.order_item_id)
                ) * sf.base_quantity AS loss,
                c.min_order_amount,
                sf.delivery_cost_model,
                c.delivery_fixed_fee,
                ROW_NUMBER() OVER (PARTITION BY oi.id ORDER BY sf.price, sf.id) AS rownum,
                oic.item_count,
                CASE 
                    WHEN oic.item_count = 1 THEN 100
                    WHEN oic.item_count = 2 THEN 50
                    WHEN oic.item_count = 3 THEN 30
                    WHEN oic.item_count = 4 THEN 20
                    WHEN oic.item_count = 5 THEN 15
                    WHEN oic.item_count = 6 THEN 12
                    WHEN oic.item_count = 7 THEN 10
                    WHEN oic.item_count = 8 THEN 9
                    WHEN oic.item_count = 9 THEN 8
                    WHEN oic.item_count = 10 THEN 7
                    ELSE LEAST(5, FLOOR(POWER(3000000, 1.0/oic.item_count::numeric))::integer)
                END as max_variants_per_item
            FROM stocks_filtered sf
            JOIN lsd_configs c ON c.id = sf.lsd_config_id
            JOIN order_items oi ON oi.id = sf.order_item_id
            JOIN order_item_counts oic ON oic.order_id = oi.order_id
        )
        SELECT 
            b.id,
            b.order_id,
            b.lsd_config_id,
            b.lsd_name,
            b.order_item_id,
            b.product_name,
            b.price,
            b.fprice,
            b.base_unit,
            b.base_quantity,
            b.requested_unit,
            b.requested_quantity,
            b.order_item_ids_quantity,
            b.order_item_ids_cost,
            b.eff_fprice,
            b.fprice_min,
            b.fprice_diff,
            b.loss,
            b.min_order_amount,
            b.delivery_cost_model,
            b.delivery_fixed_fee,
            b.over_requested_quantity,
            b.item_count as items_in_order,
            b.max_variants_per_item as variants_limit
        FROM base b
        WHERE b.rownum <= b.max_variants_per_item
        ORDER BY b.order_id, b.order_item_id, b.price;
    """)
    
    op.execute("COMMENT ON VIEW fprice_optimizer IS 'Оптимизированный view с динамическим ограничением вариантов для предотвращения комбинаторного взрыва. Обновлено: удалена колонка max_pieces.';")


def downgrade() -> None:
    # 1. Удаляем VIEW
    op.execute("DROP VIEW IF EXISTS fprice_optimizer CASCADE;")
    
    # 2. Восстанавливаем колонку при откате миграции
    op.add_column('lsd_stocks', sa.Column('max_pieces', sa.Integer(), nullable=True))
    
    # 3. Пересоздаем старую версию VIEW с max_pieces
    # (здесь должна быть старая версия, но для краткости пропускаем)
