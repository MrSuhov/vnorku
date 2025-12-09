-- Миграция: Добавление полей для поддержки документов в user_messages
-- Дата: 2025-10-06

BEGIN;

-- Обновляем message_text чтобы было nullable
ALTER TABLE user_messages 
ALTER COLUMN message_text DROP NOT NULL;

-- Добавляем новые поля для документов
ALTER TABLE user_messages 
ADD COLUMN IF NOT EXISTS is_document BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS filename VARCHAR(255),
ADD COLUMN IF NOT EXISTS file_size INTEGER;

-- Комментарии
COMMENT ON COLUMN user_messages.is_document IS 'True если сообщение содержит документ';
COMMENT ON COLUMN user_messages.filename IS 'Имя файла документа';
COMMENT ON COLUMN user_messages.file_size IS 'Размер файла в байтах';

COMMIT;
