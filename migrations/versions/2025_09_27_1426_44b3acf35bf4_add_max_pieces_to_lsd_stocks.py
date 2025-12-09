"""add_max_pieces_to_lsd_stocks

Revision ID: 44b3acf35bf4
Revises: 2f648f05f770
Create Date: 2025-09-27 14:26:XX

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '44b3acf35bf4'
down_revision = '2f648f05f770'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поле max_pieces в таблицу lsd_stocks
    op.add_column('lsd_stocks', sa.Column('max_pieces', sa.Integer(), nullable=True))


def downgrade() -> None:
    # Удаляем поле при откате миграции
    op.drop_column('lsd_stocks', 'max_pieces')
