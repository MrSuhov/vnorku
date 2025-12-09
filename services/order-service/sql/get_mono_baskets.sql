-- Получение моно-корзин с деталями для PDF-отчета
-- Параметры: order_id
-- Моно-корзина = корзина где все товары из одного LSD
-- 
-- ВАЖНО: delivery_cost_model берётся из актуальных данных lsd_stocks через basket_combinations,
-- а не из устаревших данных lsd_configs

WITH mono_basket_ids AS (
    -- Находим ID корзин, которые являются моно-корзинами (один LSD)
    SELECT 
        basket_id,
        order_id
    FROM basket_combinations
    WHERE order_id = :order_id
    GROUP BY basket_id, order_id
    HAVING COUNT(DISTINCT lsd_config_id) = 1
),
mono_baskets_base AS (
    -- Получаем базовые данные моно-корзин с актуальным delivery_cost_model
    SELECT DISTINCT ON (ba.basket_id)
        ba.basket_id,
        ba.order_id,
        bc.lsd_config_id,
        lc.display_name as lsd_display_name,
        ba.total_cost,
        ba.total_goods_cost,
        ba.total_delivery_cost,
        ba.total_loss,
        ba.delivery_topup,
        lc.delivery_fixed_fee,
        -- Используем актуальный delivery_cost_model из basket_combinations
        -- (он копируется туда из lsd_stocks при создании корзины)
        bc.delivery_cost_model
    FROM basket_analyses ba
    JOIN mono_basket_ids mbi ON mbi.basket_id = ba.basket_id AND mbi.order_id = ba.order_id
    JOIN basket_combinations bc ON bc.basket_id = ba.basket_id AND bc.order_id = ba.order_id
    JOIN lsd_configs lc ON lc.id = bc.lsd_config_id
    WHERE ba.order_id = :order_id
    ORDER BY ba.basket_id, ba.total_cost ASC
)
SELECT 
    mb.basket_id,
    mb.lsd_display_name,
    mb.total_cost,
    mb.total_goods_cost,
    mb.total_delivery_cost,
    mb.total_loss,
    mb.delivery_topup,
    mb.delivery_fixed_fee,
    mb.delivery_cost_model,
    COALESCE(
        (
            SELECT json_agg(
                json_build_object(
                    'product_name', bc.product_name,
                    'base_quantity', bc.base_quantity,
                    'base_unit', bc.base_unit,
                    'price', bc.price,
                    'fprice', bc.fprice,
                    'fprice_min', bc.fprice_min,
                    'loss', bc.loss,
                    'order_item_ids_cost', bc.order_item_ids_cost,
                    'order_item_ids_quantity', bc.order_item_ids_quantity,
                    'requested_quantity', oi.requested_quantity,
                    'requested_unit', oi.requested_unit
                ) ORDER BY bc.product_name
            )
            FROM basket_combinations bc
            JOIN order_items oi ON oi.id = bc.order_item_id
            WHERE bc.basket_id = mb.basket_id
              AND bc.order_id = :order_id
        ),
        '[]'::json
    ) as items
FROM mono_baskets_base mb
ORDER BY mb.total_cost ASC;
