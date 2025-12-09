"""add alternatives support

Revision ID: 2025_09_27_alternatives
Revises: 
Create Date: 2025-09-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2025_09_27_alternatives'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поля для поддержки альтернативных товаров в order_items
    op.add_column('order_items', sa.Column('alternatives', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('order_items', sa.Column('is_alternative_group', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('order_items', sa.Column('selected_alternative', sa.String(length=500), nullable=True))
    
    # Добавляем поля для маркировки альтернатив в lsd_stocks
    op.add_column('lsd_stocks', sa.Column('is_alternative', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('lsd_stocks', sa.Column('alternative_for', sa.String(length=500), nullable=True))


def downgrade():
    # Удаляем добавленные поля
    op.drop_column('lsd_stocks', 'alternative_for')
    op.drop_column('lsd_stocks', 'is_alternative')
    op.drop_column('order_items', 'selected_alternative')
    op.drop_column('order_items', 'is_alternative_group')
    op.drop_column('order_items', 'alternatives')
