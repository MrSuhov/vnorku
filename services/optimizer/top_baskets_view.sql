-- ==============================================================================
-- VIEW ДЛЯ ОТОБРАЖЕНИЯ ТОП-5 КОРЗИН С ПОЛНОЙ ИНФОРМАЦИЕЙ
-- ==============================================================================

-- Удаляем старую версию если существует
DROP VIEW IF EXISTS top_baskets_detailed CASCADE;

-- Создаем view для топ-5 корзин
CREATE OR REPLACE VIEW top_baskets_detailed AS
WITH 
-- Ранжируем корзины по оптимальности (loss + delivery)
ranked_baskets AS (
    SELECT 
        ba.order_id,
        ba.basket_id,
        ba.total_loss,
        ba.total_goods_cost,
        ba.delivery_cost,
        ba.delivery_topup,
        ba.total_delivery_cost,
        ba.total_cost,
        ba.total_loss_and_delivery,
        ROW_NUMBER() OVER (
            PARTITION BY ba.order_id 
            ORDER BY ba.total_loss_and_delivery, ba.total_cost
        ) as basket_rank
    FROM basket_analyses ba
),
-- Собираем детали по товарам в корзинах
basket_items_detailed AS (
    SELECT 
        bc.basket_id,
        bc.order_id,
        bc.order_item_id,
        bc.product_name,
        bc.lsd_name,
        bc.lsd_config_id,
        bc.order_item_ids_quantity as quantity_pieces,  -- количество в штуках
        bc.price as unit_price,  -- цена за единицу
        bc.order_item_ids_cost as item_total_cost,  -- стоимость позиции
        ls.product_url,  -- ссылка на товар
        bc.base_unit,
        bc.base_quantity
    FROM basket_combinations bc
    LEFT JOIN LATERAL (
        -- Находим соответствующий lsd_stock для получения product_url
        SELECT ls.product_url
        FROM lsd_stocks ls
        WHERE ls.order_item_id = bc.order_item_id
          AND ls.lsd_config_id = bc.lsd_config_id
          AND ls.price = bc.price
        ORDER BY ls.match_score DESC
        LIMIT 1
    ) ls ON true
),
-- Группируем товары по ЛСД внутри корзины
basket_by_lsd AS (
    SELECT 
        bid.basket_id,
        bid.order_id,
        bid.lsd_name,
        bid.lsd_config_id,
        jsonb_agg(
            jsonb_build_object(
                'product_name', bid.product_name,
                'quantity_pieces', bid.quantity_pieces,
                'unit_price', bid.unit_price,
                'item_total_cost', bid.item_total_cost,
                'product_url', bid.product_url,
                'base_unit', bid.base_unit,
                'base_quantity', bid.base_quantity
            ) ORDER BY bid.order_item_id
        ) as items,
        SUM(bid.item_total_cost) as lsd_subtotal
    FROM basket_items_detailed bid
    GROUP BY bid.basket_id, bid.order_id, bid.lsd_name, bid.lsd_config_id
)
-- Финальная выборка топ-5 корзин
SELECT 
    rb.order_id,
    rb.basket_rank as basket_number,
    rb.basket_id,
    -- Состав корзины по ЛСД
    jsonb_object_agg(
        bbl.lsd_name,
        jsonb_build_object(
            'lsd_config_id', bbl.lsd_config_id,
            'items', bbl.items,
            'subtotal', bbl.lsd_subtotal,
            'delivery_cost', COALESCE((rb.delivery_cost::jsonb->>bbl.lsd_name)::numeric, 0),
            'delivery_topup', COALESCE((rb.delivery_topup::jsonb->>bbl.lsd_name)::numeric, 0),
            'delivery_total', 
                COALESCE((rb.delivery_cost::jsonb->>bbl.lsd_name)::numeric, 0) + 
                COALESCE((rb.delivery_topup::jsonb->>bbl.lsd_name)::numeric, 0)
        )
    ) as basket_composition,
    -- Итоговые суммы
    rb.total_goods_cost,
    rb.total_delivery_cost,
    rb.total_cost,
    rb.total_loss,
    rb.total_loss_and_delivery
FROM ranked_baskets rb
JOIN basket_by_lsd bbl ON rb.basket_id = bbl.basket_id AND rb.order_id = bbl.order_id
WHERE rb.basket_rank <= 5  -- Только топ-5 корзин
GROUP BY 
    rb.order_id,
    rb.basket_rank,
    rb.basket_id,
    rb.total_goods_cost,
    rb.total_delivery_cost,
    rb.total_cost,
    rb.total_loss,
    rb.total_loss_and_delivery
ORDER BY rb.order_id, rb.basket_rank;

-- Добавляем комментарий
COMMENT ON VIEW top_baskets_detailed IS 'Топ-5 оптимальных корзин с полной детализацией по товарам и доставке';

-- ==============================================================================
-- ПРИМЕР ИСПОЛЬЗОВАНИЯ
-- ==============================================================================
-- SELECT * FROM top_baskets_detailed WHERE order_id = 16;
-- 
-- Результат будет содержать:
-- - basket_number: номер корзины (1-5)
-- - basket_composition: JSON с составом корзины по ЛСД:
--   {
--     "ЛСД_название": {
--       "lsd_config_id": 1,
--       "items": [
--         {
--           "product_name": "Молоко",
--           "quantity_pieces": 2,
--           "unit_price": 89.90,
--           "item_total_cost": 179.80,
--           "product_url": "https://...",
--           "base_unit": "л",
--           "base_quantity": 1.0
--         }
--       ],
--       "subtotal": 500.00,
--       "delivery_cost": 99.00,
--       "delivery_topup": 0.00,
--       "delivery_total": 99.00
--     }
--   }
-- - total_goods_cost: итого стоимость товаров
-- - total_delivery_cost: итого стоимость доставки
-- - total_cost: общая стоимость (товары + доставка)
