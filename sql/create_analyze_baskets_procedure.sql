-- Создаем процедуру для анализа корзин и записи результатов в basket_analyses
CREATE OR REPLACE PROCEDURE analyze_order_baskets(
    p_order_id INTEGER  -- ID заказа для анализа
) AS $$
DECLARE
    v_basket RECORD;
    v_analysis_id INTEGER;
BEGIN
    -- Проверяем, что order_id указан
    IF p_order_id IS NULL THEN
        RAISE EXCEPTION 'order_id is required';
    END IF;
    
    -- Удаляем старые записи анализа для этого заказа
    DELETE FROM basket_analyses WHERE order_id = p_order_id;
    
    -- Сначала убеждаемся, что рассчитана доставка для этого заказа
    CALL calculate_basket_delivery_costs(p_order_id);
    
    -- Для каждой корзины заказа создаем запись анализа
    FOR v_basket IN 
        WITH basket_aggregates AS (
            -- Агрегируем данные из basket_combinations
            SELECT 
                bc.basket_id,
                bc.order_id,
                SUM(bc.loss) as total_loss,
                SUM(bc.order_item_ids_cost) as total_goods_cost,
                -- Собираем информацию о товарах по ЛСД
                jsonb_object_agg(
                    bc.lsd_config_id::text,
                    jsonb_build_object(
                        'lsd_name', bc.lsd_name,
                        'items', bc.items_agg,
                        'cost', bc.cost_sum
                    )
                ) as lsd_items
            FROM (
                SELECT 
                    basket_id,
                    order_id,
                    lsd_config_id,
                    lsd_name,
                    SUM(loss) as loss,
                    SUM(order_item_ids_cost) as order_item_ids_cost,
                    SUM(order_item_ids_cost) as cost_sum,
                    jsonb_agg(
                        jsonb_build_object(
                            'product', product_name,
                            'quantity', order_item_ids_quantity,
                            'cost', order_item_ids_cost,
                            'loss', loss
                        )
                    ) as items_agg
                FROM basket_combinations
                WHERE order_id = p_order_id
                GROUP BY basket_id, order_id, lsd_config_id, lsd_name
            ) bc
            GROUP BY bc.basket_id, bc.order_id
        ),
        delivery_aggregates AS (
            -- Агрегируем данные о доставке
            SELECT 
                bdc.basket_id,
                -- Детали доставки по ЛСД
                jsonb_object_agg(
                    bdc.lsd_config_id::text,
                    jsonb_build_object(
                        'lsd_name', COALESCE(lc.name, bc.lsd_name),
                        'goods_cost', bdc.lsd_total_basket_cost,
                        'delivery_cost', bdc.delivery_cost,
                        'topup', bdc.topup,
                        'min_order', bdc.min_order_amount
                    )
                ) as delivery_details,
                -- Стоимости доставки
                SUM(bdc.delivery_cost) as total_delivery_cost,
                -- Список ЛСД с платной доставкой
                jsonb_agg(
                    COALESCE(lc.name, bc.lsd_name)
                ) FILTER (WHERE bdc.delivery_cost > 0) as paid_delivery_lsds,
                -- Промокоды (заглушка на будущее)
                '[]'::json as applied_promotions
            FROM basket_delivery_costs bdc
            LEFT JOIN lsd_configs lc ON lc.id = bdc.lsd_config_id
            LEFT JOIN (
                SELECT DISTINCT basket_id, lsd_config_id, lsd_name 
                FROM basket_combinations
                WHERE order_id = p_order_id
            ) bc ON bc.basket_id = bdc.basket_id AND bc.lsd_config_id = bdc.lsd_config_id
            WHERE bdc.basket_id IN (
                SELECT DISTINCT basket_id 
                FROM basket_combinations 
                WHERE order_id = p_order_id
            )
            GROUP BY bdc.basket_id
        )
        SELECT 
            ba.basket_id,
            ba.order_id,
            COALESCE(ba.total_goods_cost, 0) as total_goods_cost,
            COALESCE(da.total_delivery_cost, 0) as total_delivery_cost,
            COALESCE(ba.total_loss, 0) as total_loss,
            -- Общая стоимость (товары + доставка)
            COALESCE(ba.total_goods_cost + da.total_delivery_cost, 0) as total_cost,
            -- Экономия (потенциальная, пока 0)
            0 as total_savings,
            -- Формируем JSON с разбивкой по ЛСД
            jsonb_build_object(
                'lsd_breakdown', COALESCE(
                    (
                        SELECT jsonb_object_agg(
                            lsd_key,
                            jsonb_build_object(
                                'lsd_name', (ba.lsd_items->lsd_key->>'lsd_name'),
                                'items', (ba.lsd_items->lsd_key->'items'),
                                'goods_cost', (ba.lsd_items->lsd_key->>'cost')::numeric,
                                'delivery_cost', (da.delivery_details->lsd_key->>'delivery_cost')::numeric,
                                'topup', (da.delivery_details->lsd_key->>'topup')::numeric,
                                'min_order', (da.delivery_details->lsd_key->>'min_order')::numeric,
                                'total_cost', 
                                    (ba.lsd_items->lsd_key->>'cost')::numeric + 
                                    COALESCE((da.delivery_details->lsd_key->>'delivery_cost')::numeric, 0)
                            )
                        )
                        FROM jsonb_object_keys(ba.lsd_items) as lsd_key
                    ),
                    '{}'::jsonb
                ),
                'summary', jsonb_build_object(
                    'total_goods_cost', ba.total_goods_cost,
                    'total_delivery_cost', da.total_delivery_cost,
                    'total_loss', ba.total_loss,
                    'optimization_score', 
                        CASE 
                            WHEN ba.total_loss + da.total_delivery_cost = 0 THEN 1
                            ELSE ROUND(1 / (1 + (ba.total_loss + da.total_delivery_cost) / 1000.0), 3)
                        END
                )
            ) as lsd_breakdown_json,
            -- Стоимости доставки по ЛСД (отдельно для удобства)
            da.delivery_details as delivery_costs_json,
            -- Примененные промокоды
            da.applied_promotions
        FROM basket_aggregates ba
        LEFT JOIN delivery_aggregates da ON da.basket_id = ba.basket_id
        WHERE ba.order_id = p_order_id
    LOOP
        -- Вставляем запись в basket_analyses
        INSERT INTO basket_analyses (
            order_id,
            lsd_breakdown,
            total_cost,
            total_savings,
            delivery_costs,
            applied_promotions
        ) VALUES (
            v_basket.order_id,
            v_basket.lsd_breakdown_json,
            v_basket.total_cost,
            v_basket.total_savings,
            v_basket.delivery_costs_json,
            v_basket.applied_promotions
        ) RETURNING id INTO v_analysis_id;
        
        -- Логируем прогресс (опционально)
        IF v_basket.basket_id % 100 = 0 THEN
            RAISE NOTICE 'Обработано % корзин', v_basket.basket_id;
        END IF;
    END LOOP;
    
    -- Выводим итоговую статистику
    RAISE NOTICE 'Анализ завершен для заказа %. Создано % записей в basket_analyses', 
        p_order_id,
        (SELECT COUNT(*) FROM basket_analyses WHERE order_id = p_order_id);
END;
$$ LANGUAGE plpgsql;

-- Создаем функцию для получения топ N корзин из basket_analyses
CREATE OR REPLACE FUNCTION get_top_analyzed_baskets(
    p_order_id INTEGER,
    p_limit INTEGER DEFAULT 10
) RETURNS TABLE (
    analysis_id INTEGER,
    order_id INTEGER,
    total_cost NUMERIC(10,2),
    total_loss NUMERIC,
    total_delivery NUMERIC,
    optimization_score NUMERIC,
    lsd_count BIGINT,
    best_lsd TEXT,
    delivery_status TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH analysis_details AS (
        SELECT 
            ba.id as analysis_id,
            ba.order_id,
            ba.total_cost,
            (ba.lsd_breakdown->'summary'->>'total_loss')::numeric as total_loss,
            (ba.lsd_breakdown->'summary'->>'total_delivery_cost')::numeric as total_delivery,
            (ba.lsd_breakdown->'summary'->>'optimization_score')::numeric as optimization_score,
            jsonb_object_keys(ba.lsd_breakdown->'lsd_breakdown') as lsd_keys,
            ba.delivery_costs
        FROM basket_analyses ba
        WHERE ba.order_id = p_order_id
    ),
    aggregated AS (
        SELECT 
            ad.analysis_id,
            ad.order_id,
            ad.total_cost,
            ad.total_loss,
            ad.total_delivery,
            ad.optimization_score,
            COUNT(DISTINCT ad.lsd_keys) as lsd_count,
            -- Находим ЛСД с минимальной итоговой стоимостью
            (
                SELECT (value->>'lsd_name')::text
                FROM jsonb_each(ad.delivery_costs) 
                ORDER BY (value->>'goods_cost')::numeric + (value->>'delivery_cost')::numeric
                LIMIT 1
            ) as best_lsd,
            CASE 
                WHEN ad.total_delivery = 0 THEN 'Бесплатная доставка'
                WHEN ad.total_delivery < 200 THEN 'Недорогая доставка'
                WHEN ad.total_delivery < 500 THEN 'Средняя доставка'
                ELSE 'Дорогая доставка'
            END as delivery_status
        FROM analysis_details ad
        GROUP BY 
            ad.analysis_id, 
            ad.order_id, 
            ad.total_cost, 
            ad.total_loss, 
            ad.total_delivery,
            ad.optimization_score,
            ad.delivery_costs
    )
    SELECT 
        a.analysis_id,
        a.order_id,
        a.total_cost,
        a.total_loss,
        a.total_delivery,
        a.optimization_score,
        a.lsd_count,
        a.best_lsd,
        a.delivery_status
    FROM aggregated a
    ORDER BY a.optimization_score DESC, (a.total_loss + a.total_delivery) ASC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Создаем view для удобного просмотра результатов анализа
CREATE OR REPLACE VIEW v_basket_analyses_summary AS
SELECT 
    ba.id,
    ba.order_id,
    ba.total_cost,
    (ba.lsd_breakdown->'summary'->>'total_goods_cost')::numeric as total_goods_cost,
    (ba.lsd_breakdown->'summary'->>'total_delivery_cost')::numeric as total_delivery_cost,
    (ba.lsd_breakdown->'summary'->>'total_loss')::numeric as total_loss,
    (ba.lsd_breakdown->'summary'->>'optimization_score')::numeric as optimization_score,
    -- Подсчет количества ЛСД
    (
        SELECT COUNT(*)::integer 
        FROM jsonb_object_keys(ba.lsd_breakdown->'lsd_breakdown')
    ) as lsd_count,
    -- Критерий оптимизации
    (ba.lsd_breakdown->'summary'->>'total_loss')::numeric + 
    (ba.lsd_breakdown->'summary'->>'total_delivery_cost')::numeric as optimization_criterion,
    ba.created_at
FROM basket_analyses ba;

-- Примеры использования:
--
-- 1. Запуск анализа для заказа:
-- CALL analyze_order_baskets(1);
--
-- 2. Получение топ-10 оптимальных корзин:
-- SELECT * FROM get_top_analyzed_baskets(1, 10);
--
-- 3. Просмотр всех результатов анализа:
-- SELECT * FROM v_basket_analyses_summary WHERE order_id = 1 ORDER BY optimization_criterion LIMIT 20;
--
-- 4. Детальный просмотр конкретной корзины:
-- SELECT lsd_breakdown FROM basket_analyses WHERE id = 1;
