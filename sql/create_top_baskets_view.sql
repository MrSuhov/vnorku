-- Создаем view top_baskets для анализа оптимальных корзин
CREATE OR REPLACE VIEW top_baskets AS
WITH basket_aggregates AS (
    -- Агрегируем данные из basket_combinations
    SELECT 
        bc.basket_id,
        SUM(bc.loss) as total_loss,
        SUM(bc.order_item_ids_cost) as total_goods_cost
    FROM basket_combinations bc
    GROUP BY bc.basket_id
),
delivery_aggregates AS (
    -- Агрегируем данные о доставке в JSON формат
    SELECT 
        bdc.basket_id,
        -- JSON с стоимостью доставки по ЛСД
        jsonb_object_agg(
            COALESCE(lc.name, bc.lsd_name), 
            bdc.delivery_cost
        ) as delivery_cost,
        -- JSON с топапами по ЛСД
        jsonb_object_agg(
            COALESCE(lc.name, bc.lsd_name), 
            bdc.topup
        ) as delivery_topup,
        -- Сумма всех стоимостей доставки
        SUM(bdc.delivery_cost) as sum_delivery_cost,
        -- Сумма всех топапов
        SUM(bdc.topup) as sum_topup
    FROM basket_delivery_costs bdc
    LEFT JOIN lsd_configs lc ON lc.id = bdc.lsd_config_id
    LEFT JOIN (
        SELECT DISTINCT basket_id, lsd_config_id, lsd_name 
        FROM basket_combinations
    ) bc ON bc.basket_id = bdc.basket_id AND bc.lsd_config_id = bdc.lsd_config_id
    GROUP BY bdc.basket_id
)
SELECT 
    ba.basket_id,
    COALESCE(ba.total_loss, 0)::NUMERIC(10,2) as total_loss,
    COALESCE(ba.total_goods_cost, 0)::NUMERIC(10,2) as total_goods_cost,
    da.delivery_cost::JSON as delivery_cost,
    da.delivery_topup::JSON as delivery_topup,
    COALESCE(da.sum_delivery_cost + da.sum_topup, 0)::NUMERIC(10,2) as total_delivery_cost,
    COALESCE(ba.total_goods_cost + da.sum_delivery_cost + da.sum_topup, 0)::NUMERIC(10,2) as total_cost,
    COALESCE(ba.total_loss + da.sum_delivery_cost + da.sum_topup, 0)::NUMERIC(10,2) as total_loss_and_delivery
FROM basket_aggregates ba
LEFT JOIN delivery_aggregates da ON da.basket_id = ba.basket_id
ORDER BY COALESCE(ba.total_loss + da.sum_delivery_cost + da.sum_topup, 0) ASC;

-- Создаем индексы для улучшения производительности
CREATE INDEX IF NOT EXISTS idx_basket_combinations_basket_id 
ON basket_combinations(basket_id);

CREATE INDEX IF NOT EXISTS idx_basket_combinations_composite 
ON basket_combinations(basket_id, loss, order_item_ids_cost);

-- Создаем функцию для получения топ N корзин
CREATE OR REPLACE FUNCTION get_top_baskets(
    p_limit INTEGER DEFAULT 10
) RETURNS TABLE (
    basket_id INTEGER,
    total_loss NUMERIC(10,2),
    total_goods_cost NUMERIC(10,2),
    delivery_cost JSON,
    delivery_topup JSON,
    total_delivery_cost NUMERIC(10,2),
    total_cost NUMERIC(10,2),
    total_loss_and_delivery NUMERIC(10,2),
    lsd_breakdown TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        tb.basket_id,
        tb.total_loss,
        tb.total_goods_cost,
        tb.delivery_cost,
        tb.delivery_topup,
        tb.total_delivery_cost,
        tb.total_cost,
        tb.total_loss_and_delivery,
        -- Добавляем текстовое представление для удобства
        CONCAT(
            'Товары: ', tb.total_goods_cost::TEXT, '₽, ',
            'Доставка: ', tb.total_delivery_cost::TEXT, '₽, ',
            'Потери: ', tb.total_loss::TEXT, '₽'
        ) as lsd_breakdown
    FROM top_baskets tb
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Создаем материализованное представление для ускорения запросов (опционально)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_top_baskets AS
SELECT * FROM top_baskets;

-- Создаем индекс на материализованном представлении
CREATE INDEX IF NOT EXISTS idx_mv_top_baskets_total_loss_and_delivery 
ON mv_top_baskets(total_loss_and_delivery);

-- Функция для обновления материализованного представления
CREATE OR REPLACE FUNCTION refresh_top_baskets()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW mv_top_baskets;
    RAISE NOTICE 'Материализованное представление mv_top_baskets обновлено';
END;
$$ LANGUAGE plpgsql;

-- Примеры использования:
-- 
-- 1. Просмотр всех корзин отсортированных по оптимальности:
-- SELECT * FROM top_baskets;
--
-- 2. Получить топ-10 самых оптимальных корзин:
-- SELECT * FROM get_top_baskets(10);
--
-- 3. Найти корзины где доставка больше стоимости товаров:
-- SELECT * FROM top_baskets WHERE total_delivery_cost > total_goods_cost;
--
-- 4. Анализ корзин с минимальными потерями:
-- SELECT * FROM top_baskets WHERE total_loss < 100 LIMIT 20;
--
-- 5. Использование материализованного представления (быстрее):
-- SELECT * FROM mv_top_baskets LIMIT 10;
-- 
-- 6. Обновление материализованного представления:
-- SELECT refresh_top_baskets();
