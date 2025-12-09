"""add optimizing and results_sent to orderstatus enum

Revision ID: add_optimization_enum_values
Revises: optimization_timestamps
Create Date: 2025-09-29

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_optimization_enum_values'
down_revision = 'optimization_timestamps'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем новые значения в enum orderstatus
    # PostgreSQL требует использовать ALTER TYPE ADD VALUE вне транзакции
    
    # OPTIMIZING - между ANALYZING и OPTIMIZED
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'OPTIMIZING' BEFORE 'OPTIMIZED'")
    
    # RESULTS_SENT - после OPTIMIZED
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'RESULTS_SENT' AFTER 'OPTIMIZED'")


def downgrade():
    # Удаление значений из enum в PostgreSQL очень сложно и требует:
    # 1. Убедиться что нет записей с этими значениями
    # 2. Создать новый enum без этих значений
    # 3. Изменить тип колонки на новый enum
    # 4. Удалить старый enum
    # Поэтому downgrade не реализован
    pass
