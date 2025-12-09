-- Добавление поля is_mono_basket в таблицу basket_analyses
-- Это поле помечает корзины, которые содержат товары только из одного LSD

ALTER TABLE basket_analyses 
ADD COLUMN IF NOT EXISTS is_mono_basket BOOLEAN DEFAULT FALSE;

-- Создаем индекс для быстрого поиска моно-корзин
CREATE INDEX IF NOT EXISTS idx_basket_analyses_is_mono 
ON basket_analyses(order_id, is_mono_basket) 
WHERE is_mono_basket = TRUE;

-- Комментарий к полю
COMMENT ON COLUMN basket_analyses.is_mono_basket IS 'Флаг моно-корзины (все товары из одного LSD)';
