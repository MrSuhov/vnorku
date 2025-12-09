"""add_over_order_percent_to_users

Revision ID: 7d28f7404733
Revises: d47bbb054e63
Create Date: 2025-09-27 13:35:58.076374

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7d28f7404733'
down_revision = 'd47bbb054e63'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поле over_order_percent в таблицу users
    op.add_column('users', sa.Column('over_order_percent', sa.Integer(), nullable=False, server_default='50'))
    
    # Обновляем существующих пользователей значением 50
    op.execute("UPDATE users SET over_order_percent = 50 WHERE over_order_percent IS NULL")


def downgrade() -> None:
    # Удаляем поле при откате миграции
    op.drop_column('users', 'over_order_percent')
