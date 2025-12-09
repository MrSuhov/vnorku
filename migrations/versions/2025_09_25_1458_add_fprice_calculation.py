"""add fprice_calculation column

Revision ID: add_fprice_calculation
Revises: 
Create Date: 2025-09-25 14:58

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_fprice_calculation'
down_revision = '10b5cc8ecb13'  # Предыдущая ревизия
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем колонку fprice_calculation в таблицу lsd_stocks
    op.add_column('lsd_stocks', 
        sa.Column('fprice_calculation', sa.Text(), nullable=True, comment='Текстовое описание формулы расчета fprice')
    )


def downgrade():
    # Удаляем колонку при откате
    op.drop_column('lsd_stocks', 'fprice_calculation')
