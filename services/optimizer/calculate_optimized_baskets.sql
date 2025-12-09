-- ==============================================================================
-- ПРОЦЕДУРА: Расчет доставки и сохранение топ-N корзин
-- ==============================================================================

-- Процедура 3: Расчет оптимальных корзин с доставкой и сохранение в basket_analyses
CREATE OR REPLACE PROCEDURE calculate_optimized_baskets(
    p_order_id INTEGER,
    p_top_n INTEGER DEFAULT 3
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_basket RECORD;
    v_lsd_costs JSONB := '{}'::JSONB;
    v_delivery_costs JSONB := '{}'::JSONB;
    v_total_delivery NUMERIC(10,2);
    v_lsd_subtotal NUMERIC(10,2);
    v_delivery_fee NUMERIC(10,2);
    v_delivery_topup NUMERIC(10,2);
    v_applied_rule TEXT;
BEGIN
    -- Удаляем старые результаты для этого заказа
    DELETE FROM basket_analyses WHERE order_id = p_order_id;
    
    -- Для каждой валидной корзины (топ-N по loss)
    FOR v_basket IN 
        SELECT *
        FROM valid_baskets
        WHERE order_id = p_order_id
        ORDER BY total_loss, total_goods_cost
        LIMIT p_top_n
    LOOP
        -- Инициализируем
        v_lsd_costs := '{}'::JSONB;
        v_delivery_costs := '{}'::JSONB;
        v_total_delivery := 0;
        
        -- Товар 1
        v_lsd_subtotal := COALESCE((v_lsd_costs->v_basket.lsd_1->>'subtotal')::NUMERIC, 0) + 
                          v_basket.pieces_1 * v_basket.price_1;
        v_lsd_costs := jsonb_set(
            v_lsd_costs,
            ARRAY[v_basket.lsd_1],
            jsonb_build_object('subtotal', v_lsd_subtotal),
            true
        );
        
        -- Товар 2
        v_lsd_subtotal := COALESCE((v_lsd_costs->v_basket.lsd_2->>'subtotal')::NUMERIC, 0) + 
                          v_basket.pieces_2 * v_basket.price_2;
        v_lsd_costs := jsonb_set(
            v_lsd_costs,
            ARRAY[v_basket.lsd_2],
            jsonb_build_object('subtotal', v_lsd_subtotal),
            true
        );
        
        -- Товар 3
        v_lsd_subtotal := COALESCE((v_lsd_costs->v_basket.lsd_3->>'subtotal')::NUMERIC, 0) + 
                          v_basket.pieces_3 * v_basket.price_3;
        v_lsd_costs := jsonb_set(
            v_lsd_costs,
            ARRAY[v_basket.lsd_3],
            jsonb_build_object('subtotal', v_lsd_subtotal),
            true
        );
        
        -- Товар 4
        v_lsd_subtotal := COALESCE((v_lsd_costs->v_basket.lsd_4->>'subtotal')::NUMERIC, 0) + 
                          v_basket.pieces_4 * v_basket.price_4;
        v_lsd_costs := jsonb_set(
            v_lsd_costs,
            ARRAY[v_basket.lsd_4],
            jsonb_build_object('subtotal', v_lsd_subtotal),
            true
        );
        
        -- Рассчитываем доставку для каждого ЛСД
        -- ЛСД 1
        SELECT delivery_fee, delivery_topup, applied_rule 
        INTO v_delivery_fee, v_delivery_topup, v_applied_rule
        FROM calculate_delivery_fee(
            v_basket.lsd_config_1, 
            (v_lsd_costs->v_basket.lsd_1->>'subtotal')::NUMERIC
        );
        v_delivery_costs := jsonb_set(
            v_delivery_costs,
            ARRAY[v_basket.lsd_1],
            jsonb_build_object('fee', v_delivery_fee, 'topup', v_delivery_topup),
            true
        );
        v_total_delivery := v_total_delivery + v_delivery_fee + v_delivery_topup;
        
        -- ЛСД 2 (если отличается от ЛСД 1)
        IF v_basket.lsd_2 != v_basket.lsd_1 THEN
            SELECT delivery_fee, delivery_topup, applied_rule 
            INTO v_delivery_fee, v_delivery_topup, v_applied_rule
            FROM calculate_delivery_fee(
                v_basket.lsd_config_2, 
                (v_lsd_costs->v_basket.lsd_2->>'subtotal')::NUMERIC
            );
            v_delivery_costs := jsonb_set(
                v_delivery_costs,
                ARRAY[v_basket.lsd_2],
                jsonb_build_object('fee', v_delivery_fee, 'topup', v_delivery_topup),
                true
            );
            v_total_delivery := v_total_delivery + v_delivery_fee + v_delivery_topup;
        END IF;
        
        -- ЛСД 3 (если отличается от предыдущих)
        IF v_basket.lsd_3 != v_basket.lsd_1 AND v_basket.lsd_3 != v_basket.lsd_2 THEN
            SELECT delivery_fee, delivery_topup, applied_rule 
            INTO v_delivery_fee, v_delivery_topup, v_applied_rule
            FROM calculate_delivery_fee(
                v_basket.lsd_config_3, 
                (v_lsd_costs->v_basket.lsd_3->>'subtotal')::NUMERIC
            );
            v_delivery_costs := jsonb_set(
                v_delivery_costs,
                ARRAY[v_basket.lsd_3],
                jsonb_build_object('fee', v_delivery_fee, 'topup', v_delivery_topup),
                true
            );
            v_total_delivery := v_total_delivery + v_delivery_fee + v_delivery_topup;
        END IF;
        
        -- ЛСД 4 (если отличается от предыдущих)
        IF v_basket.lsd_4 != v_basket.lsd_1 AND v_basket.lsd_4 != v_basket.lsd_2 AND v_basket.lsd_4 != v_basket.lsd_3 THEN
            SELECT delivery_fee, delivery_topup, applied_rule 
            INTO v_delivery_fee, v_delivery_topup, v_applied_rule
            FROM calculate_delivery_fee(
                v_basket.lsd_config_4, 
                (v_lsd_costs->v_basket.lsd_4->>'subtotal')::NUMERIC
            );
            v_delivery_costs := jsonb_set(
                v_delivery_costs,
                ARRAY[v_basket.lsd_4],
                jsonb_build_object('fee', v_delivery_fee, 'topup', v_delivery_topup),
                true
            );
            v_total_delivery := v_total_delivery + v_delivery_fee + v_delivery_topup;
        END IF;
        
        -- Сохраняем результат в basket_analyses
        INSERT INTO basket_analyses (
            order_id,
            lsd_breakdown,
            total_cost,
            total_savings,
            delivery_costs,
            applied_promotions
        ) VALUES (
            p_order_id,
            v_lsd_costs::JSON,
            (v_basket.total_goods_cost + v_total_delivery)::NUMERIC(10,2),
            v_basket.total_loss::NUMERIC(10,2),
            v_delivery_costs::JSON,
            '{}'::JSON  -- промокоды пока не используем
        );
    END LOOP;
    
    RAISE NOTICE 'Сохранено % оптимизированных корзин для заказа %', p_top_n, p_order_id;
END;
$$;

COMMENT ON PROCEDURE calculate_optimized_baskets(INTEGER, INTEGER) IS 
'Рассчитывает доставку для топ-N корзин и сохраняет результаты в basket_analyses';

-- Пример использования:
-- CALL calculate_optimized_baskets(1, 3);
-- SELECT * FROM basket_analyses WHERE order_id = 1;
