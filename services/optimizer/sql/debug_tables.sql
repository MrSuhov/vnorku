-- ==============================================================================
-- Временные таблицы для debug-режима оптимизатора
-- ==============================================================================

-- Таблица 1: Все комбинации товаров во всех корзинах
CREATE TABLE IF NOT EXISTS _basket_combinations (
    basket_id INTEGER NOT NULL,
    id INTEGER NOT NULL,  -- ID из fprice_optimizer
    order_id INTEGER NOT NULL,
    order_item_id INTEGER NOT NULL,
    product_name VARCHAR(500),
    lsd_name VARCHAR(100),
    base_unit VARCHAR(10),
    base_quantity NUMERIC(10, 3),
    price NUMERIC(10, 2),
    fprice NUMERIC(10, 2),
    fprice_min NUMERIC(10, 2),
    fprice_diff NUMERIC(10, 2),
    loss NUMERIC(10, 2),
    order_item_ids_quantity INTEGER,  -- количество штук
    min_order_amount NUMERIC(10, 2),
    lsd_config_id INTEGER,
    delivery_cost_model TEXT,  -- JSON как текст
    order_item_ids_cost NUMERIC(10, 2),
    fprice_optimizer_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx__basket_combinations_basket_id ON _basket_combinations(basket_id);
CREATE INDEX IF NOT EXISTS idx__basket_combinations_order_id ON _basket_combinations(order_id);
CREATE INDEX IF NOT EXISTS idx__basket_combinations_lsd ON _basket_combinations(lsd_config_id);

COMMENT ON TABLE _basket_combinations IS 
'Временная таблица для debug-режима: все комбинации товаров во всех корзинах';

-- Таблица 2: Стоимость доставки для каждого ЛСД в каждой корзине
CREATE TABLE IF NOT EXISTS _basket_delivery_costs (
    basket_id INTEGER NOT NULL,
    lsd_config_id INTEGER NOT NULL,
    delivery_cost NUMERIC(10, 2) NOT NULL,
    topup NUMERIC(10, 2) NOT NULL,
    lsd_total_basket_cost NUMERIC(10, 2) NOT NULL,
    min_order_amount NUMERIC(10, 2)
);

CREATE INDEX IF NOT EXISTS idx__basket_delivery_costs_basket_id ON _basket_delivery_costs(basket_id);
CREATE INDEX IF NOT EXISTS idx__basket_delivery_costs_lsd ON _basket_delivery_costs(lsd_config_id);

COMMENT ON TABLE _basket_delivery_costs IS 
'Временная таблица для debug-режима: стоимость доставки по ЛСД для каждой корзины';

-- Таблица 3: Полный анализ всех корзин с рейтингом
CREATE TABLE IF NOT EXISTS _basket_analyses (
    order_id INTEGER NOT NULL,
    basket_id INTEGER NOT NULL,
    total_loss NUMERIC(10, 2),
    total_goods_cost NUMERIC(10, 2),
    delivery_cost TEXT,  -- JSON как текст
    delivery_topup TEXT,  -- JSON как текст
    total_delivery_cost NUMERIC(10, 2),
    total_cost NUMERIC(10, 2),
    total_loss_and_delivery NUMERIC(10, 2),
    basket_rank INTEGER
);

CREATE INDEX IF NOT EXISTS idx__basket_analyses_order_id ON _basket_analyses(order_id);
CREATE INDEX IF NOT EXISTS idx__basket_analyses_basket_id ON _basket_analyses(basket_id);
CREATE INDEX IF NOT EXISTS idx__basket_analyses_rank ON _basket_analyses(basket_rank);

COMMENT ON TABLE _basket_analyses IS 
'Временная таблица для debug-режима: полный анализ всех корзин с рейтингом';

-- ==============================================================================
-- Функция для очистки временных таблиц
-- ==============================================================================
CREATE OR REPLACE FUNCTION clear_debug_tables()
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    TRUNCATE TABLE _basket_combinations;
    TRUNCATE TABLE _basket_delivery_costs;
    TRUNCATE TABLE _basket_analyses;
    
    RAISE NOTICE 'Временные таблицы очищены: _basket_combinations, _basket_delivery_costs, _basket_analyses';
END;
$$;

COMMENT ON FUNCTION clear_debug_tables() IS 
'Очищает все временные таблицы для debug-режима';
