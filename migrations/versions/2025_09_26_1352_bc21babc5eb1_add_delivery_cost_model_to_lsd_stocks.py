"""add_delivery_cost_model_to_lsd_stocks

Revision ID: bc21babc5eb1
Revises: 603157456ae6
Create Date: 2025-09-26 13:52:20.762177

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bc21babc5eb1'
down_revision = '603157456ae6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поле delivery_cost_model в таблицу lsd_stocks
    op.add_column('lsd_stocks', sa.Column('delivery_cost_model', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Удаляем поле delivery_cost_model из таблицы lsd_stocks
    op.drop_column('lsd_stocks', 'delivery_cost_model')
