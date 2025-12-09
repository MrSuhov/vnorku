"""add_delivery_cost_model_to_lsd_configs

Revision ID: d1810b6eed17
Revises: bc21babc5eb1
Create Date: 2025-09-26 14:00:48.734672

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1810b6eed17'
down_revision = 'bc21babc5eb1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поле delivery_cost_model в таблицу lsd_configs
    op.add_column('lsd_configs', sa.Column('delivery_cost_model', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Удаляем поле delivery_cost_model из таблицы lsd_configs
    op.drop_column('lsd_configs', 'delivery_cost_model')
