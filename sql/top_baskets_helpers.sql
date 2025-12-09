-- Вспомогательные функции для удобного использования top_baskets
-- Автор: Korzinka Team
-- Дата: 2025-09-29

-- Функция для получения только детализации товаров
DROP FUNCTION IF EXISTS top_baskets_items(INTEGER, INTEGER);

CREATE OR REPLACE FUNCTION top_baskets_items(
    p_order_id INTEGER,
    p_rank INTEGER
)
RETURNS TABLE(
    lsd_name VARCHAR(100),
    product_name VARCHAR(500),
    original_product_name VARCHAR(500),
    base_quantity NUMERIC(10,3),
    base_unit VARCHAR(10),
    price NUMERIC(10,2),
    order_item_ids_cost NUMERIC(10,2),
    order_item_ids_quantity NUMERIC,
    requested_quantity NUMERIC(10,3),
    requested_unit VARCHAR(20),
    product_url VARCHAR(1000)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.lsd_name,
        t.product_name,
        t.original_product_name,
        t.base_quantity,
        t.base_unit,
        t.price,
        t.order_item_ids_cost,
        t.order_item_ids_quantity,
        t.requested_quantity,
        t.requested_unit,
        t.product_url
    FROM top_baskets(p_order_id, p_rank) t
    WHERE t.result_type = 'ITEMS';
END;
$$ LANGUAGE plpgsql;

-- Функция для получения только сводной информации
DROP FUNCTION IF EXISTS top_baskets_summary(INTEGER, INTEGER);

CREATE OR REPLACE FUNCTION top_baskets_summary(
    p_order_id INTEGER,
    p_rank INTEGER
)
RETURNS TABLE(
    order_id INTEGER,
    basket_rank INTEGER,
    total_goods_cost NUMERIC(10,2),
    total_delivery_cost NUMERIC(10,2),
    total_loss NUMERIC(10,2),
    total_cost NUMERIC(10,2),
    diff_with_rank1 NUMERIC(10,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.order_id,
        t.basket_rank,
        t.total_goods_cost,
        t.total_delivery_cost,
        t.total_loss,
        t.total_cost,
        t.diff_with_rank1
    FROM top_baskets(p_order_id, p_rank) t
    WHERE t.result_type = 'SUMMARY';
END;
$$ LANGUAGE plpgsql;

-- Комментарии
COMMENT ON FUNCTION top_baskets_items(INTEGER, INTEGER) IS 
'Возвращает только детализацию товаров из корзины';

COMMENT ON FUNCTION top_baskets_summary(INTEGER, INTEGER) IS 
'Возвращает только сводную информацию по корзине';

-- Примеры использования:
-- Только товары:
-- SELECT * FROM top_baskets_items(16, 1);

-- Только сводка:
-- SELECT * FROM top_baskets_summary(16, 1);

-- Полная информация:
-- SELECT * FROM top_baskets(16, 1);
