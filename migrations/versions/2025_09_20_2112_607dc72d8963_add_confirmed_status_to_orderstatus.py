"""add_confirmed_status_to_orderstatus

Revision ID: 607dc72d8963
Revises: 20250919_114153_updated_at_type
Create Date: 2025-09-20 21:12:12.483883

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '607dc72d8963'
down_revision = '20250919_114153_updated_at_type'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Добавляем новый статус CONFIRMED в enum orderstatus"""
    
    op.execute("""
        DO $$
        BEGIN
            -- Проверяем, существует ли уже значение CONFIRMED
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum 
                WHERE enumlabel = 'CONFIRMED' 
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'orderstatus')
            ) THEN
                -- Добавляем новое значение CONFIRMED после ANALYSIS_COMPLETE
                ALTER TYPE orderstatus ADD VALUE 'CONFIRMED' AFTER 'ANALYSIS_COMPLETE';
                RAISE NOTICE 'Added CONFIRMED status to orderstatus enum';
            ELSE
                RAISE NOTICE 'CONFIRMED status already exists in orderstatus enum';
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    """Откат миграции - удаление CONFIRMED статуса"""
    
    # Примечание: PostgreSQL не поддерживает удаление значений из enum
    # Поэтому в downgrade мы просто логируем, что статус был добавлен
    op.execute("""
        DO $$
        BEGIN
            RAISE NOTICE 'Cannot remove CONFIRMED from enum orderstatus - PostgreSQL limitation';
            RAISE NOTICE 'Manual intervention required if rollback is necessary';
        END
        $$;
    """)
