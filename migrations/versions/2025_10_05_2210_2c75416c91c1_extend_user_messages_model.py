"""extend_user_messages_model

Revision ID: 2c75416c91c1
Revises: 9869f8e7643f
Create Date: 2025-10-05 22:10:41.091558

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2c75416c91c1'
down_revision = '9869f8e7643f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Добавляем новые колонки
    op.add_column('user_messages', sa.Column('user_id', sa.Integer(), nullable=True))
    op.add_column('user_messages', sa.Column('message_direction', sa.String(10), nullable=False, server_default='outgoing'))
    op.add_column('user_messages', sa.Column('chat_type', sa.String(20), nullable=False, server_default='group'))
    op.add_column('user_messages', sa.Column('message_category', sa.String(50), nullable=True))
    op.add_column('user_messages', sa.Column('telegram_message_id', sa.Integer(), nullable=True))
    op.add_column('user_messages', sa.Column('reply_to_telegram_message_id', sa.Integer(), nullable=True))
    op.add_column('user_messages', sa.Column('raw_update', sa.JSON(), nullable=True))
    op.add_column('user_messages', sa.Column('is_significant', sa.Boolean(), nullable=False, server_default='true'))
    
    # 2. Переименовываем старое поле reply_to_message_id во временное
    op.alter_column('user_messages', 'reply_to_message_id', 
                    new_column_name='old_reply_to_message_id',
                    existing_type=sa.Integer(),
                    existing_nullable=True)
    
    # 3. Копируем данные из старого поля в новое
    op.execute("""
        UPDATE user_messages 
        SET reply_to_telegram_message_id = old_reply_to_message_id
        WHERE old_reply_to_message_id IS NOT NULL
    """)
    
    # 4. Удаляем старое поле
    op.drop_column('user_messages', 'old_reply_to_message_id')
    
    # 5. Определяем chat_type на основе chat_id для существующих записей
    # Telegram group IDs начинаются с -100 для supergroups
    op.execute("""
        UPDATE user_messages 
        SET chat_type = CASE 
            WHEN CAST(chat_id AS BIGINT) < 0 THEN 
                CASE 
                    WHEN CAST(chat_id AS BIGINT) > -1000000000000 THEN 'group'
                    ELSE 'supergroup'
                END
            ELSE 'private'
        END
    """)
    
    # 6. Пытаемся определить user_id через order_id для существующих записей
    op.execute("""
        UPDATE user_messages um
        SET user_id = o.user_id
        FROM orders o
        WHERE um.order_id = o.id AND um.user_id IS NULL
    """)
    
    # 7. Устанавливаем категорию для существующих записей
    op.execute("""
        UPDATE user_messages 
        SET message_category = 'order_result'
        WHERE message_category IS NULL AND order_id IS NOT NULL
    """)
    
    # 8. Изменяем тип chat_id с String на BigInteger
    # Сначала создаём новую колонку
    op.add_column('user_messages', sa.Column('chat_id_new', sa.BigInteger(), nullable=True))
    
    # Копируем данные, преобразуя строку в число
    op.execute("""
        UPDATE user_messages 
        SET chat_id_new = CAST(chat_id AS BIGINT)
    """)
    
    # Удаляем старую колонку и индекс
    op.drop_index('ix_user_messages_chat_id', table_name='user_messages')
    op.drop_column('user_messages', 'chat_id')
    
    # Переименовываем новую колонку и делаем её NOT NULL
    op.alter_column('user_messages', 'chat_id_new', 
                    new_column_name='chat_id',
                    nullable=False)
    
    # 9. Добавляем Foreign Key для user_id
    op.create_foreign_key(
        'fk_user_messages_user_id', 
        'user_messages', 
        'users', 
        ['user_id'], 
        ['id'], 
        ondelete='CASCADE'
    )
    
    # 10. Создаём новые индексы
    op.create_index('ix_user_messages_user_id', 'user_messages', ['user_id'])
    op.create_index('ix_user_messages_message_direction', 'user_messages', ['message_direction'])
    op.create_index('ix_user_messages_message_category', 'user_messages', ['message_category'])
    op.create_index('ix_user_messages_telegram_message_id', 'user_messages', ['telegram_message_id'])
    op.create_index('ix_user_messages_chat_id', 'user_messages', ['chat_id'])
    
    # Составной индекс для сложных запросов
    op.create_index(
        'ix_user_messages_user_chat_direction', 
        'user_messages', 
        ['user_id', 'chat_id', 'message_direction']
    )
    
    # 11. Удаляем server_default после миграции данных
    op.alter_column('user_messages', 'message_direction', server_default=None)
    op.alter_column('user_messages', 'chat_type', server_default=None)
    op.alter_column('user_messages', 'is_significant', server_default=None)


def downgrade() -> None:
    # Удаляем новые индексы
    op.drop_index('ix_user_messages_user_chat_direction', table_name='user_messages')
    op.drop_index('ix_user_messages_telegram_message_id', table_name='user_messages')
    op.drop_index('ix_user_messages_message_category', table_name='user_messages')
    op.drop_index('ix_user_messages_message_direction', table_name='user_messages')
    op.drop_index('ix_user_messages_user_id', table_name='user_messages')
    op.drop_index('ix_user_messages_chat_id', table_name='user_messages')
    
    # Удаляем Foreign Key
    op.drop_constraint('fk_user_messages_user_id', 'user_messages', type_='foreignkey')
    
    # Возвращаем chat_id к String типу
    op.add_column('user_messages', sa.Column('chat_id_old', sa.String(), nullable=True))
    op.execute("UPDATE user_messages SET chat_id_old = CAST(chat_id AS VARCHAR)")
    op.drop_column('user_messages', 'chat_id')
    op.alter_column('user_messages', 'chat_id_old', new_column_name='chat_id', nullable=False)
    op.create_index('ix_user_messages_chat_id', 'user_messages', ['chat_id'])
    
    # Возвращаем старое поле reply_to_message_id
    op.add_column('user_messages', sa.Column('reply_to_message_id', sa.Integer(), nullable=True))
    op.execute("""
        UPDATE user_messages 
        SET reply_to_message_id = reply_to_telegram_message_id
    """)
    
    # Удаляем новые колонки
    op.drop_column('user_messages', 'is_significant')
    op.drop_column('user_messages', 'raw_update')
    op.drop_column('user_messages', 'reply_to_telegram_message_id')
    op.drop_column('user_messages', 'telegram_message_id')
    op.drop_column('user_messages', 'message_category')
    op.drop_column('user_messages', 'chat_type')
    op.drop_column('user_messages', 'message_direction')
    op.drop_column('user_messages', 'user_id')
