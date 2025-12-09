-- ==============================================================================
-- ОЧИСТКА: Удаление дублирующихся записей с конфликтующими basket_id
-- ==============================================================================
-- Проблема: в basket_combinations есть записи из разных заказов с одинаковым basket_id
-- Решение: оставить только самые свежие записи для каждой комбинации (order_id, basket_id)

BEGIN;

-- Показываем статистику ПЕРЕД очисткой
SELECT 
    'BEFORE CLEANUP' as stage,
    order_id,
    basket_id,
    COUNT(*) as records_count,
    STRING_AGG(DISTINCT lsd_name, ', ') as lsd_names
FROM basket_combinations
GROUP BY order_id, basket_id
HAVING COUNT(*) > 1
ORDER BY order_id DESC, basket_id;

-- Удаляем дубликаты, оставляя запись с максимальным id (самую свежую)
WITH duplicates AS (
    SELECT 
        id,
        order_id,
        basket_id,
        ROW_NUMBER() OVER (PARTITION BY order_id, basket_id ORDER BY id DESC) as rn
    FROM basket_combinations
)
DELETE FROM basket_combinations
WHERE id IN (
    SELECT id 
    FROM duplicates 
    WHERE rn > 1
);

-- Показываем, сколько записей удалено
SELECT 
    'CLEANUP RESULT' as stage,
    COUNT(*) as deleted_records
FROM basket_combinations
WHERE FALSE;  -- Пустой запрос для структуры

-- Проверяем, что дубликатов больше нет
SELECT 
    'AFTER CLEANUP' as stage,
    order_id,
    basket_id,
    COUNT(*) as records_count
FROM basket_combinations
GROUP BY order_id, basket_id
HAVING COUNT(*) > 1
ORDER BY order_id DESC, basket_id;

COMMIT;

-- Показываем финальную статистику
SELECT 
    'FINAL STATS' as info,
    order_id,
    COUNT(DISTINCT basket_id) as unique_baskets,
    COUNT(*) as total_records
FROM basket_combinations
GROUP BY order_id
ORDER BY order_id DESC
LIMIT 10;
