-- Миграция: Удаление LINKING_FIRST_LSD из UserStatus enum
-- Дата: 2025-09-25

-- Сначала проверяем, есть ли пользователи с этим статусом
DO $$
DECLARE
    user_count INTEGER;
BEGIN
    -- Проверяем количество пользователей (если enum значение существует)
    SELECT COUNT(*) INTO user_count 
    FROM users 
    WHERE status::text = 'linking_first_lsd';
    
    IF user_count > 0 THEN
        -- Если есть пользователи, переводим их в ACTIVE
        UPDATE users 
        SET status = 'active'::userstatus 
        WHERE status::text = 'linking_first_lsd';
        
        RAISE NOTICE 'Updated % users from linking_first_lsd to active', user_count;
    END IF;
END $$;

-- Создаем новый enum без LINKING_FIRST_LSD
CREATE TYPE userstatus_new AS ENUM (
    'initial',
    'pre_registered', 
    'waiting_contact',
    'waiting_address',
    'waiting_delivery',
    'registered',
    'active',
    'blocked'
);

-- Обновляем колонку на использование нового типа
ALTER TABLE users 
    ALTER COLUMN status TYPE userstatus_new 
    USING status::text::userstatus_new;

-- Удаляем старый тип
DROP TYPE userstatus;

-- Переименовываем новый тип
ALTER TYPE userstatus_new RENAME TO userstatus;

-- Подтверждение
SELECT 'Migration completed successfully' as result;
