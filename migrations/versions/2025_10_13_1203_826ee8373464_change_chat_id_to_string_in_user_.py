"""change_chat_id_to_string_in_user_messages

Revision ID: 826ee8373464
Revises: 699baa829acc
Create Date: 2025-10-13 12:03:34.465042

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '826ee8373464'
down_revision = '699baa829acc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Изменяем тип chat_id с bigint на varchar(50)
    # Используем USING для явного приведения типа
    op.execute("""
        ALTER TABLE user_messages
        ALTER COLUMN chat_id TYPE VARCHAR(50)
        USING chat_id::VARCHAR(50)
    """)


def downgrade() -> None:
    # Обратное преобразование: varchar(50) → bigint
    # ВАЖНО: это может привести к ошибкам если в chat_id хранятся не числовые значения
    op.execute("""
        ALTER TABLE user_messages
        ALTER COLUMN chat_id TYPE BIGINT
        USING chat_id::BIGINT
    """)
