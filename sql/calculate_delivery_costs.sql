-- Создаем таблицу для хранения результатов расчета стоимости доставки
CREATE TABLE IF NOT EXISTS basket_delivery_costs (
    id SERIAL PRIMARY KEY,
    basket_id INTEGER NOT NULL,
    lsd_config_id INTEGER NOT NULL,
    delivery_cost NUMERIC(10,2) NOT NULL DEFAULT 0,
    topup NUMERIC(10,2) NOT NULL DEFAULT 0,  -- Сколько нужно доплатить до минимальной суммы
    total_basket_cost NUMERIC(10,2) NOT NULL DEFAULT 0,  -- Общая стоимость товаров в корзине для данного ЛСД
    min_order_amount NUMERIC(10,2) DEFAULT 0,  -- Минимальная сумма заказа для бесплатной доставки
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Уникальный индекс на комбинацию basket_id и lsd_config_id
    UNIQUE (basket_id, lsd_config_id)
);

-- Создаем индекс для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_basket_delivery_costs_basket_id ON basket_delivery_costs(basket_id);
CREATE INDEX IF NOT EXISTS idx_basket_delivery_costs_lsd_config_id ON basket_delivery_costs(lsd_config_id);

-- Функция для расчета стоимости доставки на основе модели
CREATE OR REPLACE FUNCTION calculate_delivery_by_model(
    p_delivery_model JSON,
    p_total_cost NUMERIC
) RETURNS NUMERIC AS $$
DECLARE
    v_delivery_cost NUMERIC := 0;
    v_range RECORD;
BEGIN
    -- Если модель не задана, возвращаем 0
    IF p_delivery_model IS NULL THEN
        RETURN 0;
    END IF;
    
    -- Проходим по диапазонам в модели доставки
    FOR v_range IN 
        SELECT 
            (range_obj->>'min_amount')::NUMERIC as min_amount,
            (range_obj->>'max_amount')::NUMERIC as max_amount,
            (range_obj->>'delivery_cost')::NUMERIC as delivery_cost
        FROM json_array_elements(p_delivery_model->'ranges') AS range_obj
        ORDER BY (range_obj->>'min_amount')::NUMERIC
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
            SUM(bc.order_item_ids_cost) as total_cost,
            -- Берем первую модель доставки (они должны быть одинаковые для одного ЛСД)
            (array_agg(bc.delivery_cost_model))[1] as delivery_model
        FROM basket_combinations bc
        WHERE (p_order_id IS NULL OR bc.order_id = p_order_id)
            AND bc.lsd_config_id IS NOT NULL
            AND bc.order_item_ids_cost IS NOT NULL
        GROUP BY bc.basket_id, bc.lsd_config_id
    LOOP
        -- Рассчитываем стоимость доставки на основе модели
        v_delivery_cost := calculate_delivery_by_model(
            v_lsd_cost.delivery_model, 
            v_lsd_cost.total_cost
        );
        
        -- Получаем минимальную сумму заказа для бесплатной доставки (если есть)
        v_min_order_amount := 0;
        IF v_lsd_cost.delivery_model IS NOT NULL AND 
           v_lsd_cost.delivery_model->'min_order_for_free_delivery' IS NOT NULL THEN
            v_min_order_amount := (v_lsd_cost.delivery_model->>'min_order_for_free_delivery')::NUMERIC;
        END IF;
        
        -- Рассчитываем топап (сколько нужно доплатить до минимальной суммы)
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
