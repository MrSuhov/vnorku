-- ==============================================================================
-- ФУНКЦИЯ ДЛЯ РАСЧЕТА ДОСТАВКИ
-- ==============================================================================

-- Функция расчета стоимости доставки для корзины в одном ЛСД
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
    
    -- Рассчитываем delivery_topup если есть min_order_amount
    delivery_topup := 0;
    IF v_min_order_amount IS NOT NULL AND v_min_order_amount > 0 THEN
        IF p_order_amount < v_min_order_amount THEN
            delivery_topup := v_min_order_amount - p_order_amount;
        END IF;
    END IF;
    
    -- Перебираем правила доставки
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
            
            -- Проверяем попадание в диапазон
            IF p_order_amount >= v_min AND (v_max IS NULL OR p_order_amount < v_max) THEN
                RETURN QUERY SELECT v_fee, delivery_topup, v_label;
                RETURN;
            END IF;
            
        ELSIF v_rule ? 'order_lower' THEN
            -- Модель с order_lower/order_upper
            v_order_lower := (v_rule->>'order_lower')::NUMERIC;
            v_order_upper := CASE 
                WHEN v_rule->>'order_upper' = 'null' OR v_rule->>'order_upper' IS NULL THEN NULL 
                ELSE (v_rule->>'order_upper')::NUMERIC 
            END;
            
            -- Проверяем попадание в диапазон
            IF p_order_amount >= v_order_lower AND (v_order_upper IS NULL OR p_order_amount < v_order_upper) THEN
                RETURN QUERY SELECT v_fee, delivery_topup, v_label;
                RETURN;
            END IF;
        END IF;
    END LOOP;
    
    -- Если ничего не подошло, возвращаем 0
    RETURN QUERY SELECT 0::NUMERIC(10,2), delivery_topup, 'No match'::TEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION calculate_delivery_fee(INTEGER, NUMERIC) IS 
'Рассчитывает стоимость доставки и delivery_topup для заказа в ЛСД';

-- ==============================================================================
-- ТЕСТЫ
-- ==============================================================================

-- Тест 1: Samokat (min_order=300, fee=300 если <300, иначе 0)
SELECT 'Samokat 200р' as test, * FROM calculate_delivery_fee(1, 200); -- fee=300, topup=100
SELECT 'Samokat 400р' as test, * FROM calculate_delivery_fee(1, 400); -- fee=0, topup=0

-- Тест 2: Yandex (диапазоны: 0-1150=134, 1150-1950=94, >1950=0)
SELECT 'Yandex 500р' as test, * FROM calculate_delivery_fee(2, 500);   -- fee=134
SELECT 'Yandex 1200р' as test, * FROM calculate_delivery_fee(2, 1200); -- fee=94
SELECT 'Yandex 2000р' as test, * FROM calculate_delivery_fee(2, 2000); -- fee=0

-- Тест 3: Ozon (min_order=500, fee=500 если <500, иначе 0)
SELECT 'Ozon 300р' as test, * FROM calculate_delivery_fee(3, 300);  -- fee=500, topup=200
SELECT 'Ozon 600р' as test, * FROM calculate_delivery_fee(3, 600);  -- fee=0, topup=0

-- Тест 4: VkusVill (всегда бесплатно)
SELECT 'VkusVill 100р' as test, * FROM calculate_delivery_fee(4, 100); -- fee=0
