-- Миграция: добавление поля fprice_optimizer_id в basket_combinations и _basket_combinations
-- Это поле хранит ссылку на запись в fprice_optimizer для трейсабилити

-- 1. Добавляем поле в основную таблицу basket_combinations
ALTER TABLE basket_combinations 
ADD COLUMN IF NOT EXISTS fprice_optimizer_id INTEGER;

-- Создаём индекс для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_basket_combinations_fprice_id 
ON basket_combinations(fprice_optimizer_id);

COMMENT ON COLUMN basket_combinations.fprice_optimizer_id IS 
'Ссылка на запись в fprice_optimizer - источник данных для этой позиции в корзине';

-- 2. Добавляем поле во временную таблицу _basket_combinations (если существует)
DO $$ 
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '_basket_combinations') THEN
        ALTER TABLE _basket_combinations 
        ADD COLUMN IF NOT EXISTS fprice_optimizer_id INTEGER;
        
        CREATE INDEX IF NOT EXISTS idx__basket_combinations_fprice_id 
        ON _basket_combinations(fprice_optimizer_id);
        
        COMMENT ON COLUMN _basket_combinations.fprice_optimizer_id IS 
        'Ссылка на запись в fprice_optimizer - источник данных для этой позиции в корзине';
        
        RAISE NOTICE 'Поле fprice_optimizer_id добавлено в _basket_combinations';
    ELSE
        RAISE NOTICE 'Таблица _basket_combinations не существует, пропускаем';
    END IF;
END $$;

-- Проверка результата
SELECT 
    'basket_combinations' as table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'basket_combinations' 
  AND column_name = 'fprice_optimizer_id'

UNION ALL

SELECT 
    '_basket_combinations' as table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = '_basket_combinations' 
  AND column_name = 'fprice_optimizer_id';
