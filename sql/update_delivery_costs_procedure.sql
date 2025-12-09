-- Удаляем старые функции и процедуры
DROP FUNCTION IF EXISTS calculate_delivery_by_model CASCADE;
DROP PROCEDURE IF EXISTS calculate_basket_delivery_costs CASCADE;
DROP FUNCTION IF EXISTS get_basket_delivery_summary CASCADE;

-- Функция для расчета стоимости доставки на основе модели (поддержка разных форматов)
CREATE OR REPLACE FUNCTION calculate_delivery_by_model(
    p_delivery_model JSON,
    p_total_cost NUMERIC
) RETURNS NUMERIC AS $$
DECLARE
    v_delivery_cost NUMERIC := 0;
    v_range RECORD;
    v_delivery_array JSON;
BEGIN
    -- Если модель не задана, возвращаем 0
    IF p_delivery_model IS NULL THEN
        RETURN 0;
    END IF;
    
    -- Получаем массив delivery_cost
    v_delivery_array := p_delivery_model->'delivery_cost';
    
    IF v_delivery_array IS NULL THEN
        RETURN 0;
    END IF;
    
    -- Проходим по диапазонам в модели доставки
    FOR v_range IN 
        SELECT 
            -- Поддерживаем разные форматы: min/max, order_lower/order_upper
            COALESCE(
                (range_obj->>'min')::NUMERIC,
                (range_obj->>'order_lower')::NUMERIC,
                0
            ) as min_amount,
            CASE 
                WHEN range_obj->>'max' = 'null' OR range_obj->>'order_upper' = 'null' THEN NULL
                ELSE COALESCE(
                    (range_obj->>'max')::NUMERIC,
                    (range_obj->>'order_upper')::NUMERIC
                )
            END as max_amount,
            (range_obj->>'fee')::NUMERIC as delivery_cost
        FROM json_array_elements(v_delivery_array) AS range_obj
        ORDER BY 1  -- Сортируем по min_amount
    LOOP
        -- Проверяем, попадает ли сумма в текущий диапазон
        IF p_total_cost >= v_range.min_amount AND 
           (v_range.max_amount IS NULL OR p_total_cost < v_range.max_amount) THEN
            v_delivery_cost := v_range.delivery_cost;
            EXIT; -- Нашли подходящий диапазон, выходим из цикла
        END IF;
    END LOOP;
    
    RETURN v_delivery_cost;
END;
$$ LANGUAGE plpgsql;

-- Основная процедура расчета стоимости доставки для всех корзин
CREATE OR REPLACE PROCEDURE calculate_basket_delivery_costs(
    p_order_id INTEGER DEFAULT NULL  -- Опциональный параметр для расчета только для конкретного заказа
) AS $$
DECLARE
    v_basket RECORD;
    v_lsd_cost RECORD;
    v_delivery_cost NUMERIC;
    v_topup NUMERIC;
    v_min_order_amount NUMERIC;
    v_free_delivery_threshold NUMERIC;
BEGIN
    -- Удаляем старые записи для указанного заказа или всех заказов
    IF p_order_id IS NOT NULL THEN
        DELETE FROM basket_delivery_costs 
        WHERE basket_id IN (
            SELECT DISTINCT basket_id 
            FROM basket_combinations 
            WHERE order_id = p_order_id
        );
    ELSE
        -- Если order_id не указан, очищаем всю таблицу
        TRUNCATE basket_delivery_costs;
    END IF;
    
    -- Получаем уникальные комбинации basket_id и lsd_config_id с суммарной стоимостью товаров
    FOR v_lsd_cost IN 
        SELECT 
            bc.basket_id,
            bc.lsd_config_id,
            bc.lsd_name,
            SUM(bc.order_item_ids_cost) as total_cost,
            -- Берем первую модель доставки (они должны быть одинаковые для одного ЛСД)
            (array_agg(bc.delivery_cost_model))[1] as delivery_model
        FROM basket_combinations bc
        WHERE (p_order_id IS NULL OR bc.order_id = p_order_id)
            AND bc.lsd_config_id IS NOT NULL
            AND bc.order_item_ids_cost IS NOT NULL
        GROUP BY bc.basket_id, bc.lsd_config_id, bc.lsd_name
    LOOP
        -- Рассчитываем стоимость доставки на основе модели
        v_delivery_cost := calculate_delivery_by_model(
            v_lsd_cost.delivery_model, 
            v_lsd_cost.total_cost
        );
        
        -- Определяем минимальную сумму для бесплатной доставки
        -- Для разных ЛСД разная логика
        v_min_order_amount := 0;
        v_free_delivery_threshold := NULL;
        
        -- Ищем порог бесплатной доставки в модели
        IF v_lsd_cost.delivery_model IS NOT NULL AND 
           v_lsd_cost.delivery_model->'delivery_cost' IS NOT NULL THEN
            -- Находим диапазон с fee = 0
            SELECT MIN(COALESCE(
                    (range_obj->>'min')::NUMERIC,
                    (range_obj->>'order_lower')::NUMERIC,
                    0
                ))
            INTO v_free_delivery_threshold
            FROM json_array_elements(v_lsd_cost.delivery_model->'delivery_cost') AS range_obj
            WHERE (range_obj->>'fee')::NUMERIC = 0;
        END IF;
        
        -- Если есть порог бесплатной доставки, используем его
        IF v_free_delivery_threshold IS NOT NULL THEN
            v_min_order_amount := v_free_delivery_threshold;
        END IF;
        
        -- Рассчитываем топап (сколько нужно доплатить до бесплатной доставки)
        v_topup := 0;
        IF v_min_order_amount > 0 AND v_lsd_cost.total_cost < v_min_order_amount THEN
            v_topup := v_min_order_amount - v_lsd_cost.total_cost;
        END IF;
        
        -- Вставляем результат в таблицу
        INSERT INTO basket_delivery_costs (
            basket_id,
            lsd_config_id,
            delivery_cost,
            topup,
            total_basket_cost,
            min_order_amount
        ) VALUES (
            v_lsd_cost.basket_id,
            v_lsd_cost.lsd_config_id,
            v_delivery_cost,
            v_topup,
            v_lsd_cost.total_cost,
            v_min_order_amount
        ) ON CONFLICT (basket_id, lsd_config_id) 
        DO UPDATE SET
            delivery_cost = EXCLUDED.delivery_cost,
            topup = EXCLUDED.topup,
            total_basket_cost = EXCLUDED.total_basket_cost,
            min_order_amount = EXCLUDED.min_order_amount,
            updated_at = CURRENT_TIMESTAMP;
    END LOOP;
    
    -- Выводим сообщение о завершении
    RAISE NOTICE 'Расчет стоимости доставки завершен для % корзин', 
        (SELECT COUNT(DISTINCT basket_id) FROM basket_delivery_costs);
END;
$$ LANGUAGE plpgsql;

-- Вспомогательная функция для получения результатов расчета
CREATE OR REPLACE FUNCTION get_basket_delivery_summary(
    p_basket_id INTEGER DEFAULT NULL,
    p_order_id INTEGER DEFAULT NULL
) RETURNS TABLE (
    basket_id INTEGER,
    lsd_config_id INTEGER,
    lsd_name VARCHAR(100),
    total_basket_cost NUMERIC(10,2),
    delivery_cost NUMERIC(10,2),
    topup NUMERIC(10,2),
    min_order_amount NUMERIC(10,2),
    final_cost NUMERIC(10,2)  -- Общая стоимость с доставкой
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        bdc.basket_id,
        bdc.lsd_config_id,
        lc.name as lsd_name,
        bdc.total_basket_cost,
        bdc.delivery_cost,
        bdc.topup,
        bdc.min_order_amount,
        (bdc.total_basket_cost + bdc.delivery_cost) as final_cost
    FROM basket_delivery_costs bdc
    LEFT JOIN lsd_configs lc ON lc.id = bdc.lsd_config_id
    WHERE (p_basket_id IS NULL OR bdc.basket_id = p_basket_id)
        AND (p_order_id IS NULL OR bdc.basket_id IN (
            SELECT DISTINCT basket_id 
            FROM basket_combinations 
            WHERE order_id = p_order_id
        ))
    ORDER BY bdc.basket_id, bdc.lsd_config_id;
END;
$$ LANGUAGE plpgsql;

-- Примеры использования:
-- 
-- 1. Расчет для всех корзин:
-- CALL calculate_basket_delivery_costs();
--
-- 2. Расчет только для конкретного заказа:
-- CALL calculate_basket_delivery_costs(123);
--
-- 3. Получение результатов для конкретной корзины:
-- SELECT * FROM get_basket_delivery_summary(p_basket_id := 1);
--
-- 4. Получение результатов для конкретного заказа:
-- SELECT * FROM get_basket_delivery_summary(p_order_id := 123);
--
-- 5. Получение всех результатов:
-- SELECT * FROM basket_delivery_costs ORDER BY basket_id, lsd_config_id;
