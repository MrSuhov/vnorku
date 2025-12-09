-- Процедура для анализа корзин заказа и записи результатов в basket_analyses
CREATE OR REPLACE PROCEDURE analyze_order_baskets(
    p_order_id INTEGER
) AS $$
DECLARE
    v_basket RECORD;
    v_lsd_breakdown JSON;
    v_delivery_costs JSON;
    v_total_cost NUMERIC(10,2);
    v_total_savings NUMERIC(10,2);
    v_applied_promotions JSON;
    v_basket_count INTEGER;
    v_best_basket_id INTEGER;
    v_min_loss_and_delivery NUMERIC(10,2);
BEGIN
    -- Проверяем, что order_id указан
    IF p_order_id IS NULL THEN
        RAISE EXCEPTION 'order_id is required';
    END IF;
    
    -- Сначала рассчитываем стоимость доставки для всех корзин заказа
    CALL calculate_basket_delivery_costs(p_order_id);
    
    -- Удаляем старые записи анализа для этого заказа
    DELETE FROM basket_analyses WHERE order_id = p_order_id;
    
    -- Находим лучшую корзину (с минимальным total_loss_and_delivery)
    SELECT 
        basket_id,
        total_loss_and_delivery
    INTO 
        v_best_basket_id,
        v_min_loss_and_delivery
    FROM top_baskets
    WHERE order_id = p_order_id
    ORDER BY total_loss_and_delivery ASC
    LIMIT 1;
    
    -- Получаем данные лучшей корзины
    SELECT * INTO v_basket
    FROM top_baskets
    WHERE basket_id = v_best_basket_id;
    
    -- Формируем lsd_breakdown - разбивка товаров по ЛСД
    SELECT json_object_agg(
        lsd_name,
        json_build_object(
            'items_count', items_count,
            'items_cost', items_cost,
            'delivery_cost', delivery_cost,
            'topup', topup,
            'total_cost', items_cost + delivery_cost
        )
    ) INTO v_lsd_breakdown
    FROM (
        SELECT 
            COALESCE(lc.name, bc.lsd_name) as lsd_name,
            COUNT(DISTINCT bc.order_item_id) as items_count,
            SUM(bc.order_item_ids_cost) as items_cost,
            MAX(bdc.delivery_cost) as delivery_cost,
            MAX(bdc.topup) as topup
        FROM basket_combinations bc
        LEFT JOIN basket_delivery_costs bdc 
            ON bdc.basket_id = bc.basket_id 
            AND bdc.lsd_config_id = bc.lsd_config_id
        LEFT JOIN lsd_configs lc ON lc.id = bc.lsd_config_id
        WHERE bc.basket_id = v_best_basket_id
        GROUP BY COALESCE(lc.name, bc.lsd_name)
    ) t;
    
    -- Берем delivery_costs из top_baskets
    v_delivery_costs := v_basket.delivery_cost;
    
    -- Общая стоимость
    v_total_cost := v_basket.total_cost;
    
    -- Рассчитываем экономию относительно худшей корзины
    SELECT MAX(total_cost) - v_total_cost
    INTO v_total_savings
    FROM top_baskets
    WHERE order_id = p_order_id;
    
    -- Пока заглушка для промокодов (будет заполняться позже)
    v_applied_promotions := '[]'::JSON;
    
    -- Вставляем результат анализа
    INSERT INTO basket_analyses (
        order_id,
        lsd_breakdown,
        total_cost,
        total_savings,
        delivery_costs,
        applied_promotions
    ) VALUES (
        p_order_id,
        v_lsd_breakdown,
        v_total_cost,
        COALESCE(v_total_savings, 0),
        v_delivery_costs,
        v_applied_promotions
    );
    
    -- Выводим результат
    RAISE NOTICE 'Анализ завершен для заказа %', p_order_id;
    RAISE NOTICE 'Лучшая корзина: % (потери+доставка: %₽)', v_best_basket_id, v_min_loss_and_delivery;
    RAISE NOTICE 'Общая стоимость: %₽, Экономия: %₽', v_total_cost, COALESCE(v_total_savings, 0);
    
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Ошибка при анализе заказа %: %', p_order_id, SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- Функция для получения результатов анализа
CREATE OR REPLACE FUNCTION get_basket_analysis_results(
    p_order_id INTEGER
) RETURNS TABLE (
    order_id INTEGER,
    best_basket_id INTEGER,
    total_cost NUMERIC(10,2),
    total_savings NUMERIC(10,2),
    total_goods_cost NUMERIC(10,2),
    total_delivery_cost NUMERIC(10,2),
    total_loss NUMERIC(10,2),
    lsd_count INTEGER,
    lsd_breakdown JSON,
    delivery_costs JSON
) AS $$
BEGIN
    RETURN QUERY
    WITH best_basket AS (
        SELECT 
            tb.basket_id,
            tb.order_id,
            tb.total_cost,
            tb.total_goods_cost,
            tb.total_delivery_cost,
            tb.total_loss,
            tb.delivery_cost,
            tb.delivery_topup
        FROM top_baskets tb
        WHERE tb.order_id = p_order_id
        ORDER BY tb.total_loss_and_delivery ASC
        LIMIT 1
    )
    SELECT 
        ba.order_id,
        bb.basket_id as best_basket_id,
        ba.total_cost,
        ba.total_savings,
        bb.total_goods_cost,
        bb.total_delivery_cost,
        bb.total_loss,
        (SELECT COUNT(DISTINCT lsd_config_id) 
         FROM basket_combinations 
         WHERE basket_id = bb.basket_id)::INTEGER as lsd_count,
        ba.lsd_breakdown,
        ba.delivery_costs
    FROM basket_analyses ba
    JOIN best_basket bb ON bb.order_id = ba.order_id
    WHERE ba.order_id = p_order_id;
END;
$$ LANGUAGE plpgsql;

-- Создаем view для удобного просмотра результатов анализа
CREATE OR REPLACE VIEW v_basket_analysis_summary AS
SELECT 
    ba.id,
    ba.order_id,
    o.user_id,
    o.status as order_status,
    ba.total_cost,
    ba.total_savings,
    ba.delivery_costs,
    jsonb_array_length(jsonb_object_keys(ba.lsd_breakdown::jsonb)) as lsd_count,
    ba.created_at,
    -- Извлекаем данные из JSON для удобства
    (SELECT SUM((value->>'items_cost')::NUMERIC) 
     FROM jsonb_each(ba.lsd_breakdown::jsonb)) as total_items_cost,
    (SELECT SUM((value->>'delivery_cost')::NUMERIC) 
     FROM jsonb_each(ba.lsd_breakdown::jsonb)) as total_delivery_cost
FROM basket_analyses ba
JOIN orders o ON o.id = ba.order_id;

-- Примеры использования:
--
-- 1. Анализ заказа:
-- CALL analyze_order_baskets(1);
--
-- 2. Получение результатов анализа:
-- SELECT * FROM get_basket_analysis_results(1);
--
-- 3. Просмотр всех анализов:
-- SELECT * FROM v_basket_analysis_summary;
--
-- 4. Детальный просмотр lsd_breakdown для заказа:
-- SELECT order_id, 
--        jsonb_pretty(lsd_breakdown::jsonb) as lsd_details
-- FROM basket_analyses 
-- WHERE order_id = 1;
