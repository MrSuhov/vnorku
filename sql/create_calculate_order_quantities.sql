-- Универсальная процедура для расчета order_item_ids_quantity и order_item_ids_cost
-- Используется как в штатном процессе, так и для пересчета существующих данных

-- Вспомогательная функция для нормализации единиц измерения (аналог Python функции)
DROP FUNCTION IF EXISTS normalize_to_base_unit CASCADE;
CREATE OR REPLACE FUNCTION normalize_to_base_unit(
    p_quantity NUMERIC,
    p_unit VARCHAR
) RETURNS NUMERIC AS $$
BEGIN
    -- Преобразование в базовые единицы
    CASE p_unit
        WHEN 'г' THEN RETURN p_quantity / 1000;  -- граммы в килограммы
        WHEN 'мл' THEN RETURN p_quantity / 1000;  -- миллилитры в литры  
        WHEN 'кг', 'л', 'шт' THEN RETURN p_quantity;  -- уже в базовых единицах
        ELSE RETURN p_quantity;  -- для неизвестных единиц
    END CASE;
END;
$$ LANGUAGE plpgsql;

-- Функция определения молочных продуктов
DROP FUNCTION IF EXISTS is_milk_product CASCADE;
CREATE OR REPLACE FUNCTION is_milk_product(
    p_product_name VARCHAR
) RETURNS BOOLEAN AS $$
BEGIN
    IF p_product_name IS NULL THEN
        RETURN FALSE;
    END IF;
    
    -- Приводим к нижнему регистру для проверки
    p_product_name := LOWER(p_product_name);
    
    -- Проверяем наличие ключевых слов молочных продуктов
    IF p_product_name ~ '(молоко|milk|кефир|ряженка|сливки|йогурт|творог|сметана|простокваша|варенец|бифидок|снежок|ацидофилин|пахта|сыворотка)' THEN
        -- Исключаем некоторые не-молочные продукты
        IF p_product_name ~ '(сгущенка|сгущенное|сухое молоко|порошок)' THEN
            RETURN FALSE;
        END IF;
        RETURN TRUE;
    END IF;
    
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- Основная процедура расчета количества для заказа
CREATE OR REPLACE PROCEDURE calculate_order_quantities(
    p_order_id INTEGER DEFAULT NULL,  -- NULL = пересчитать для всех заказов
    p_force_recalc BOOLEAN DEFAULT FALSE  -- TRUE = пересчитать даже заполненные
) AS $$
DECLARE
    v_stock RECORD;
    v_over_order_percent INTEGER;
    v_requested_in_base NUMERIC;
    v_order_quantity INTEGER;
    v_order_cost NUMERIC;
    v_unit_for_calc VARCHAR;
    v_processed_count INTEGER := 0;
    v_updated_count INTEGER := 0;
BEGIN
    RAISE NOTICE 'Starting order quantities calculation for order_id=%', COALESCE(p_order_id::TEXT, 'ALL');
    
    -- Цикл по всем записям lsd_stocks
    FOR v_stock IN 
        SELECT 
            ls.id,
            ls.order_id,
            ls.order_item_id,
            ls.lsd_config_id,
            ls.found_name,
            ls.found_unit,
            ls.base_quantity,
            ls.base_unit,
            ls.price,
            ls.requested_quantity,
            ls.requested_unit,
            ls.order_item_ids_quantity,
            ls.order_item_ids_cost,
            COALESCE(o.over_order_percent, u.over_order_percent, 50) as over_order_percent
        FROM lsd_stocks ls
        LEFT JOIN orders o ON o.id = ls.order_id
        LEFT JOIN users u ON u.id = o.user_id
        WHERE (p_order_id IS NULL OR ls.order_id = p_order_id)
            AND ls.requested_quantity IS NOT NULL
            AND ls.requested_unit IS NOT NULL
            AND ls.base_quantity IS NOT NULL
            AND ls.base_quantity > 0
            AND ls.price IS NOT NULL
            AND (p_force_recalc = TRUE OR ls.order_item_ids_quantity IS NULL)
        ORDER BY ls.order_id, ls.order_item_id, ls.id
    LOOP
        v_processed_count := v_processed_count + 1;
        
        -- Корректируем единицы для молочных продуктов
        v_unit_for_calc := v_stock.requested_unit;
        IF is_milk_product(v_stock.found_name) THEN
            IF v_stock.requested_unit = 'г' THEN
                v_unit_for_calc := 'мл';
            ELSIF v_stock.requested_unit = 'кг' THEN
                v_unit_for_calc := 'л';
            END IF;
        END IF;
        
        -- Определяем тип товара (штучный или весовой/объемный)
        IF v_unit_for_calc IN ('шт', 'штука', 'штук', 'пач', 'пачка', 'упак', 'упаковка') THEN
            -- Штучный товар - используем requested_quantity напрямую
            v_order_quantity := v_stock.requested_quantity::INTEGER;
            v_order_cost := ROUND(v_order_quantity * v_stock.price, 2);
            
        ELSE
            -- Весовой/объемный товар - нормализуем и рассчитываем
            v_requested_in_base := normalize_to_base_unit(v_stock.requested_quantity, v_unit_for_calc);
            
            -- Рассчитываем диапазон с учетом over_order_percent
            DECLARE
                v_min_pieces NUMERIC;
                v_max_pieces NUMERIC;
                v_over_requested NUMERIC;
            BEGIN
                v_over_requested := v_requested_in_base * (1 + v_stock.over_order_percent / 100.0);
                
                -- Проверяем, не превышает ли минимальная упаковка максимум
                IF v_stock.base_quantity > v_over_requested THEN
                    -- Минимальная упаковка больше максимально допустимого
                    v_order_quantity := -1;  -- Индикатор превышения
                    v_order_cost := NULL;
                ELSE
                    -- Рассчитываем количество упаковок
                    v_min_pieces := v_requested_in_base / v_stock.base_quantity;
                    v_max_pieces := v_over_requested / v_stock.base_quantity;
                    
                    -- Берем минимальное целое число >= min_pieces
                    v_order_quantity := CEIL(v_min_pieces)::INTEGER;
                    
                    -- Проверяем, что не превышаем максимум
                    IF v_order_quantity > v_max_pieces THEN
                        v_order_quantity := FLOOR(v_max_pieces)::INTEGER;
                    END IF;
                    
                    -- Минимум 1 штука
                    IF v_order_quantity < 1 THEN
                        v_order_quantity := 1;
                    END IF;
                    
                    v_order_cost := ROUND(v_order_quantity * v_stock.price, 2);
                END IF;
            END;
        END IF;
        
        -- Обновляем запись
        UPDATE lsd_stocks
        SET 
            order_item_ids_quantity = v_order_quantity,
            order_item_ids_cost = v_order_cost,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = v_stock.id;
        
        v_updated_count := v_updated_count + 1;
        
        -- Логируем каждые 100 записей
        IF v_processed_count % 100 = 0 THEN
            RAISE NOTICE 'Processed % records, updated %', v_processed_count, v_updated_count;
        END IF;
    END LOOP;
    
    RAISE NOTICE 'Calculation completed: processed % records, updated %', v_processed_count, v_updated_count;
    
    -- Если указан order_id, пересчитываем basket_combinations
    IF p_order_id IS NOT NULL THEN
        CALL update_basket_combinations_costs(p_order_id);
    END IF;
    
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Error in calculate_order_quantities: %', SQLERRM;
        RAISE;
END;
$$ LANGUAGE plpgsql;

-- Процедура для обновления order_item_ids_cost в basket_combinations
CREATE OR REPLACE PROCEDURE update_basket_combinations_costs(
    p_order_id INTEGER DEFAULT NULL
) AS $$
DECLARE
    v_updated_count INTEGER;
BEGIN
    RAISE NOTICE 'Updating basket_combinations costs for order_id=%', COALESCE(p_order_id::TEXT, 'ALL');
    
    -- Обновляем order_item_ids_cost в basket_combinations на основе lsd_stocks
    WITH stock_data AS (
        SELECT 
            ls.order_id,
            ls.order_item_id,
            ls.lsd_config_id,
            ls.order_item_ids_cost,
            ls.order_item_ids_quantity
        FROM lsd_stocks ls
        WHERE (p_order_id IS NULL OR ls.order_id = p_order_id)
            AND ls.order_item_ids_cost IS NOT NULL
    )
    UPDATE basket_combinations bc
    SET 
        order_item_ids_cost = sd.order_item_ids_cost,
        order_item_ids_quantity = sd.order_item_ids_quantity
    FROM stock_data sd
    WHERE bc.order_id = sd.order_id
        AND bc.order_item_id = sd.order_item_id
        AND bc.lsd_config_id = sd.lsd_config_id;
    
    GET DIAGNOSTICS v_updated_count = ROW_COUNT;
    RAISE NOTICE 'Updated % records in basket_combinations', v_updated_count;
    
    -- После обновления basket_combinations, пересчитываем доставку
    IF p_order_id IS NOT NULL THEN
        CALL calculate_basket_delivery_costs(p_order_id);
        RAISE NOTICE 'Recalculated delivery costs for order %', p_order_id;
    END IF;
    
END;
$$ LANGUAGE plpgsql;

-- Функция для проверки статуса расчетов
CREATE OR REPLACE FUNCTION check_order_quantities_status(
    p_order_id INTEGER DEFAULT NULL
) RETURNS TABLE (
    order_id INTEGER,
    total_stocks BIGINT,
    with_quantity BIGINT,
    without_quantity BIGINT,
    with_negative_qty BIGINT,
    total_cost NUMERIC,
    avg_cost NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ls.order_id,
        COUNT(*) as total_stocks,
        COUNT(ls.order_item_ids_quantity) as with_quantity,
        COUNT(*) - COUNT(ls.order_item_ids_quantity) as without_quantity,
        COUNT(*) FILTER (WHERE ls.order_item_ids_quantity = -1) as with_negative_qty,
        SUM(ls.order_item_ids_cost) as total_cost,
        AVG(ls.order_item_ids_cost) as avg_cost
    FROM lsd_stocks ls
    WHERE (p_order_id IS NULL OR ls.order_id = p_order_id)
    GROUP BY ls.order_id
    ORDER BY ls.order_id;
END;
$$ LANGUAGE plpgsql;

-- Примеры использования:
--
-- 1. Пересчитать для конкретного заказа (только пустые)
-- CALL calculate_order_quantities(1);
--
-- 2. Пересчитать для конкретного заказа (все записи)
-- CALL calculate_order_quantities(1, TRUE);
--
-- 3. Пересчитать для всех заказов (только пустые)
-- CALL calculate_order_quantities();
--
-- 4. Проверить статус расчетов
-- SELECT * FROM check_order_quantities_status();
--
-- 5. Проверить статус для конкретного заказа
-- SELECT * FROM check_order_quantities_status(1);
