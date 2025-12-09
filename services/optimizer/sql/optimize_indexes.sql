-- ==============================================================================
-- ОПТИМИЗАЦИЯ ИНДЕКСОВ: Удаление избыточных индексов только на basket_id
-- ==============================================================================
-- После перехода на composite key (order_id, basket_id) индексы только на basket_id
-- становятся менее эффективными. Composite индексы уже существуют.

-- Проверяем текущие индексы на basket_combinations
SELECT 
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'basket_combinations'
ORDER BY indexname;

-- ТЕКУЩИЕ ИНДЕКСЫ:
-- 1. idx_basket_combinations_fprice_id - полезен
-- 2. idx_basket_combinations_lsd_stock - полезен
-- 3. ix_bc_basket - ИЗБЫТОЧЕН (только basket_id)
-- 4. ix_bc_basket_lsd - ЧАСТИЧНО ИЗБЫТОЧЕН (basket_id, lsd_config_id без order_id)
-- 5. ix_bc_order_basket - ХОРОШИЙ (order_id, basket_id)
-- 6. ix_bc_order_lsd_basket_partial - ОТЛИЧНЫЙ (order_id, lsd_config_id, basket_id)

BEGIN;

-- Удаляем индекс только на basket_id (избыточен, т.к. есть ix_bc_order_basket)
DROP INDEX IF EXISTS ix_bc_basket;

-- Удаляем индекс (basket_id, lsd_config_id) - избыточен, т.к. есть ix_bc_order_lsd_basket_partial
DROP INDEX IF EXISTS ix_bc_basket_lsd;

-- Создаем оптимизированный индекс для частого запроса top_baskets
-- (order_id, basket_id) с INCLUDE для ускорения выборки
CREATE INDEX IF NOT EXISTS ix_bc_order_basket_optimized 
ON basket_combinations (order_id, basket_id)
INCLUDE (lsd_name, product_name, price, fprice, order_item_ids_cost, order_item_ids_quantity);

COMMIT;

-- Показываем финальный список индексов
SELECT 
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size,
    indexdef
FROM pg_indexes
WHERE tablename = 'basket_combinations'
ORDER BY indexname;
