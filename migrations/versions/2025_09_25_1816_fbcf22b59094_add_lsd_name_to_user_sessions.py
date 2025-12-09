"""add_lsd_name_to_user_sessions

Revision ID: fbcf22b59094
Revises: add_fprice_calculation
Create Date: 2025-09-25 18:16:38.934610

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fbcf22b59094'
down_revision = 'add_fprice_calculation'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поле lsd_name в user_sessions
    op.add_column('user_sessions', sa.Column('lsd_name', sa.String(length=100), nullable=True))
    op.create_index('ix_user_sessions_lsd_name', 'user_sessions', ['lsd_name'], unique=False)


def downgrade() -> None:
    # Удаляем индекс и поле lsd_name
    op.drop_index('ix_user_sessions_lsd_name', table_name='user_sessions')
    op.drop_column('user_sessions', 'lsd_name')
