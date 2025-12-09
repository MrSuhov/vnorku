-- ==============================================================================
-- ТАБЛИЦЫ ДЛЯ ОТЛАДКИ ОПТИМИЗАТОРА
-- ==============================================================================

-- Таблица basket_combinations используется для хранения всех возможных комбинаций
-- Примечание: таблица order_combinations была удалена для унификации

-- Таблица 1: Валидные корзины
DROP TABLE IF EXISTS valid_baskets CASCADE;

CREATE TABLE valid_baskets (
    id SERIAL PRIMARY KEY,
    basket_id BIGINT,
    order_id INTEGER REFERENCES orders(id),
    -- Товар 1
    item_id_1 INTEGER,
    product_1 VARCHAR(500),
    lsd_1 VARCHAR(100),
    lsd_config_1 INTEGER,
    pieces_1 INTEGER,
    base_qty_1 NUMERIC(10,3),
    price_1 NUMERIC(10,2),
    loss_1 NUMERIC,
    -- Товар 2
    item_id_2 INTEGER,
    product_2 VARCHAR(500),
    lsd_2 VARCHAR(100),
    lsd_config_2 INTEGER,
    pieces_2 INTEGER,
    base_qty_2 NUMERIC(10,3),
    price_2 NUMERIC(10,2),
    loss_2 NUMERIC,
    -- Товар 3
    item_id_3 INTEGER,
    product_3 VARCHAR(500),
    lsd_3 VARCHAR(100),
    lsd_config_3 INTEGER,
    pieces_3 INTEGER,
    base_qty_3 NUMERIC(10,3),
    price_3 NUMERIC(10,2),
    loss_3 NUMERIC,
    -- Товар 4
    item_id_4 INTEGER,
    product_4 VARCHAR(500),
    lsd_4 VARCHAR(100),
    lsd_config_4 INTEGER,
    pieces_4 INTEGER,
    base_qty_4 NUMERIC(10,3),
    price_4 NUMERIC(10,2),
    loss_4 NUMERIC,
    -- Метрики
    total_goods_cost NUMERIC(10,2),
    total_loss NUMERIC(10,2),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_valid_baskets_order_id ON valid_baskets(order_id);
CREATE INDEX idx_valid_baskets_basket_id ON valid_baskets(basket_id);
CREATE INDEX idx_valid_baskets_loss ON valid_baskets(total_loss);

COMMENT ON TABLE valid_baskets IS 'Валидные корзины после фильтрации для отладки';

-- View 2: Оптимизированные корзины (топ-N по каждому заказу)
DROP VIEW IF EXISTS optimized_baskets CASCADE;

CREATE VIEW optimized_baskets AS
WITH ranked_baskets AS (
    SELECT 
        vb.*,
        ROW_NUMBER() OVER (
            PARTITION BY vb.order_id 
            ORDER BY vb.total_loss, vb.total_goods_cost
        ) as basket_rank,
        -- TODO: добавить delivery_cost когда будет реализован
        0::NUMERIC(10,2) as total_delivery_cost
    FROM valid_baskets vb
)
SELECT 
    basket_rank,
    order_id,
    basket_id,
    -- Формируем lsd_breakdown как JSON
    jsonb_build_object(
        lsd_1, jsonb_build_object(
            'items', jsonb_build_array(
                jsonb_build_object(
                    'product', product_1,
                    'pieces', pieces_1,
                    'price', price_1,
                    'subtotal', ROUND(pieces_1 * price_1, 2)
                )
            ),
            'subtotal', ROUND(pieces_1 * price_1, 2)
        ),
        lsd_2, jsonb_build_object(
            'items', jsonb_build_array(
                jsonb_build_object(
                    'product', product_2,
                    'pieces', pieces_2,
                    'price', price_2,
                    'subtotal', ROUND(pieces_2 * price_2, 2)
                )
            ),
            'subtotal', ROUND(pieces_2 * price_2, 2)
        ),
        lsd_3, jsonb_build_object(
            'items', jsonb_build_array(
                jsonb_build_object(
                    'product', product_3,
                    'pieces', pieces_3,
                    'price', price_3,
                    'subtotal', ROUND(pieces_3 * price_3, 2)
                )
            ),
            'subtotal', ROUND(pieces_3 * price_3, 2)
        ),
        lsd_4, jsonb_build_object(
            'items', jsonb_build_array(
                jsonb_build_object(
                    'product', product_4,
                    'pieces', pieces_4,
                    'price', price_4,
                    'subtotal', ROUND(pieces_4 * price_4, 2)
                )
            ),
            'subtotal', ROUND(pieces_4 * price_4, 2)
        )
    )::JSON as lsd_breakdown,
    total_goods_cost,
    total_loss,
    '{}'::JSON as delivery_costs,
    total_delivery_cost,
    (total_goods_cost + total_delivery_cost)::NUMERIC(10,2) as total_cost,
    (total_loss + total_delivery_cost)::NUMERIC(10,2) as total_loss_and_delivery
FROM ranked_baskets
WHERE basket_rank <= 3  -- топ-3 для каждого заказа
ORDER BY order_id, basket_rank;

COMMENT ON VIEW optimized_baskets IS 'Топ-3 оптимизированные корзины для каждого заказа';
