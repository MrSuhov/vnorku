"""Change user_sessions.updated_at from time to timestamp with timezone

Revision ID: 20250919_114153_updated_at_type
Revises: 9ea450069b2e
Create Date: 2025-09-19 11:41:53.563058

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250919_114153_updated_at_type'
down_revision = '9ea450069b2e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Изменяем тип поля updated_at с time на timestamp with timezone"""
    
    op.execute("""
        DO $$
        BEGIN
            -- Проверяем тип текущего поля updated_at
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'user_sessions' 
                AND column_name = 'updated_at' 
                AND data_type IN ('time without time zone', 'time with time zone')
            ) THEN
                -- Если поле имеет тип time (с зоной или без), заменяем его на timestamp
                RAISE NOTICE 'Found updated_at field with time type, converting to timestamp with timezone...';
                
                -- Удаляем старое поле
                ALTER TABLE user_sessions DROP COLUMN updated_at;
                
                -- Добавляем новое поле с правильным типом
                ALTER TABLE user_sessions ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE 
                    DEFAULT NOW() NOT NULL;
                
                RAISE NOTICE 'Successfully changed updated_at from time to timestamp with timezone';
                
            ELSIF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'user_sessions' 
                AND column_name = 'updated_at' 
                AND data_type = 'timestamp with time zone'
            ) THEN
                RAISE NOTICE 'Field updated_at already has correct type (timestamp with time zone)';
                
            ELSE
                -- Поле updated_at не существует, создаем его
                RAISE NOTICE 'Creating updated_at field with timestamp with timezone type...';
                
                ALTER TABLE user_sessions ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE 
                    DEFAULT NOW() NOT NULL;
                    
                RAISE NOTICE 'Created updated_at field with timestamp with timezone type';
            END IF;
            
            -- Создаем или обновляем триггер для автоматического обновления
            CREATE OR REPLACE FUNCTION update_user_sessions_updated_at()
            RETURNS TRIGGER AS $trigger$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $trigger$ LANGUAGE plpgsql;
            
            -- Создаем триггер (удаляем старый если есть)
            DROP TRIGGER IF EXISTS user_sessions_updated_at_trigger ON user_sessions;
            CREATE TRIGGER user_sessions_updated_at_trigger
                BEFORE UPDATE ON user_sessions
                FOR EACH ROW
                EXECUTE FUNCTION update_user_sessions_updated_at();
                
            RAISE NOTICE 'Created trigger for automatic updated_at updates';
        END
        $$;
    """)


def downgrade() -> None:
    """Откатываем изменения"""
    
    op.execute("""
        DO $$
        BEGIN
            -- Удаляем триггер и функцию
            DROP TRIGGER IF EXISTS user_sessions_updated_at_trigger ON user_sessions;
            DROP FUNCTION IF EXISTS update_user_sessions_updated_at();
            
            RAISE NOTICE 'Downgrade: removed trigger and function for updated_at';
        END
        $$;
    """)
