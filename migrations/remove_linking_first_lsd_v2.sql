-- Миграция: Удаление LINKING_FIRST_LSD из UserStatus enum
-- Дата: 2025-09-25

-- Шаг 1: Проверяем текущие значения
SELECT status, COUNT(*) as count FROM users GROUP BY status;

-- Шаг 2: Создаем новый enum без LINKING_FIRST_LSD
DO $$
BEGIN
    -- Удаляем временный тип если он существует
    DROP TYPE IF EXISTS userstatus_new CASCADE;
    
    -- Создаем новый enum
    CREATE TYPE userstatus_new AS ENUM (
        'initial',
        'pre_registered', 
        'waiting_contact',
        'waiting_address',
        'waiting_delivery',
        'registered',
        'active',
        'blocked',
        'INITIAL',
        'ACTIVE',
        'WAITING_ADDRESS'
    );
    
    -- Обновляем колонку
    ALTER TABLE users 
        ALTER COLUMN status TYPE userstatus_new 
        USING status::text::userstatus_new;
    
    -- Удаляем старый тип с CASCADE
    DROP TYPE IF EXISTS userstatus CASCADE;
    
    -- Переименовываем новый тип
    ALTER TYPE userstatus_new RENAME TO userstatus;
    
    RAISE NOTICE 'Migration completed successfully';
END $$;

-- Шаг 3: Проверяем результат
SELECT status, COUNT(*) as count FROM users GROUP BY status;
