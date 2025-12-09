"""remove_over_order_percent_from_lsd_stocks

Revision ID: 845a67137d03
Revises: 22abe6600c94
Create Date: 2025-09-27 14:08:XX

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '845a67137d03'
down_revision = '22abe6600c94'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Удаляем поле over_order_percent из таблицы lsd_stocks
    op.drop_column('lsd_stocks', 'over_order_percent')


def downgrade() -> None:
    # Восстанавливаем поле при откате
    op.add_column('lsd_stocks', sa.Column('over_order_percent', sa.Integer(), nullable=True))
