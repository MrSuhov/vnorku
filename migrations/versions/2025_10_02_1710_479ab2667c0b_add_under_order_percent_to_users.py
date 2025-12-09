"""add_under_order_percent_to_users

Revision ID: 479ab2667c0b
Revises: 6a28cce43686
Create Date: 2025-10-02 17:10:23.654931

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '479ab2667c0b'
down_revision = '6a28cce43686'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поле under_order_percent в таблицу users
    op.add_column('users', sa.Column('under_order_percent', sa.Integer(), nullable=False, server_default='10'))
    
    # Обновляем существующих пользователей значением 10
    op.execute("UPDATE users SET under_order_percent = 10 WHERE under_order_percent IS NULL")


def downgrade() -> None:
    # Удаляем поле при откате миграции
    op.drop_column('users', 'under_order_percent')
