-- ==============================================================================
-- ФУНКЦИЯ ДЛЯ РАСЧЕТА ДОСТАВКИ (ИСПРАВЛЕННАЯ ВЕРСИЯ)
-- ==============================================================================
-- КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Если есть топап И попадаем в первый диапазон,
-- то delivery_fee = fee_первого_диапазона - min_order_amount

DROP FUNCTION IF EXISTS calculate_delivery_fee(INTEGER, NUMERIC);

CREATE OR REPLACE FUNCTION calculate_delivery_fee(
    p_lsd_config_id INTEGER,
    p_order_amount NUMERIC(10,2)
) RETURNS TABLE (
    delivery_fee NUMERIC(10,2),
    delivery_topup NUMERIC(10,2),
    applied_rule TEXT
) AS $$
DECLARE
    v_delivery_model JSONB;
    v_min_order_amount NUMERIC(10,2);
    v_rule JSONB;
    v_fee NUMERIC(10,2);
    v_min NUMERIC;
    v_max NUMERIC;
    v_order_lower NUMERIC;
    v_order_upper NUMERIC;
    v_label TEXT;
    v_has_topup BOOLEAN;
    v_adjusted_order_amount NUMERIC(10,2);
    v_original_order_amount NUMERIC(10,2);
BEGIN
    -- Получаем модель доставки и min_order_amount
    SELECT 
        lc.delivery_cost_model::JSONB,
        lc.min_order_amount
    INTO v_delivery_model, v_min_order_amount
    FROM lsd_configs lc
    WHERE lc.id = p_lsd_config_id;
    
    -- Если модели нет, возвращаем 0
    IF v_delivery_model IS NULL THEN
        RETURN QUERY SELECT 0::NUMERIC(10,2), 0::NUMERIC(10,2), 'No model'::TEXT;
        RETURN;
    END IF;
    
    -- Сохраняем оригинальную сумму
    v_original_order_amount := p_order_amount;
    v_adjusted_order_amount := p_order_amount;
    v_has_topup := FALSE;
    
    -- Рассчитываем delivery_topup если есть min_order_amount
    delivery_topup := 0;
    IF v_min_order_amount IS NOT NULL AND v_min_order_amount > 0 THEN
        IF p_order_amount < v_min_order_amount THEN
            delivery_topup := v_min_order_amount - p_order_amount;
            v_adjusted_order_amount := v_min_order_amount;
            v_has_topup := TRUE;
        END IF;
    END IF;
    
    -- Перебираем правила доставки (используем adjusted для выбора диапазона)
    FOR v_rule IN SELECT * FROM jsonb_array_elements(v_delivery_model->'delivery_cost')
    LOOP
        v_fee := (v_rule->>'fee')::NUMERIC;
        v_label := v_rule->>'label';
        
        -- Проверяем тип модели (min/max или order_lower/order_upper)
        IF v_rule ? 'min' THEN
            -- Модель с min/max
            v_min := (v_rule->>'min')::NUMERIC;
            v_max := CASE 
                WHEN v_rule->>'max' = 'null' OR v_rule->>'max' IS NULL THEN NULL 
                ELSE (v_rule->>'max')::NUMERIC 
            END;
            
            -- Проверяем попадание adjusted_order_amount в диапазон
            IF v_adjusted_order_amount >= v_min AND (v_max IS NULL OR v_adjusted_order_amount < v_max) THEN
                -- НОВАЯ ЛОГИКА: если есть топап И это первый диапазон (min=0)
                -- то вычитаем min_order_amount из fee
                delivery_fee := v_fee;
                IF v_has_topup AND v_min = 0 THEN
                    -- Проверяем что оригинальная сумма попадает в этот диапазон
                    IF v_original_order_amount >= v_min AND (v_max IS NULL OR v_original_order_amount < v_max) THEN
                        delivery_fee := GREATEST(0, v_fee - v_min_order_amount);
                    END IF;
                END IF;
                
                RETURN QUERY SELECT delivery_fee, delivery_topup, v_label;
                RETURN;
            END IF;
            
        ELSIF v_rule ? 'order_lower' THEN
            -- Модель с order_lower/order_upper
            v_order_lower := (v_rule->>'order_lower')::NUMERIC;
            v_order_upper := CASE 
                WHEN v_rule->>'order_upper' = 'null' OR v_rule->>'order_upper' IS NULL THEN NULL 
                ELSE (v_rule->>'order_upper')::NUMERIC 
            END;
            
            -- Проверяем попадание adjusted_order_amount в диапазон
            IF v_adjusted_order_amount >= v_order_lower AND (v_order_upper IS NULL OR v_adjusted_order_amount < v_order_upper) THEN
                -- НОВАЯ ЛОГИКА: если есть топап И это первый диапазон (order_lower=0)
                delivery_fee := v_fee;
                IF v_has_topup AND v_order_lower = 0 THEN
                    -- Проверяем что оригинальная сумма попадает в этот диапазон
                    IF v_original_order_amount >= v_order_lower AND (v_order_upper IS NULL OR v_original_order_amount < v_order_upper) THEN
                        delivery_fee := GREATEST(0, v_fee - v_min_order_amount);
                    END IF;
                END IF;
                
                RETURN QUERY SELECT delivery_fee, delivery_topup, v_label;
                RETURN;
            END IF;
        END IF;
    END LOOP;
    
    -- Если ничего не подошло, возвращаем 0
    RETURN QUERY SELECT 0::NUMERIC(10,2), delivery_topup, 'No match'::TEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION calculate_delivery_fee(INTEGER, NUMERIC) IS 
'Рассчитывает стоимость доставки и delivery_topup для заказа в ЛСД. 
ИСПРАВЛЕНО: Если есть топап И попадаем в первый диапазон, то delivery_fee = fee - min_order_amount';

-- ==============================================================================
-- ТЕСТЫ
-- ==============================================================================

-- Тест на Ozon с новой логикой
-- Модель: диапазон 1: 0-500₽ fee=579₽, диапазон 2: 500+₽ fee=79₽
-- min_order_amount = 499.99₽

SELECT 'Ozon 128₽ (с топапом)' as test, * FROM calculate_delivery_fee(3, 128);
-- Ожидается: delivery_fee = 579 - 499.99 = 79.01₽, topup = 371.99₽

SELECT 'Ozon 300₽ (с топапом)' as test, * FROM calculate_delivery_fee(3, 300);
-- Ожидается: delivery_fee = 579 - 499.99 = 79.01₽, topup = 199.99₽

SELECT 'Ozon 500₽ (без топапа)' as test, * FROM calculate_delivery_fee(3, 500);
-- Ожидается: delivery_fee = 79₽, topup = 0₽

SELECT 'Ozon 600₽ (без топапа)' as test, * FROM calculate_delivery_fee(3, 600);
-- Ожидается: delivery_fee = 79₽, topup = 0₽
