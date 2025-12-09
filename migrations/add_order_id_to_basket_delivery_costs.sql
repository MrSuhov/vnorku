-- Добавляем order_id в basket_delivery_costs
-- Миграция: add_order_id_to_basket_delivery_costs.sql

BEGIN;

-- 1. Удаляем все существующие данные (они не связаны с актуальными заказами)
TRUNCATE TABLE basket_delivery_costs CASCADE;

-- 2. Добавляем колонку order_id
ALTER TABLE basket_delivery_costs 
ADD COLUMN order_id INTEGER NOT NULL;

-- 3. Удаляем старые constraints
DROP INDEX IF EXISTS ux_bdc_basket_lsd;
ALTER TABLE basket_delivery_costs 
DROP CONSTRAINT IF EXISTS basket_delivery_costs_basket_id_lsd_config_id_key;

-- 4. Создаём новый unique constraint на (order_id, basket_id, lsd_config_id)
ALTER TABLE basket_delivery_costs 
ADD CONSTRAINT basket_delivery_costs_order_basket_lsd_key 
UNIQUE (order_id, basket_id, lsd_config_id);

-- 5. Создаём индекс на order_id для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_basket_delivery_costs_order_id 
ON basket_delivery_costs(order_id);

-- 6. Добавляем foreign key на orders
ALTER TABLE basket_delivery_costs
ADD CONSTRAINT fk_basket_delivery_costs_order
FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE;

COMMIT;
