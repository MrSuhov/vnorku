-- Комплексная процедура для полного пересчета заказа
-- Включает: расчет количеств, обновление basket_combinations, расчет доставки и анализ корзин

CREATE OR REPLACE PROCEDURE full_order_recalculation(
    p_order_id INTEGER,
    p_force_recalc BOOLEAN DEFAULT FALSE
) AS $$
DECLARE
    v_start_time TIMESTAMP;
    v_end_time TIMESTAMP;
    v_duration INTERVAL;
BEGIN
    v_start_time := clock_timestamp();
    
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Starting full recalculation for order %', p_order_id;
    RAISE NOTICE '========================================';
    
    -- ШАГ 1: Пересчет количеств товаров
    RAISE NOTICE 'Step 1: Calculating order quantities...';
    CALL calculate_order_quantities(p_order_id, p_force_recalc);
    
    -- ШАГ 2: Обновление basket_combinations (уже включает расчет доставки)
    RAISE NOTICE 'Step 2: Updating basket combinations and delivery costs...';
    CALL update_basket_combinations_costs(p_order_id);
    
    -- ШАГ 3: Анализ корзин
    RAISE NOTICE 'Step 3: Analyzing baskets...';
    CALL analyze_order_baskets(p_order_id);
    
    v_end_time := clock_timestamp();
    v_duration := v_end_time - v_start_time;
    
    -- Вывод итоговой статистики
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Recalculation completed in %', v_duration;
    
    -- Показываем результаты
    PERFORM * FROM (
        SELECT 
            COUNT(DISTINCT basket_id) as total_baskets,
            MIN(total_loss_and_delivery) as best_score,
            MAX(total_loss_and_delivery) as worst_score
        FROM basket_analyses
        WHERE order_id = p_order_id
    ) stats;
    
    RAISE NOTICE 'Order % analysis: found best basket with score %.2f₽',
        p_order_id,
        (SELECT MIN(total_loss_and_delivery) FROM basket_analyses WHERE order_id = p_order_id);
    
    RAISE NOTICE '========================================';
    
END;
$$ LANGUAGE plpgsql;

-- Процедура для проверки и исправления проблемных данных
CREATE OR REPLACE PROCEDURE fix_problematic_quantities(
    p_dry_run BOOLEAN DEFAULT TRUE
) AS $$
DECLARE
    v_problematic_count INTEGER;
    v_fixed_count INTEGER := 0;
BEGIN
    -- Находим проблемные записи
    SELECT COUNT(*) INTO v_problematic_count
    FROM lsd_stocks
    WHERE order_item_ids_cost > 10000
       OR order_item_ids_quantity > 100;
    
    IF v_problematic_count = 0 THEN
        RAISE NOTICE 'No problematic records found';
        RETURN;
    END IF;
    
    RAISE NOTICE 'Found % problematic records', v_problematic_count;
    
    IF p_dry_run THEN
        -- Показываем примеры проблемных записей
        RAISE NOTICE 'DRY RUN MODE - showing examples:';
        
        FOR v_record IN 
            SELECT 
                id,
                found_name,
                price,
                order_item_ids_quantity,
                order_item_ids_cost
            FROM lsd_stocks
            WHERE order_item_ids_cost > 10000
               OR order_item_ids_quantity > 100
            LIMIT 5
        LOOP
            RAISE NOTICE '  ID %: % (qty=%, cost=%₽)', 
                v_record.id, 
                LEFT(v_record.found_name, 50),
                v_record.order_item_ids_quantity,
                v_record.order_item_ids_cost;
        END LOOP;
        
        RAISE NOTICE 'Run with p_dry_run=FALSE to fix these records';
    ELSE
        -- Исправляем проблемные записи
        UPDATE lsd_stocks
        SET 
            order_item_ids_quantity = NULL,
            order_item_ids_cost = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE order_item_ids_cost > 10000
           OR order_item_ids_quantity > 100;
        
        GET DIAGNOSTICS v_fixed_count = ROW_COUNT;
        
        RAISE NOTICE 'Fixed % problematic records (set to NULL for recalculation)', v_fixed_count;
        
        -- Запускаем пересчет для затронутых заказов
        FOR v_order_id IN 
            SELECT DISTINCT order_id 
            FROM lsd_stocks 
            WHERE order_item_ids_quantity IS NULL
                AND order_id IS NOT NULL
        LOOP
            RAISE NOTICE 'Recalculating order %...', v_order_id;
            CALL calculate_order_quantities(v_order_id);
        END LOOP;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Вспомогательная функция для диагностики
CREATE OR REPLACE FUNCTION diagnose_order_calculations(
    p_order_id INTEGER
) RETURNS TABLE (
    check_name TEXT,
    status TEXT,
    details TEXT
) AS $$
BEGIN
    -- Проверка 1: Наличие lsd_stocks
    RETURN QUERY
    SELECT 
        'LSD Stocks Records'::TEXT,
        CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'ERROR' END,
        'Total: ' || COUNT(*)::TEXT || ' records'
    FROM lsd_stocks
    WHERE order_id = p_order_id;
    
    -- Проверка 2: Расчет количеств
    RETURN QUERY
    SELECT 
        'Order Quantities Calculated'::TEXT,
        CASE 
            WHEN COUNT(*) = COUNT(order_item_ids_quantity) THEN 'OK'
            WHEN COUNT(order_item_ids_quantity) > 0 THEN 'PARTIAL'
            ELSE 'MISSING'
        END,
        'Calculated: ' || COUNT(order_item_ids_quantity)::TEXT || '/' || COUNT(*)::TEXT
    FROM lsd_stocks
    WHERE order_id = p_order_id;
    
    -- Проверка 3: Проблемные записи
    RETURN QUERY
    SELECT 
        'Problematic Quantities'::TEXT,
        CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'WARNING' END,
        'Found: ' || COUNT(*)::TEXT || ' records with qty>100 or cost>10000'
    FROM lsd_stocks
    WHERE order_id = p_order_id
        AND (order_item_ids_quantity > 100 OR order_item_ids_cost > 10000);
    
    -- Проверка 4: Basket combinations
    RETURN QUERY
    SELECT 
        'Basket Combinations'::TEXT,
        CASE WHEN COUNT(DISTINCT basket_id) > 0 THEN 'OK' ELSE 'ERROR' END,
        'Baskets: ' || COUNT(DISTINCT basket_id)::TEXT
    FROM basket_combinations
    WHERE order_id = p_order_id;
    
    -- Проверка 5: Delivery costs
    RETURN QUERY
    SELECT 
        'Delivery Costs Calculated'::TEXT,
        CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'MISSING' END,
        'Records: ' || COUNT(*)::TEXT
    FROM basket_delivery_costs
    WHERE basket_id IN (
        SELECT DISTINCT basket_id 
        FROM basket_combinations 
        WHERE order_id = p_order_id
    );
    
    -- Проверка 6: Basket analyses
    RETURN QUERY
    SELECT 
        'Basket Analysis'::TEXT,
        CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'MISSING' END,
        'Analyzed baskets: ' || COUNT(*)::TEXT || 
        ', Best score: ' || COALESCE(MIN(total_loss_and_delivery)::TEXT, 'N/A') || '₽'
    FROM basket_analyses
    WHERE order_id = p_order_id;
    
END;
$$ LANGUAGE plpgsql;

-- Примеры использования:
--
-- 1. Полный пересчет заказа:
-- CALL full_order_recalculation(1);
--
-- 2. Принудительный пересчет (даже заполненных):
-- CALL full_order_recalculation(1, TRUE);
--
-- 3. Проверка и исправление проблемных данных (dry run):
-- CALL fix_problematic_quantities(TRUE);
--
-- 4. Исправление проблемных данных:
-- CALL fix_problematic_quantities(FALSE);
--
-- 5. Диагностика заказа:
-- SELECT * FROM diagnose_order_calculations(1);
