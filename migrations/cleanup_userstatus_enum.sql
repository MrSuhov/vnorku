-- Миграция: Очистка UserStatus enum от неиспользуемых статусов
-- Дата: 2025-09-25
-- Цель: Оставить только 5 используемых статусов

-- ============================================
-- Шаг 1: BACKUP - показать текущее состояние
-- ============================================
\echo '📊 Current state BEFORE migration:'
SELECT 
    status, 
    COUNT(*) as count 
FROM users 
GROUP BY status 
ORDER BY status;

\echo ''
\echo '📋 Current enum values:'
\dT+ userstatus

-- ============================================
-- Шаг 2: Обновление существующих записей (если есть)
-- ============================================
\echo ''
\echo '🔄 Migrating old statuses to new ones...'

-- Конвертируем устаревшие статусы
UPDATE users 
SET status = CASE 
    WHEN status::text = 'initial' THEN 'waiting_contact'::userstatus
    WHEN status::text = 'pre_registered' THEN 'waiting_contact'::userstatus
    WHEN status::text = 'waiting_delivery' THEN 'active'::userstatus
    ELSE status
END
WHERE status::text IN ('initial', 'pre_registered', 'waiting_delivery');

\echo '✅ Old statuses migrated'

-- ============================================
-- Шаг 3: Показать состояние после миграции
-- ============================================
\echo ''
\echo '📊 State AFTER data migration:'
SELECT 
    status, 
    COUNT(*) as count 
FROM users 
GROUP BY status 
ORDER BY status;

-- ============================================
-- Шаг 4: Пересоздание enum
-- ============================================
\echo ''
\echo '🗑️  Recreating enum with only used statuses...'

-- Создать новый чистый enum (только 5 статусов)
CREATE TYPE userstatus_clean AS ENUM (
    'waiting_contact',
    'waiting_address',
    'active',
    'registered',
    'blocked'
);

-- Обновить колонку
ALTER TABLE users 
    ALTER COLUMN status TYPE userstatus_clean 
    USING status::text::userstatus_clean;

-- Удалить старый тип
DROP TYPE userstatus CASCADE;

-- Переименовать
ALTER TYPE userstatus_clean RENAME TO userstatus;

\echo '✅ Enum recreated with 5 statuses'

-- ============================================
-- Шаг 5: Финальная проверка
-- ============================================
\echo ''
\echo '📊 FINAL state:'
SELECT 
    status, 
    COUNT(*) as count 
FROM users 
GROUP BY status 
ORDER BY status;

\echo ''
\echo '📋 FINAL enum values:'
\dT+ userstatus

\echo ''
\echo '🎉 Migration completed successfully!'
\echo ''
\echo '✅ Removed statuses: initial, pre_registered, waiting_delivery'
\echo '✅ Kept statuses: waiting_contact, waiting_address, active, registered, blocked'
\echo ''
\echo 'ℹ️  Next steps:'
\echo '   1. Code already updated'
\echo '   2. Restart all services'
\echo '   3. Test registration flow'
