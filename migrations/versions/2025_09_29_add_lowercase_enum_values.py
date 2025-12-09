"""add lowercase enum values to orderstatus

Revision ID: add_lowercase_enum_values
Revises: add_optimization_enum_values
Create Date: 2025-09-29

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_lowercase_enum_values'
down_revision = 'add_optimization_enum_values'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем все значения в нижнем регистре
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'new'")
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'analyzing'")
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'analysis_complete'")
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'optimizing'")
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'optimized'")
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'results_sent'")
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'confirmed'")
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'creating_orders'")
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'completed'")
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'failed'")
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'cancelled'")
    
    # Обновляем существующие данные на нижний регистр
    op.execute("""
        UPDATE orders SET status = 'new' WHERE status = 'NEW';
        UPDATE orders SET status = 'analyzing' WHERE status = 'ANALYZING';
        UPDATE orders SET status = 'analysis_complete' WHERE status = 'ANALYSIS_COMPLETE';
        UPDATE orders SET status = 'optimizing' WHERE status = 'OPTIMIZING';
        UPDATE orders SET status = 'optimized' WHERE status = 'OPTIMIZED';
        UPDATE orders SET status = 'results_sent' WHERE status = 'RESULTS_SENT';
        UPDATE orders SET status = 'confirmed' WHERE status = 'CONFIRMED';
        UPDATE orders SET status = 'creating_orders' WHERE status = 'CREATING_ORDERS';
        UPDATE orders SET status = 'completed' WHERE status = 'COMPLETED';
        UPDATE orders SET status = 'failed' WHERE status = 'FAILED';
        UPDATE orders SET status = 'cancelled' WHERE status = 'CANCELLED';
    """)


def downgrade():
    # Обратное преобразование в верхний регистр
    op.execute("""
        UPDATE orders SET status = 'NEW' WHERE status = 'new';
        UPDATE orders SET status = 'ANALYZING' WHERE status = 'analyzing';
        UPDATE orders SET status = 'ANALYSIS_COMPLETE' WHERE status = 'analysis_complete';
        UPDATE orders SET status = 'OPTIMIZING' WHERE status = 'optimizing';
        UPDATE orders SET status = 'OPTIMIZED' WHERE status = 'optimized';
        UPDATE orders SET status = 'RESULTS_SENT' WHERE status = 'results_sent';
        UPDATE orders SET status = 'CONFIRMED' WHERE status = 'confirmed';
        UPDATE orders SET status = 'CREATING_ORDERS' WHERE status = 'creating_orders';
        UPDATE orders SET status = 'COMPLETED' WHERE status = 'completed';
        UPDATE orders SET status = 'FAILED' WHERE status = 'failed';
        UPDATE orders SET status = 'CANCELLED' WHERE status = 'cancelled';
    """)
