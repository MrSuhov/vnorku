-- Миграция: Очистка UserStatus enum - удаление LINKING_FIRST_LSD и дубликатов
-- Дата: 2025-09-25

-- Шаг 1: Проверяем текущее состояние
SELECT 'Before migration:' as stage, status, COUNT(*) as count FROM users GROUP BY status;

-- Шаг 2: Приводим все значения к нижнему регистру
UPDATE users SET status = 'active'::userstatus WHERE status::text = 'ACTIVE';
UPDATE users SET status = 'initial'::userstatus WHERE status::text = 'INITIAL';
UPDATE users SET status = 'waiting_address'::userstatus WHERE status::text = 'WAITING_ADDRESS';

-- Шаг 3: Создаем чистый enum
DO $$
BEGIN
    -- Удаляем временный тип если существует
    DROP TYPE IF EXISTS userstatus_clean CASCADE;
    
    -- Создаем чистый enum только с нижним регистром
    CREATE TYPE userstatus_clean AS ENUM (
        'initial',
        'pre_registered', 
        'waiting_contact',
        'waiting_address',
        'waiting_delivery',
        'registered',
        'active',
        'blocked'
    );
    
    -- Обновляем колонку
    ALTER TABLE users 
        ALTER COLUMN status TYPE userstatus_clean 
        USING status::text::userstatus_clean;
    
    -- Удаляем старый тип
    DROP TYPE IF EXISTS userstatus CASCADE;
    
    -- Переименовываем
    ALTER TYPE userstatus_clean RENAME TO userstatus;
    
    RAISE NOTICE '✅ Migration completed successfully - LINKING_FIRST_LSD removed, enum cleaned';
END $$;

-- Шаг 4: Проверяем результат
SELECT 'After migration:' as stage, status, COUNT(*) as count FROM users GROUP BY status;

-- Шаг 5: Показываем финальный enum
\dT+ userstatus
