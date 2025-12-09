-- ==============================================================================
-- ИСПРАВЛЕНИЕ: Использование composite key (order_id, basket_id) в top_baskets
-- ==============================================================================
-- Проблема: функция top_baskets использовала только basket_id для JOIN,
--           что приводило к смешиванию данных из разных заказов с одинаковым basket_id
-- Решение: добавить order_id во все WHERE условия и JOIN'ы

DROP FUNCTION IF EXISTS top_baskets(INTEGER, INTEGER);

CREATE OR REPLACE FUNCTION top_baskets(p_order_id INTEGER, p_rank INTEGER)
RETURNS TABLE(
    result_type TEXT,
    lsd_name VARCHAR(100),
    product_name VARCHAR(500),
    original_product_name VARCHAR(500),
    base_quantity NUMERIC(10,3),
    base_unit VARCHAR(10),
    price NUMERIC(10,2),
    fprice NUMERIC(10,2),
    order_item_ids_cost NUMERIC(10,2),
    order_item_ids_quantity NUMERIC,
    requested_quantity NUMERIC(10,3),
    requested_unit VARCHAR(20),
    product_url VARCHAR(1000),
    basket_id INTEGER,
    order_id INTEGER,
    basket_rank INTEGER,
    total_goods_cost NUMERIC(10,2),
    total_delivery_cost NUMERIC(10,2),
    total_loss NUMERIC(10,2),
    total_cost NUMERIC(10,2),
    diff_with_rank1 NUMERIC(10,2),
    delivery_cost NUMERIC(10,2),
    topup NUMERIC(10,2),
    delivery_topup JSON
) AS $$
DECLARE
    v_basket_id INTEGER;
    v_rank1_total_cost NUMERIC(10,2);
    v_current_total_cost NUMERIC(10,2);
BEGIN
    -- Находим basket_id для указанного ранга И заказа
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
    WHERE ba.order_id = p_order_id  -- ИСПРАВЛЕНИЕ: добавлен order_id
      AND ba.basket_id = v_basket_id;
    
    -- Result Set 1: Детализация товаров, сгруппированная по магазинам
    -- КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: добавлен фильтр bc.order_id = p_order_id
    RETURN QUERY
    SELECT
        'ITEMS'::TEXT,
        bc.lsd_name,
        bc.product_name,
        oi.product_name,
        bc.base_quantity,
        bc.base_unit,
        bc.price,
        bc.fprice,
        bc.order_item_ids_cost,
        bc.order_item_ids_quantity,
        oi.requested_quantity,
        oi.requested_unit,
        ls.product_url,
        NULL::INTEGER,
        NULL::INTEGER,
        NULL::INTEGER,
        NULL::NUMERIC(10,2),
        NULL::NUMERIC(10,2),
        NULL::NUMERIC(10,2),
        NULL::NUMERIC(10,2),
        NULL::NUMERIC(10,2),
        NULL::NUMERIC(10,2),
        NULL::NUMERIC(10,2),
        NULL::JSON
    FROM basket_combinations bc
    INNER JOIN order_items oi ON bc.order_item_id = oi.id
    LEFT JOIN lsd_stocks ls ON bc.lsd_stock_id = ls.id
    WHERE bc.order_id = p_order_id      -- ИСПРАВЛЕНИЕ: добавлен фильтр по order_id
      AND bc.basket_id = v_basket_id
    ORDER BY bc.lsd_name, bc.order_item_id;
    
    -- Result Set 2: Детализация доставки и топапов по ЛСД
    -- КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: добавлен фильтр bdc.order_id = p_order_id
    RETURN QUERY
    SELECT
        'DELIVERY_DETAILS'::TEXT,
        lc.name,
        NULL::VARCHAR(500),
        NULL::VARCHAR(500),
        NULL::NUMERIC(10,3),
        NULL::VARCHAR(10),
        NULL::NUMERIC(10,2),
        NULL::NUMERIC(10,2),
        NULL::NUMERIC(10,2),
        NULL::NUMERIC,
        NULL::NUMERIC(10,3),
        NULL::VARCHAR(20),
        NULL::VARCHAR(1000),
        NULL::INTEGER,
        NULL::INTEGER,
        NULL::INTEGER,
        NULL::NUMERIC(10,2),
        NULL::NUMERIC(10,2),
        NULL::NUMERIC(10,2),
        NULL::NUMERIC(10,2),
        NULL::NUMERIC(10,2),
        bdc.delivery_cost,
        bdc.topup,
        NULL::JSON
    FROM basket_delivery_costs bdc
    INNER JOIN lsd_configs lc ON bdc.lsd_config_id = lc.id
    WHERE bdc.order_id = p_order_id     -- ИСПРАВЛЕНИЕ: добавлен фильтр по order_id
      AND bdc.basket_id = v_basket_id
      AND (bdc.delivery_cost > 0 OR bdc.topup > 0)
    ORDER BY lc.name;
    
    -- Result Set 3: Сводная информация
    -- ИСПРАВЛЕНИЕ: фильтр по order_id уже был корректен
    RETURN QUERY
    SELECT
        'SUMMARY'::TEXT,
        NULL::VARCHAR(100),
        NULL::VARCHAR(500),
        NULL::VARCHAR(500),
        NULL::NUMERIC(10,3),
        NULL::VARCHAR(10),
        NULL::NUMERIC(10,2),
        NULL::NUMERIC(10,2),
        NULL::NUMERIC(10,2),
        NULL::NUMERIC,
        NULL::NUMERIC(10,3),
        NULL::VARCHAR(20),
        NULL::VARCHAR(1000),
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
        END,
        NULL::NUMERIC(10,2),
        NULL::NUMERIC(10,2),
        ba.delivery_topup
    FROM basket_analyses ba
    WHERE ba.order_id = p_order_id      -- Фильтр уже был
      AND ba.basket_id = v_basket_id;
    
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION top_baskets(INTEGER, INTEGER) IS 
'Возвращает детализацию корзины указанного ранга с использованием composite key (order_id, basket_id). 
ИСПРАВЛЕНИЕ: добавлены фильтры по order_id во все JOIN для предотвращения смешивания данных разных заказов.';

-- ==============================================================================
-- ТЕСТ
-- ==============================================================================
-- SELECT * FROM top_baskets(30, 1);
