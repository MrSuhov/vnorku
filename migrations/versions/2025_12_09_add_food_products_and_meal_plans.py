"""add_food_products_and_meal_plans

Revision ID: a1b2c3d4e5f6
Revises: 826ee8373464
Create Date: 2025-12-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '826ee8373464'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создаём таблицу категорий продуктов
    op.create_table(
        'food_categories',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('name_en', sa.String(100), nullable=True),
        sa.Column('icon', sa.String(10), nullable=True),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('ix_food_categories_id', 'food_categories', ['id'])

    # Создаём таблицу продуктов питания
    op.create_table(
        'food_products',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('category_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('calories', sa.Numeric(8, 2), nullable=False),
        sa.Column('protein', sa.Numeric(6, 2), nullable=False),
        sa.Column('fat', sa.Numeric(6, 2), nullable=False),
        sa.Column('carbs', sa.Numeric(6, 2), nullable=False),
        sa.Column('fiber', sa.Numeric(6, 2), default=0),
        sa.Column('unit', sa.String(20), default='г'),
        sa.Column('serving_size', sa.Numeric(8, 2), default=100),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('source', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['category_id'], ['food_categories.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_food_products_id', 'food_products', ['id'])
    op.create_index('ix_food_products_name', 'food_products', ['name'])

    # Создаём таблицу планов питания
    op.create_table(
        'meal_plans',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('target_calories', sa.Integer(), nullable=False),
        sa.Column('target_protein', sa.Numeric(6, 2), nullable=True),
        sa.Column('target_fat', sa.Numeric(6, 2), nullable=True),
        sa.Column('target_carbs', sa.Numeric(6, 2), nullable=True),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('name', sa.String(200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_meal_plans_id', 'meal_plans', ['id'])
    op.create_index('ix_meal_plans_user_id', 'meal_plans', ['user_id'])

    # Создаём таблицу дневных логов питания
    op.create_table(
        'meal_daily_logs',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('meal_plan_id', sa.BigInteger(), nullable=False),
        sa.Column('log_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actual_calories', sa.Numeric(8, 2), default=0),
        sa.Column('actual_protein', sa.Numeric(6, 2), default=0),
        sa.Column('actual_fat', sa.Numeric(6, 2), default=0),
        sa.Column('actual_carbs', sa.Numeric(6, 2), default=0),
        sa.Column('calories_percent', sa.Numeric(5, 2), default=0),
        sa.Column('is_completed', sa.Boolean(), default=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['meal_plan_id'], ['meal_plans.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_meal_daily_logs_id', 'meal_daily_logs', ['id'])
    op.create_index('ix_meal_daily_logs_meal_plan_id', 'meal_daily_logs', ['meal_plan_id'])
    op.create_index('ix_meal_daily_logs_log_date', 'meal_daily_logs', ['log_date'])

    # Создаём таблицу записей приёмов пищи
    op.create_table(
        'meal_entries',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('daily_log_id', sa.BigInteger(), nullable=False),
        sa.Column('food_product_id', sa.BigInteger(), nullable=True),
        sa.Column('meal_type', sa.String(50), nullable=False),
        sa.Column('product_name', sa.String(200), nullable=False),
        sa.Column('portion_size', sa.Numeric(8, 2), nullable=False),
        sa.Column('portion_unit', sa.String(20), default='г'),
        sa.Column('calories', sa.Numeric(8, 2), nullable=False),
        sa.Column('protein', sa.Numeric(6, 2), nullable=False),
        sa.Column('fat', sa.Numeric(6, 2), nullable=False),
        sa.Column('carbs', sa.Numeric(6, 2), nullable=False),
        sa.Column('is_custom', sa.Boolean(), default=False),
        sa.Column('logged_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['daily_log_id'], ['meal_daily_logs.id']),
        sa.ForeignKeyConstraint(['food_product_id'], ['food_products.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_meal_entries_id', 'meal_entries', ['id'])
    op.create_index('ix_meal_entries_daily_log_id', 'meal_entries', ['daily_log_id'])


def downgrade() -> None:
    op.drop_table('meal_entries')
    op.drop_table('meal_daily_logs')
    op.drop_table('meal_plans')
    op.drop_table('food_products')
    op.drop_table('food_categories')
