-- Миграция: добавление поддержки файловой системы для cookies
-- Дата: 2025-10-01
-- Описание: Добавляем комментарий к колонке data и индекс для быстрого поиска по cookie_file

-- Обновляем комментарий к колонке data для документирования новой структуры
COMMENT ON COLUMN user_sessions.data IS 'JSONB with cookie file metadata: {"cookie_file": "path/to/file.json", "cookie_count": 14, "last_updated": "ISO8601"}';

-- Создаём индекс для быстрого поиска сессий с cookie файлами
CREATE INDEX IF NOT EXISTS idx_user_sessions_cookie_file 
ON user_sessions ((data->>'cookie_file')) 
WHERE data->>'cookie_file' IS NOT NULL;

-- Комментарий к индексу
COMMENT ON INDEX idx_user_sessions_cookie_file IS 'Fast lookup for sessions with file-based cookies';
