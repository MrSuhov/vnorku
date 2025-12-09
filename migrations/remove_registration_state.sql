-- Миграция: Удаление поля registration_state из таблицы users
-- Дата: 2025-09-25
-- Цель: Убрать дублирование с UserStatus

-- ============================================
-- Шаг 1: BACKUP - показать текущее состояние
-- ============================================
\echo '📊 Current state BEFORE migration:'
SELECT 
    status, 
    registration_state, 
    COUNT(*) as count 
FROM users 
GROUP BY status, registration_state 
ORDER BY status, registration_state;

-- ============================================
-- Шаг 2: Миграция данных
-- ============================================
\echo ''
\echo '🔄 Migrating registration_state → status...'

-- Обновляем status на основе registration_state где это нужно
UPDATE users 
SET status = CASE 
    WHEN registration_state::text = 'waiting_contact' THEN 'waiting_contact'::userstatus
    WHEN registration_state::text = 'waiting_address' THEN 'waiting_address'::userstatus
    WHEN registration_state::text = 'waiting_delivery_details' THEN 'waiting_delivery'::userstatus
    WHEN registration_state::text = 'waiting_lsd_auth' THEN 'active'::userstatus
    WHEN registration_state::text = 'completed' THEN 'active'::userstatus
    ELSE status  -- Оставляем текущий status если registration_state = NULL
END
WHERE registration_state IS NOT NULL;

\echo '✅ Data migration completed'

-- ============================================
-- Шаг 3: Показать результат миграции
-- ============================================
\echo ''
\echo '📊 State AFTER migration (before column drop):'
SELECT 
    status, 
    registration_state, 
    COUNT(*) as count 
FROM users 
GROUP BY status, registration_state 
ORDER BY status, registration_state;

-- ============================================
-- Шаг 4: Удаление колонки
-- ============================================
\echo ''
\echo '🗑️  Dropping registration_state column...'

ALTER TABLE users DROP COLUMN IF EXISTS registration_state;

\echo '✅ Column dropped'

-- ============================================
-- Шаг 5: Удаление enum типа
-- ============================================
\echo ''
\echo '🗑️  Dropping RegistrationState enum...'

DROP TYPE IF EXISTS registrationstate CASCADE;

\echo '✅ Enum dropped'

-- ============================================
-- Шаг 6: Финальная проверка
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
\echo '🎉 Migration completed successfully!'
\echo 'ℹ️  Next steps:'
\echo '   1. Update code to remove RegistrationState'
\echo '   2. Restart all services'
\echo '   3. Test registration flow'
