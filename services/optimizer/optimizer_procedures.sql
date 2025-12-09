-- ==============================================================================
-- ПРОЦЕДУРЫ ДЛЯ ОПТИМИЗАЦИИ КОРЗИН (С МАТЕРИАЛИЗАЦИЕЙ В ТАБЛИЦЫ)
-- ==============================================================================

-- Удаляем старые версии
DROP PROCEDURE IF EXISTS generate_basket_combinations(INTEGER);
DROP PROCEDURE IF EXISTS generate_valid_baskets(INTEGER);
DROP FUNCTION IF EXISTS optimize_order(INTEGER, INTEGER);

-- ==============================================================================
-- Процедура 1: Генерация всех комбинаций корзин
-- Записывает результат в таблицу basket_combinations
-- ==============================================================================
CREATE OR REPLACE PROCEDURE generate_basket_combinations(p_order_id INTEGER)
LANGUAGE plpgsql
AS $$
BEGIN
    -- Удаляем старые данные для этого заказа
    DELETE FROM basket_combinations WHERE order_id = p_order_id;
    
    -- Генерируем и записываем комбинации
    INSERT INTO basket_combinations (
        basket_id,
        id,
        order_id,
        order_item_id,
        product_name,
        lsd_name,
        lsd_config_id,
        base_unit,
        base_quantity,
        price,
        fprice,
        fprice_min,
        fprice_diff,
        loss,
        order_item_ids_quantity,
        order_item_ids_cost,
        min_order_amount,
        delivery_cost_model
    )
    WITH pieces_generator AS (
        SELECT 
            fp.id,
            fp.order_id,
            fp.order_item_id,
            fp.product_name,
            fp.lsd_name,
            fp.lsd_config_id,
            fp.base_unit,
            fp.base_quantity,
            fp.price,
            fp.fprice,
            fp.fprice_min,
            fp.fprice_diff,
            fp.loss,
            fp.order_item_ids_quantity,
            fp.order_item_ids_cost,
            fp.min_order_amount,
            fp.delivery_cost_model,
            fp.over_requested_quantity,
            generate_series(1, CEIL(fp.over_requested_quantity / NULLIF(fp.base_quantity, 0))::INTEGER) as pieces
        FROM fprice_optimizer fp
        WHERE fp.order_id = p_order_id
    )
    SELECT 
        ROW_NUMBER() OVER (ORDER BY pg.order_item_id, pg.lsd_name, pg.pieces) as basket_id,
        pg.id,
        pg.order_id,
        pg.order_item_id,
        pg.product_name,
        pg.lsd_name,
        pg.lsd_config_id,
        pg.base_unit,
        pg.base_quantity,
        pg.price,
        pg.fprice,
        pg.fprice_min,
        pg.fprice_diff,
        pg.loss,
        pg.pieces as order_item_ids_quantity,  -- количество штук
        (pg.pieces * pg.price) as order_item_ids_cost,  -- стоимость позиции
        pg.min_order_amount,
        pg.delivery_cost_model
    FROM pieces_generator pg;
    
    RAISE NOTICE 'Сгенерировано % комбинаций для заказа %', 
        (SELECT COUNT(*) FROM basket_combinations WHERE order_id = p_order_id), 
        p_order_id;
END;
$$;

-- ==============================================================================
-- Процедура 2: Генерация валидных корзин
-- Записывает результат в таблицу valid_baskets
-- ==============================================================================
CREATE OR REPLACE PROCEDURE generate_valid_baskets(p_order_id INTEGER)
LANGUAGE plpgsql
AS $$
DECLARE
    v_total_baskets BIGINT;
BEGIN
    -- Сначала генерируем комбинации
    CALL generate_basket_combinations(p_order_id);
    
    -- Удаляем старые корзины для этого заказа
    DELETE FROM valid_baskets WHERE order_id = p_order_id;
    
    -- Генерируем и записываем валидные корзины
    INSERT INTO valid_baskets (
        basket_id,
        order_id,
        -- Товар 1
        item_id_1, product_1, lsd_1, lsd_config_1, pieces_1, base_qty_1, price_1, loss_1,
        -- Товар 2
        item_id_2, product_2, lsd_2, lsd_config_2, pieces_2, base_qty_2, price_2, loss_2,
        -- Товар 3
        item_id_3, product_3, lsd_3, lsd_config_3, pieces_3, base_qty_3, price_3, loss_3,
        -- Товар 4
        item_id_4, product_4, lsd_4, lsd_config_4, pieces_4, base_qty_4, price_4, loss_4,
        -- Метрики
        total_goods_cost,
        total_loss
    )
    WITH 
    -- Получаем список уникальных товаров
    item_ids AS (
        SELECT DISTINCT order_item_id 
        FROM basket_combinations
        WHERE order_id = p_order_id
        ORDER BY order_item_id
    ),
    -- Генерируем все корзины через CROSS JOIN
    all_baskets AS (
        SELECT 
            ROW_NUMBER() OVER () as basket_id,
            p_order_id as order_id,
            -- Товар 1
            c1.order_item_id as item_id_1,
            c1.product_name as product_1,
            c1.lsd_name as lsd_1,
            c1.lsd_config_id as lsd_config_1,
            c1.order_item_ids_quantity as pieces_1,
            c1.base_quantity as base_qty_1,
            c1.price as price_1,
            c1.loss as loss_1,
            c1.base_quantity * 1.5 as over_req_qty_1,
            -- Товар 2  
            c2.order_item_id as item_id_2,
            c2.product_name as product_2,
            c2.lsd_name as lsd_2,
            c2.lsd_config_id as lsd_config_2,
            c2.order_item_ids_quantity as pieces_2,
            c2.base_quantity as base_qty_2,
            c2.price as price_2,
            c2.loss as loss_2,
            c2.base_quantity * 1.5 as over_req_qty_2,
            -- Товар 3
            c3.order_item_id as item_id_3,
            c3.product_name as product_3,
            c3.lsd_name as lsd_3,
            c3.lsd_config_id as lsd_config_3,
            c3.order_item_ids_quantity as pieces_3,
            c3.base_quantity as base_qty_3,
            c3.price as price_3,
            c3.loss as loss_3,
            c3.base_quantity * 1.5 as over_req_qty_3,
            -- Товар 4
            c4.order_item_id as item_id_4,
            c4.product_name as product_4,
            c4.lsd_name as lsd_4,
            c4.lsd_config_id as lsd_config_4,
            c4.order_item_ids_quantity as pieces_4,
            c4.base_quantity as base_qty_4,
            c4.price as price_4,
            c4.loss as loss_4,
            c4.base_quantity * 1.5 as over_req_qty_4
        FROM basket_combinations c1
        CROSS JOIN basket_combinations c2
        CROSS JOIN basket_combinations c3
        CROSS JOIN basket_combinations c4
        WHERE 
            c1.order_id = p_order_id
            AND c2.order_id = p_order_id
            AND c3.order_id = p_order_id
            AND c4.order_id = p_order_id
            AND c1.order_item_id = (SELECT order_item_id FROM item_ids LIMIT 1 OFFSET 0)
            AND c2.order_item_id = (SELECT order_item_id FROM item_ids LIMIT 1 OFFSET 1)
            AND c3.order_item_id = (SELECT order_item_id FROM item_ids LIMIT 1 OFFSET 2)
            AND c4.order_item_id = (SELECT order_item_id FROM item_ids LIMIT 1 OFFSET 3)
    )
    -- Фильтруем валидные корзины
    SELECT 
        all_baskets.basket_id,
        all_baskets.order_id,
        -- Товар 1
        all_baskets.item_id_1, all_baskets.product_1, all_baskets.lsd_1, all_baskets.lsd_config_1, 
        all_baskets.pieces_1, all_baskets.base_qty_1, all_baskets.price_1, all_baskets.loss_1,
        -- Товар 2
        all_baskets.item_id_2, all_baskets.product_2, all_baskets.lsd_2, all_baskets.lsd_config_2, 
        all_baskets.pieces_2, all_baskets.base_qty_2, all_baskets.price_2, all_baskets.loss_2,
        -- Товар 3
        all_baskets.item_id_3, all_baskets.product_3, all_baskets.lsd_3, all_baskets.lsd_config_3, 
        all_baskets.pieces_3, all_baskets.base_qty_3, all_baskets.price_3, all_baskets.loss_3,
        -- Товар 4
        all_baskets.item_id_4, all_baskets.product_4, all_baskets.lsd_4, all_baskets.lsd_config_4, 
        all_baskets.pieces_4, all_baskets.base_qty_4, all_baskets.price_4, all_baskets.loss_4,
        -- Метрики
        ROUND(all_baskets.pieces_1 * all_baskets.price_1 + all_baskets.pieces_2 * all_baskets.price_2 + 
              all_baskets.pieces_3 * all_baskets.price_3 + all_baskets.pieces_4 * all_baskets.price_4, 2) as total_goods_cost,
        ROUND(all_baskets.loss_1 + all_baskets.loss_2 + all_baskets.loss_3 + all_baskets.loss_4, 2) as total_loss
    FROM all_baskets
    WHERE 
        (all_baskets.pieces_1 * all_baskets.base_qty_1) <= all_baskets.over_req_qty_1
        AND (all_baskets.pieces_2 * all_baskets.base_qty_2) <= all_baskets.over_req_qty_2
        AND (all_baskets.pieces_3 * all_baskets.base_qty_3) <= all_baskets.over_req_qty_3
        AND (all_baskets.pieces_4 * all_baskets.base_qty_4) <= all_baskets.over_req_qty_4;
    
    GET DIAGNOSTICS v_total_baskets = ROW_COUNT;
    RAISE NOTICE 'Сгенерировано % валидных корзин для заказа %', v_total_baskets, p_order_id;
END;
$$;

-- ==============================================================================
-- КОММЕНТАРИИ К ПРОЦЕДУРАМ
-- ==============================================================================

COMMENT ON PROCEDURE generate_basket_combinations(INTEGER) IS 
'Генерирует все возможные комбинации корзин и записывает в таблицу basket_combinations';

COMMENT ON PROCEDURE generate_valid_baskets(INTEGER) IS 
'Создает все возможные корзины, фильтрует их и записывает в таблицу valid_baskets';

-- ==============================================================================
-- ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ
-- ==============================================================================

-- 1. Сгенерировать комбинации для заказа
-- CALL generate_basket_combinations(16);
-- SELECT * FROM basket_combinations WHERE order_id = 16 LIMIT 10;

-- 2. Сгенерировать валидные корзины для заказа
-- CALL generate_valid_baskets(16);
-- SELECT * FROM valid_baskets WHERE order_id = 16 LIMIT 10;

-- 3. Посмотреть топ-3 оптимизированные корзины
-- SELECT * FROM optimized_baskets WHERE order_id = 16;
