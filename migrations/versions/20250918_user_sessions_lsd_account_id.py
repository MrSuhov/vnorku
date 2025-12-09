"""Update user_sessions with lsd_account_id

Revision ID: 20250918_user_sessions_lsd_account_id
Revises: 
Create Date: 2025-09-18 09:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '20250918_user_sessions_lsd_account_id'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем новое поле lsd_account_id в таблицу user_sessions
    op.add_column('user_sessions', sa.Column('lsd_account_id', sa.Integer(), nullable=True))
    
    # Создаем внешний ключ на lsd_accounts.id
    op.create_foreign_key('fk_user_sessions_lsd_account_id', 'user_sessions', 'lsd_accounts', ['lsd_account_id'], ['id'])
    
    # Делаем session_type nullable (теперь не обязательное для куки)
    op.alter_column('user_sessions', 'session_type', nullable=True)


def downgrade() -> None:
    # Убираем внешний ключ
    op.drop_constraint('fk_user_sessions_lsd_account_id', 'user_sessions', type_='foreignkey')
    
    # Убираем колонку lsd_account_id
    op.drop_column('user_sessions', 'lsd_account_id')
    
    # Возвращаем session_type как NOT NULL
    op.alter_column('user_sessions', 'session_type', nullable=False)
