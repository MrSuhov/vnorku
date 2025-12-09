-- Получение монокорзин по LSD: показывает все найденные RPA товары
-- Параметры: order_id
-- Возвращает данные для каждого LSD из lsd_stocks (match_score > 0.75)
--
-- Для каждого LSD показываем:
-- 1. Найденные товары (лучшее предложение для каждого товара в данном LSD)
-- 2. Не найденные товары (из order_items, которых нет в lsd_stocks для этого LSD)
-- 3. Расчет итоговой стоимости (товары + топап + доставка)

WITH active_lsds AS (
    -- Находим все LSD, которые нашли хотя бы один товар с хорошим match_score
    SELECT DISTINCT ON (ls.lsd_config_id)
        ls.lsd_config_id,
        lc.delivery_cost_model
    FROM lsd_stocks ls
    JOIN lsd_configs lc ON lc.id = ls.lsd_config_id
    WHERE ls.order_id = :order_id
      AND ls.match_score > 0.75
    ORDER BY ls.lsd_config_id
),
best_lsd_items AS (
    -- Для каждого LSD берем лучшее (минимальное по fprice) предложение для каждого товара
    SELECT DISTINCT ON (ls.lsd_config_id, ls.order_item_id)
        ls.lsd_config_id,
        ls.order_item_id,
        oi.product_name,
        ls.base_quantity,
        ls.base_unit,
        ls.price,
        ls.fprice,
        -- Глобальный минимум fprice для этого товара среди всех LSD
        (
            SELECT MIN(ls2.fprice)
            FROM lsd_stocks ls2
            WHERE ls2.order_item_id = ls.order_item_id
              AND ls2.order_id = :order_id
              AND ls2.match_score > 0.75
        ) as fprice_min,
        oi.requested_quantity,
        oi.requested_unit,
        -- ИСПОЛЬЗУЕМ ГОТОВЫЕ ЗНАЧЕНИЯ ИЗ lsd_stocks
        ls.order_item_ids_quantity,
        -- FALLBACK: если order_item_ids_cost = NULL, рассчитываем вручную
        COALESCE(
            ls.order_item_ids_cost,
            CASE
                WHEN oi.requested_unit = ls.base_unit THEN
                    ls.fprice * oi.requested_quantity
                ELSE
                    CEIL(oi.requested_quantity / ls.base_quantity) * ls.price
            END
        ) as item_cost,
        -- Рассчитываем потери: (fprice текущего ЛСД - минимальный fprice) * вес в базовых единицах
        -- Вес в базовых единицах = base_quantity (вес упаковки) * order_item_ids_quantity (кол-во упаковок)
        (ls.fprice - (
            SELECT MIN(ls2.fprice)
            FROM lsd_stocks ls2
            WHERE ls2.order_item_id = ls.order_item_id
              AND ls2.order_id = :order_id
              AND ls2.match_score > 0.75
        )) * (ls.base_quantity * ls.order_item_ids_quantity) as loss
    FROM lsd_stocks ls
    JOIN order_items oi ON oi.id = ls.order_item_id
    WHERE ls.order_id = :order_id
      AND ls.match_score > 0.75
      AND ls.order_item_ids_quantity > 0  -- ✅ Фильтруем товары, которые можно купить
      AND EXISTS (
          SELECT 1 FROM active_lsds al WHERE al.lsd_config_id = ls.lsd_config_id
      )
    ORDER BY ls.lsd_config_id, ls.order_item_id, ls.fprice ASC
),
not_found_items AS (
    -- Товары, которые RPA не нашел в данном LSD
    SELECT
        al.lsd_config_id,
        oi.id as order_item_id,
        oi.product_name,
        oi.requested_quantity,
        oi.requested_unit
    FROM active_lsds al
    CROSS JOIN order_items oi
    WHERE oi.order_id = :order_id
      -- Товара нет в lsd_stocks для этого LSD
      AND NOT EXISTS (
          SELECT 1
          FROM lsd_stocks ls
          WHERE ls.lsd_config_id = al.lsd_config_id
            AND ls.order_item_id = oi.id
            AND ls.order_id = :order_id
            AND ls.match_score > 0.75
      )
),
lsd_summary AS (
    -- Агрегируем данные по каждому LSD
    SELECT
        al.lsd_config_id,
        lc.display_name as lsd_display_name,
        al.delivery_cost_model,

        -- Найденные товары (лучшие предложения)
        COALESCE(
            (
                SELECT json_agg(
                    json_build_object(
                        'product_name', bli.product_name,
                        'base_quantity', bli.base_quantity,
                        'base_unit', bli.base_unit,
                        'price', bli.price,
                        'fprice', bli.fprice,
                        'fprice_min', bli.fprice_min,
                        'loss', bli.loss,
                        'order_item_ids_cost', bli.item_cost,
                        'order_item_ids_quantity', bli.order_item_ids_quantity,
                        'requested_quantity', bli.requested_quantity,
                        'requested_unit', bli.requested_unit
                    ) ORDER BY bli.product_name
                )
                FROM best_lsd_items bli
                WHERE bli.lsd_config_id = al.lsd_config_id
            ),
            '[]'::json
        ) as found_items,

        -- Не найденные товары
        COALESCE(
            (
                SELECT json_agg(
                    json_build_object(
                        'product_name', nfi.product_name,
                        'requested_quantity', nfi.requested_quantity,
                        'requested_unit', nfi.requested_unit
                    ) ORDER BY nfi.product_name
                )
                FROM not_found_items nfi
                WHERE nfi.lsd_config_id = al.lsd_config_id
            ),
            '[]'::json
        ) as not_found_items,

        -- Количество товаров
        (
            SELECT COUNT(*)
            FROM best_lsd_items bli
            WHERE bli.lsd_config_id = al.lsd_config_id
        ) as found_count,
        (
            SELECT COUNT(*)
            FROM not_found_items nfi
            WHERE nfi.lsd_config_id = al.lsd_config_id
        ) as not_found_count,

        -- Итоговая стоимость товаров
        COALESCE(
            (
                SELECT SUM(bli.item_cost)
                FROM best_lsd_items bli
                WHERE bli.lsd_config_id = al.lsd_config_id
            ),
            0
        ) as total_goods_cost,

        -- Итоговые потери
        COALESCE(
            (
                SELECT SUM(bli.loss)
                FROM best_lsd_items bli
                WHERE bli.lsd_config_id = al.lsd_config_id
            ),
            0
        ) as total_loss

    FROM active_lsds al
    JOIN lsd_configs lc ON lc.id = al.lsd_config_id
)
SELECT
    ls.lsd_config_id,
    ls.lsd_display_name,
    ls.delivery_cost_model,
    ls.found_items,
    ls.not_found_items,
    ls.found_count,
    ls.not_found_count,
    ls.total_goods_cost,
    ls.total_loss,

    -- Вычисляем топап (если total_goods_cost меньше минимальной суммы заказа)
    CASE
        WHEN ls.found_count = 0 THEN NULL
        ELSE (
            -- Находим минимальную сумму заказа (первый min с fee > 0)
            SELECT COALESCE(
                (
                    SELECT
                        CASE
                            WHEN (range_item->>'min')::numeric > ls.total_goods_cost
                            THEN (range_item->>'min')::numeric - ls.total_goods_cost
                            ELSE 0
                        END
                    FROM jsonb_array_elements(
                        CASE
                            WHEN jsonb_typeof(ls.delivery_cost_model::jsonb->'delivery_cost') = 'array'
                            THEN ls.delivery_cost_model::jsonb->'delivery_cost'
                            ELSE '[]'::jsonb
                        END
                    ) as range_item
                    WHERE (range_item->>'fee')::numeric > 0
                    ORDER BY (range_item->>'min')::numeric ASC
                    LIMIT 1
                ),
                0
            )
        )
    END as topup,

    -- Вычисляем стоимость доставки на основе (total_goods_cost + topup)
    -- ВАЖНО: доставка рассчитывается ПОСЛЕ применения топапа
    CASE
        WHEN ls.found_count = 0 THEN NULL
        ELSE (
            -- Сначала вычисляем сумму после топапа
            WITH topup_calc AS (
                SELECT
                    ls.total_goods_cost as goods_cost,
                    COALESCE(
                        (
                            SELECT
                                CASE
                                    WHEN (range_item->>'min')::numeric > ls.total_goods_cost
                                    THEN (range_item->>'min')::numeric - ls.total_goods_cost
                                    ELSE 0
                                END
                            FROM jsonb_array_elements(
                                CASE
                                    WHEN jsonb_typeof(ls.delivery_cost_model::jsonb->'delivery_cost') = 'array'
                                    THEN ls.delivery_cost_model::jsonb->'delivery_cost'
                                    ELSE '[]'::jsonb
                                END
                            ) as range_item
                            WHERE (range_item->>'fee')::numeric > 0
                            ORDER BY (range_item->>'min')::numeric ASC
                            LIMIT 1
                        ),
                        0
                    ) as topup_amount
            )
            -- Теперь ищем fee в диапазоне для суммы ПОСЛЕ топапа
            SELECT COALESCE(
                (
                    SELECT (range_item->>'fee')::numeric
                    FROM jsonb_array_elements(
                        CASE
                            WHEN jsonb_typeof(ls.delivery_cost_model::jsonb->'delivery_cost') = 'array'
                            THEN ls.delivery_cost_model::jsonb->'delivery_cost'
                            ELSE '[]'::jsonb
                        END
                    ) as range_item,
                    topup_calc
                    WHERE (range_item->>'min')::numeric <= (topup_calc.goods_cost + topup_calc.topup_amount)
                      AND (
                          range_item->>'max' IS NULL
                          OR (range_item->>'max')::numeric > (topup_calc.goods_cost + topup_calc.topup_amount)
                      )
                    ORDER BY (range_item->>'min')::numeric DESC
                    LIMIT 1
                ),
                0
            )
        )
    END as delivery_cost,

    -- Признак: можно ли собрать полный заказ из этого LSD
    CASE
        WHEN ls.found_count > 0 AND ls.not_found_count = 0 THEN true
        ELSE false
    END as can_fulfill_order

FROM lsd_summary ls
ORDER BY
    -- Сначала те, где можно собрать полный заказ
    CASE
        WHEN ls.found_count > 0 AND ls.not_found_count = 0 THEN 1
        ELSE 2
    END,
    -- Потом по количеству найденных товаров
    ls.found_count DESC,
    -- Потом по итоговой стоимости (товары + топап + доставка)
    (ls.total_goods_cost +
     COALESCE(
        (
            SELECT
                CASE
                    WHEN (range_item->>'min')::numeric > ls.total_goods_cost
                    THEN (range_item->>'min')::numeric - ls.total_goods_cost
                    ELSE 0
                END
            FROM jsonb_array_elements(
                CASE
                    WHEN jsonb_typeof(ls.delivery_cost_model::jsonb->'delivery_cost') = 'array'
                    THEN ls.delivery_cost_model::jsonb->'delivery_cost'
                    ELSE '[]'::jsonb
                END
            ) as range_item
            WHERE (range_item->>'fee')::numeric > 0
            ORDER BY (range_item->>'min')::numeric ASC
            LIMIT 1
        ),
        0
    )) ASC;
