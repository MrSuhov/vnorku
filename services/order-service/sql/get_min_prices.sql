-- Получение товаров с минимальными ценами для PDF-отчета
-- Параметры: order_id
-- 
-- ЛОГИКА:
-- 1. Фильтруем lsd_stocks по match_score > 0.75 и order_item_ids_quantity > 0 (как в fprice_optimizer)
-- 2. Для каждого товара находим минимальный fprice среди ВСЕХ ЛСД
-- 3. Показываем ЛСД с этим минимальным fprice
-- 4. Если несколько ЛСД имеют одинаковый минимальный fprice, показываем все через запятую

WITH params AS (
    -- Те же параметры фильтрации что и в fprice_optimizer
    SELECT 0.75 AS match_score_threshold
),
stocks_filtered AS (
    -- Фильтруем stocks по тем же правилам что и fprice_optimizer
    SELECT 
        ls.id,
        ls.order_item_id,
        ls.lsd_config_id,
        ls.price,
        ls.fprice,
        ls.base_unit,
        ls.base_quantity,
        ls.order_item_ids_quantity,
        ls.order_item_ids_cost
    FROM lsd_stocks ls
    CROSS JOIN params p
    WHERE ls.order_id = :order_id
      AND ls.match_score > p.match_score_threshold
      AND ls.order_item_ids_quantity > 0
),
min_fprice_per_item AS (
    -- Находим минимальный fprice для каждого order_item среди ВСЕХ ЛСД
    SELECT 
        sf.order_item_id,
        MIN(sf.fprice) as min_fprice
    FROM stocks_filtered sf
    GROUP BY sf.order_item_id
),
best_items_per_lsd AS (
    -- Для каждого ЛСД берем лучшее (минимальное по fprice) предложение для каждого товара
    SELECT DISTINCT ON (sf.lsd_config_id, sf.order_item_id)
        sf.order_item_id,
        sf.lsd_config_id,
        sf.price,
        sf.fprice,
        sf.base_unit,
        sf.base_quantity,
        sf.order_item_ids_quantity,
        sf.order_item_ids_cost
    FROM stocks_filtered sf
    ORDER BY sf.lsd_config_id, sf.order_item_id, sf.fprice ASC, sf.price ASC, sf.id
),
items_with_min_price AS (
    -- Выбираем только те ЛСД, которые имеют минимальный fprice для товара
    SELECT 
        bi.order_item_id,
        oi.product_name,
        oi.requested_quantity,
        oi.requested_unit,
        bi.lsd_config_id,
        lc.name as lsd_name,
        bi.fprice,
        bi.base_quantity,
        bi.base_unit,
        bi.price,
        mf.min_fprice,
        bi.order_item_ids_cost
    FROM best_items_per_lsd bi
    JOIN order_items oi ON oi.id = bi.order_item_id
    JOIN lsd_configs lc ON lc.id = bi.lsd_config_id
    JOIN min_fprice_per_item mf ON mf.order_item_id = bi.order_item_id
    WHERE bi.fprice = mf.min_fprice
)
SELECT
    order_item_id,
    product_name,
    STRING_AGG(DISTINCT lsd_name, ', ' ORDER BY lsd_name) as lsd_names,
    min_fprice as fprice,
    MAX(base_unit) as base_unit,
    MAX(base_quantity) as base_quantity,
    MAX(requested_quantity) as requested_quantity,
    MAX(requested_unit) as requested_unit,
    MAX(price) as price,
    MAX(base_unit) as found_unit,
    MAX(order_item_ids_cost) as order_item_ids_cost
FROM items_with_min_price
GROUP BY order_item_id, product_name, min_fprice
ORDER BY product_name;
