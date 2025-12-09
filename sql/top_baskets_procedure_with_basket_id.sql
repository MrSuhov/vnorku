-- Процедура для получения детализированной информации о корзине по рангу
-- Автор: Korzinka Team
-- Дата: 2025-09-29
-- Обновлено: добавлен basket_id в результаты
-- Исправлено: 2025-10-06 - исправлен JOIN на lsd_stocks через lsd_stock_id
-- Исправлено: 2025-10-06 - добавлен фильтр по order_id в SUMMARY для предотвращения дублей

DROP FUNCTION IF EXISTS top_baskets(INTEGER, INTEGER);

CREATE OR REPLACE FUNCTION top_baskets(
    p_order_id INTEGER,
    p_rank INTEGER
)
RETURNS TABLE(
    result_type TEXT,
    -- Поля для детализации товаров
    lsd_name VARCHAR(100),
    product_name VARCHAR(500),
    original_product_name VARCHAR(500),
    base_quantity NUMERIC(10,3),
    base_unit VARCHAR(10),
    price NUMERIC(10,2),
    fprice NUMERIC(10,2),
    loss NUMERIC(10,2),
    order_item_ids_cost NUMERIC(10,2),
    order_item_ids_quantity NUMERIC,
    requested_quantity NUMERIC(10,3),
    requested_unit VARCHAR(20),
    product_url VARCHAR(1000),
    -- Поля для сводной информации
    basket_id INTEGER,
    order_id INTEGER,
    basket_rank INTEGER,
    total_goods_cost NUMERIC(10,2),
    total_delivery_cost NUMERIC(10,2),
    total_loss NUMERIC(10,2),
    total_cost NUMERIC(10,2),
    diff_with_rank1 NUMERIC(10,2),
    delivery_topup JSON
) AS $$
DECLARE
    v_basket_id INTEGER;
    v_rank1_total_cost NUMERIC(10,2);
    v_current_total_cost NUMERIC(10,2);
BEGIN
    -- Находим basket_id для указанного ранга
    SELECT ba.basket_id
    INTO v_basket_id
    FROM basket_analyses ba
    WHERE ba.order_id = p_order_id
      AND ba.basket_rank = p_rank;
    
    -- Если корзина не найдена, возвращаем пустой результат
    IF v_basket_id IS NULL THEN
        RAISE NOTICE 'Basket with order_id=% and rank=% not found', p_order_id, p_rank;
        RETURN;
    END IF;
    
    -- Получаем стоимость корзины с рангом 1 для расчета разницы
    SELECT ba.total_cost
    INTO v_rank1_total_cost
    FROM basket_analyses ba
    WHERE ba.order_id = p_order_id
      AND ba.basket_rank = 1;
    
    -- Получаем стоимость текущей корзины
    SELECT ba.total_cost
    INTO v_current_total_cost
    FROM basket_analyses ba
    WHERE ba.basket_id = v_basket_id
      AND ba.order_id = p_order_id;
    
    -- Result Set 1: Детализация товаров, сгруппированная по магазинам
    RETURN QUERY
    SELECT
        'ITEMS'::TEXT as result_type,
        bc.lsd_name,
        bc.product_name,
        oi.product_name as original_product_name,
        bc.base_quantity,
        bc.base_unit,
        bc.price,
        bc.fprice,
        bc.loss,
        bc.order_item_ids_cost,
        bc.order_item_ids_quantity,
        oi.requested_quantity,
        oi.requested_unit,
        ls.product_url,
        -- Сводные поля NULL для детализации
        NULL::INTEGER as basket_id,
        NULL::INTEGER as order_id,
        NULL::INTEGER as basket_rank,
        NULL::NUMERIC(10,2) as total_goods_cost,
        NULL::NUMERIC(10,2) as total_delivery_cost,
        NULL::NUMERIC(10,2) as total_loss,
        NULL::NUMERIC(10,2) as total_cost,
        NULL::NUMERIC(10,2) as diff_with_rank1,
        NULL::JSON as delivery_topup
    FROM basket_combinations bc
    INNER JOIN order_items oi ON bc.order_item_id = oi.id
    LEFT JOIN lsd_stocks ls ON 
        bc.lsd_stock_id = ls.id
        AND ls.order_id = p_order_id
    WHERE bc.basket_id = v_basket_id
      AND bc.order_id = p_order_id
    ORDER BY bc.lsd_name, bc.order_item_id;
    
    -- Result Set 2: Сводная информация
    RETURN QUERY
    SELECT
        'SUMMARY'::TEXT as result_type,
        -- Детальные поля NULL для сводки
        NULL::VARCHAR(100) as lsd_name,
        NULL::VARCHAR(500) as product_name,
        NULL::VARCHAR(500) as original_product_name,
        NULL::NUMERIC(10,3) as base_quantity,
        NULL::VARCHAR(10) as base_unit,
        NULL::NUMERIC(10,2) as price,
        NULL::NUMERIC(10,2) as fprice,
        NULL::NUMERIC(10,2) as loss,
        NULL::NUMERIC(10,2) as order_item_ids_cost,
        NULL::NUMERIC as order_item_ids_quantity,
        NULL::NUMERIC(10,3) as requested_quantity,
        NULL::VARCHAR(20) as requested_unit,
        NULL::VARCHAR(1000) as product_url,
        -- Сводные поля
        ba.basket_id,
        ba.order_id,
        ba.basket_rank,
        ba.total_goods_cost,
        ba.total_delivery_cost,
        ba.total_loss,
        ba.total_cost,
        CASE 
            WHEN p_rank = 1 THEN 0.00
            ELSE (v_current_total_cost - COALESCE(v_rank1_total_cost, 0.00))
        END as diff_with_rank1,
        ba.delivery_topup
    FROM basket_analyses ba
    WHERE ba.basket_id = v_basket_id
      AND ba.order_id = p_order_id;
    
END;
$$ LANGUAGE plpgsql;

-- Комментарии к функции
COMMENT ON FUNCTION top_baskets(INTEGER, INTEGER) IS 
'Возвращает детализированную информацию о корзине по order_id и basket_rank.
Result Set 1 (result_type=ITEMS): детализация товаров, сгруппированная по магазинам
Result Set 2 (result_type=SUMMARY): сводная информация по корзине с разницей от rank=1
FIX 2025-10-06: Использует прямую связь bc.lsd_stock_id = ls.id для предотвращения утечки данных между заказами
FIX 2025-10-06: Добавлен фильтр по order_id в запросе SUMMARY для корректной работы с композитным ключом (order_id, basket_id)';

-- Примеры использования:
-- SELECT * FROM top_baskets(16, 1);
-- SELECT * FROM top_baskets(16, 2);
