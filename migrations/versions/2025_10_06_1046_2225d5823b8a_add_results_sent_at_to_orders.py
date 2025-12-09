"""add_results_sent_at_to_orders

Revision ID: 2225d5823b8a
Revises: 2c75416c91c1
Create Date: 2025-10-06 10:46:25.391970

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2225d5823b8a'
down_revision = '2c75416c91c1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем колонку results_sent_at в таблицу orders
    op.add_column(
        'orders',
        sa.Column('results_sent_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    # Удаляем колонку results_sent_at из таблицы orders
    op.drop_column('orders', 'results_sent_at')
