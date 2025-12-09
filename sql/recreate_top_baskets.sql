-- Пересоздаем view top_baskets с учетом новой структуры basket_delivery_costs
CREATE OR REPLACE VIEW top_baskets AS
WITH basket_aggregates AS (
    -- Агрегируем данные из basket_combinations
    SELECT 
        bc.basket_id,
        bc.order_id,
        SUM(bc.loss) as total_loss,
        SUM(bc.order_item_ids_cost) as total_goods_cost
    FROM basket_combinations bc
    GROUP BY bc.basket_id, bc.order_id
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
        -- Сумма всех топапов (для информации, не складываем в total_delivery_cost)
        SUM(bdc.topup) as sum_topup,
        -- Максимальный топап (если докупать в одном ЛСД)
        MAX(bdc.topup) as max_topup
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
    ba.order_id,
    COALESCE(ba.total_loss, 0)::NUMERIC(10,2) as total_loss,
    COALESCE(ba.total_goods_cost, 0)::NUMERIC(10,2) as total_goods_cost,
    da.delivery_cost::JSON as delivery_cost,
    da.delivery_topup::JSON as delivery_topup,
    -- Стоимость доставки - это только сумма delivery_cost (топап - это не стоимость доставки, а доплата до бесплатной)
    COALESCE(da.sum_delivery_cost, 0)::NUMERIC(10,2) as total_delivery_cost,
    -- Общая стоимость = товары + доставка
    COALESCE(ba.total_goods_cost + da.sum_delivery_cost, 0)::NUMERIC(10,2) as total_cost,
    -- Критерий оптимизации = потери + стоимость доставки
    COALESCE(ba.total_loss + da.sum_delivery_cost, 0)::NUMERIC(10,2) as total_loss_and_delivery
FROM basket_aggregates ba
LEFT JOIN delivery_aggregates da ON da.basket_id = ba.basket_id
ORDER BY COALESCE(ba.total_loss + da.sum_delivery_cost, 0) ASC;

-- Проверочный запрос для basket_id = 1
SELECT 
    '=== Проверка расчетов для basket_id = 1 ===' as info;

SELECT 
    'Данные из basket_combinations:' as description,
    NULL as value
UNION ALL
SELECT 
    '  Товары в Яндекс (lsd=2)',
    SUM(order_item_ids_cost)::TEXT || '₽'
FROM basket_combinations 
WHERE basket_id = 1 AND lsd_config_id = 2
UNION ALL
SELECT 
    '  Товары в Озон (lsd=3)',
    SUM(order_item_ids_cost)::TEXT || '₽'
FROM basket_combinations 
WHERE basket_id = 1 AND lsd_config_id = 3
UNION ALL
SELECT 
    '  Товары в Пятерочка (lsd=7)',
    SUM(order_item_ids_cost)::TEXT || '₽'
FROM basket_combinations 
WHERE basket_id = 1 AND lsd_config_id = 7
UNION ALL
SELECT 
    '  Общая стоимость товаров',
    SUM(order_item_ids_cost)::TEXT || '₽'
FROM basket_combinations 
WHERE basket_id = 1
UNION ALL
SELECT 
    '  Общие потери',
    SUM(loss)::TEXT || '₽'
FROM basket_combinations 
WHERE basket_id = 1;

SELECT 
    'Расчет доставки:' as description,
    NULL as value
UNION ALL
SELECT 
    '  ' || lsd_name || ': товары ' || lsd_total_basket_cost::TEXT || '₽',
    'доставка ' || delivery_cost::TEXT || '₽' || 
    CASE WHEN topup > 0 THEN ' (докупить ' || topup::TEXT || '₽ до бесплатной)' ELSE '' END
FROM v_basket_delivery_analysis
WHERE basket_id = 1
ORDER BY lsd_config_id;

SELECT 
    'Итоги для корзины:' as description,
    value
FROM (
    SELECT 1 as ord, 'Общая стоимость товаров' as description, total_goods_cost::TEXT || '₽' as value
    FROM top_baskets WHERE basket_id = 1
    UNION ALL
    SELECT 2, 'Общая стоимость доставки', total_delivery_cost::TEXT || '₽'
    FROM top_baskets WHERE basket_id = 1
    UNION ALL
    SELECT 3, 'Общие потери', total_loss::TEXT || '₽'
    FROM top_baskets WHERE basket_id = 1
    UNION ALL
    SELECT 4, 'Критерий оптимизации (потери+доставка)', total_loss_and_delivery::TEXT || '₽'
    FROM top_baskets WHERE basket_id = 1
) t
ORDER BY ord;
