-- ==============================================================================
-- ПОЛНАЯ УСТАНОВКА СИСТЕМЫ ОПТИМИЗАЦИИ КОРЗИН
-- ==============================================================================
-- Использование: psql <db_url> -f install.sql

\echo '=========================================='
\echo 'УСТАНОВКА СИСТЕМЫ ОПТИМИЗАЦИИ КОРЗИН'
\echo '=========================================='
\echo ''

-- 1. Создание таблиц
\echo '[1/4] Создание таблиц...'
\i optimizer_tables.sql
\echo ''

-- 2. Функция расчета доставки
\echo '[2/4] Установка функции расчета доставки...'
\i delivery_calculator.sql
\echo ''

-- 3. Процедуры генерации комбинаций и корзин
\echo '[3/4] Установка процедур генерации...'
\i optimizer_procedures.sql
\echo ''

-- 4. Процедура оптимизации с доставкой
\echo '[4/4] Установка процедуры оптимизации...'
\i calculate_optimized_baskets.sql
\echo ''

\echo '=========================================='
\echo '✓ УСТАНОВКА ЗАВЕРШЕНА'
\echo '=========================================='
\echo ''
\echo 'Доступные команды:'
\echo '  CALL generate_order_combinations(<order_id>);'
\echo '  CALL generate_valid_baskets(<order_id>);'
\echo '  CALL calculate_optimized_baskets(<order_id>, <top_n>);'
\echo ''
\echo 'CLI скрипты:'
\echo '  ./optimize_order_fast.sh <order_id> [top_n]'
\echo '  ./show_results.sh <order_id>'
\echo ''
