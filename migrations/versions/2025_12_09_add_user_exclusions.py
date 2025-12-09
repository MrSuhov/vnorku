"""add_user_exclusions

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2025-12-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создаём таблицу категорий исключений
    op.create_table(
        'exclusion_categories',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('icon', sa.String(10), nullable=True),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_index('ix_exclusion_categories_id', 'exclusion_categories', ['id'])
    op.create_index('ix_exclusion_categories_code', 'exclusion_categories', ['code'])

    # Создаём таблицу ключевых слов для категорий
    op.create_table(
        'exclusion_keywords',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('category_id', sa.BigInteger(), nullable=False),
        sa.Column('keyword', sa.String(100), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['category_id'], ['exclusion_categories.id'], ondelete='CASCADE')
    )
    op.create_index('ix_exclusion_keywords_id', 'exclusion_keywords', ['id'])
    op.create_index('ix_exclusion_keywords_category_id', 'exclusion_keywords', ['category_id'])
    op.create_index('ix_exclusion_keywords_keyword', 'exclusion_keywords', ['keyword'])

    # Создаём таблицу типов диет
    op.create_table(
        'diet_types',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(10), nullable=True),
        sa.Column('excluded_categories', sa.JSON(), default=list),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_index('ix_diet_types_id', 'diet_types', ['id'])
    op.create_index('ix_diet_types_code', 'diet_types', ['code'])

    # Создаём таблицу исключений пользователя
    op.create_table(
        'user_exclusions',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('diet_type_code', sa.String(50), nullable=True),
        sa.Column('excluded_categories', sa.JSON(), default=list),
        sa.Column('excluded_products', sa.JSON(), default=list),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index('ix_user_exclusions_id', 'user_exclusions', ['id'])
    op.create_index('ix_user_exclusions_user_id', 'user_exclusions', ['user_id'])

    # Заполняем начальные данные категорий исключений
    op.execute("""
        INSERT INTO exclusion_categories (id, code, name, icon, sort_order, is_active) VALUES
        (1, 'dairy', 'Молочные продукты', '🥛', 1, true),
        (2, 'gluten', 'Глютен', '🌾', 2, true),
        (3, 'nuts', 'Орехи', '🥜', 3, true),
        (4, 'seafood', 'Морепродукты и рыба', '🐟', 4, true),
        (5, 'meat', 'Мясо', '🥩', 5, true),
        (6, 'poultry', 'Птица', '🍗', 6, true),
        (7, 'eggs', 'Яйца', '🥚', 7, true),
        (8, 'honey', 'Мёд', '🍯', 8, true),
        (9, 'sugar', 'Сахар', '🍬', 9, true),
        (10, 'grains', 'Злаки и крупы', '🌾', 10, true),
        (11, 'soy', 'Соя', '🫘', 11, true),
        (12, 'alcohol', 'Алкоголь', '🍷', 12, true)
    """)

    # Заполняем ключевые слова для категорий
    op.execute("""
        INSERT INTO exclusion_keywords (category_id, keyword, is_active) VALUES
        -- Молочные продукты (dairy)
        (1, 'молоко', true),
        (1, 'молочн', true),
        (1, 'сыр', true),
        (1, 'творог', true),
        (1, 'сметан', true),
        (1, 'йогурт', true),
        (1, 'кефир', true),
        (1, 'сливк', true),
        (1, 'масло сливочное', true),
        (1, 'ряженка', true),
        (1, 'простокваша', true),
        (1, 'сырок', true),
        (1, 'сырн', true),
        (1, 'пармезан', true),
        (1, 'моцарелла', true),
        (1, 'брынза', true),
        (1, 'фета', true),

        -- Глютен (gluten)
        (2, 'пшениц', true),
        (2, 'хлеб', true),
        (2, 'батон', true),
        (2, 'булк', true),
        (2, 'булочк', true),
        (2, 'макарон', true),
        (2, 'спагетти', true),
        (2, 'паста', true),
        (2, 'лапша', true),
        (2, 'мука пшеничн', true),
        (2, 'лаваш', true),
        (2, 'ячмень', true),
        (2, 'ячмен', true),
        (2, 'рожь', true),
        (2, 'ржан', true),
        (2, 'овёс', true),
        (2, 'овсян', true),
        (2, 'манк', true),
        (2, 'кускус', true),
        (2, 'пельмен', true),
        (2, 'вареник', true),
        (2, 'блин', true),
        (2, 'оладь', true),
        (2, 'печень', true),
        (2, 'торт', true),
        (2, 'пирог', true),
        (2, 'пирожк', true),
        (2, 'пицц', true),

        -- Орехи (nuts)
        (3, 'орех', true),
        (3, 'миндаль', true),
        (3, 'фундук', true),
        (3, 'кешью', true),
        (3, 'фисташк', true),
        (3, 'грецк', true),
        (3, 'арахис', true),
        (3, 'пекан', true),
        (3, 'макадам', true),
        (3, 'кедров', true),
        (3, 'каштан', true),

        -- Морепродукты и рыба (seafood)
        (4, 'рыб', true),
        (4, 'лосось', true),
        (4, 'сёмга', true),
        (4, 'семга', true),
        (4, 'форель', true),
        (4, 'тунец', true),
        (4, 'скумбрия', true),
        (4, 'сельдь', true),
        (4, 'селёдк', true),
        (4, 'треск', true),
        (4, 'минтай', true),
        (4, 'карп', true),
        (4, 'щук', true),
        (4, 'судак', true),
        (4, 'окунь', true),
        (4, 'сом', true),
        (4, 'креветк', true),
        (4, 'кальмар', true),
        (4, 'мидии', true),
        (4, 'устриц', true),
        (4, 'краб', true),
        (4, 'омар', true),
        (4, 'лангуст', true),
        (4, 'осьминог', true),
        (4, 'икр', true),
        (4, 'морепродукт', true),

        -- Мясо (meat)
        (5, 'говядин', true),
        (5, 'свинин', true),
        (5, 'баранин', true),
        (5, 'телятин', true),
        (5, 'фарш', true),
        (5, 'стейк', true),
        (5, 'колбас', true),
        (5, 'сосиск', true),
        (5, 'сардельк', true),
        (5, 'ветчин', true),
        (5, 'бекон', true),
        (5, 'грудинк', true),
        (5, 'корейк', true),
        (5, 'шашлык', true),
        (5, 'котлет', true),
        (5, 'буженин', true),
        (5, 'сало', true),
        (5, 'мясо', true),
        (5, 'мясн', true),
        (5, 'субпродукт', true),
        (5, 'печень говяж', true),
        (5, 'печень свин', true),
        (5, 'язык', true),
        (5, 'почк', true),
        (5, 'сердц', true),

        -- Птица (poultry)
        (6, 'курица', true),
        (6, 'куриц', true),
        (6, 'курин', true),
        (6, 'индейк', true),
        (6, 'утк', true),
        (6, 'гус', true),
        (6, 'цыпл', true),
        (6, 'перепел', true),
        (6, 'птиц', true),
        (6, 'печень куриц', true),

        -- Яйца (eggs)
        (7, 'яйц', true),
        (7, 'яичн', true),
        (7, 'омлет', true),
        (7, 'яичниц', true),
        (7, 'глазунь', true),

        -- Мёд (honey)
        (8, 'мёд', true),
        (8, 'мед', true),
        (8, 'медов', true),

        -- Сахар (sugar)
        (9, 'сахар', true),
        (9, 'сахарн', true),
        (9, 'конфет', true),
        (9, 'шоколад', true),
        (9, 'варень', true),
        (9, 'джем', true),
        (9, 'повидл', true),
        (9, 'мармелад', true),
        (9, 'зефир', true),
        (9, 'пастил', true),
        (9, 'халв', true),
        (9, 'карамель', true),
        (9, 'ирис', true),
        (9, 'леденец', true),
        (9, 'пряник', true),
        (9, 'вафл', true),
        (9, 'мороженое', true),

        -- Злаки и крупы (grains)
        (10, 'крупа', true),
        (10, 'рис', true),
        (10, 'гречк', true),
        (10, 'гречнев', true),
        (10, 'перловк', true),
        (10, 'пшено', true),
        (10, 'пшённ', true),
        (10, 'ячневая', true),
        (10, 'кукурузн', true),
        (10, 'булгур', true),
        (10, 'киноа', true),
        (10, 'полба', true),

        -- Соя (soy)
        (11, 'соя', true),
        (11, 'соев', true),
        (11, 'тофу', true),
        (11, 'темпе', true),
        (11, 'эдамаме', true),
        (11, 'мисо', true),

        -- Алкоголь (alcohol)
        (12, 'вино', true),
        (12, 'винн', true),
        (12, 'пиво', true),
        (12, 'пивн', true),
        (12, 'водк', true),
        (12, 'коньяк', true),
        (12, 'виски', true),
        (12, 'ром', true),
        (12, 'джин', true),
        (12, 'ликёр', true),
        (12, 'ликер', true),
        (12, 'шампанск', true),
        (12, 'сидр', true),
        (12, 'алкогол', true)
    """)

    # Заполняем типы диет
    op.execute("""
        INSERT INTO diet_types (id, code, name, description, icon, excluded_categories, sort_order, is_active) VALUES
        (1, 'vegan', 'Веган', 'Исключает все продукты животного происхождения', '🌱', '["meat", "poultry", "seafood", "dairy", "eggs", "honey"]', 1, true),
        (2, 'vegetarian', 'Вегетарианец', 'Исключает мясо, птицу и рыбу', '🥬', '["meat", "poultry", "seafood"]', 2, true),
        (3, 'pescatarian', 'Пескетарианец', 'Исключает мясо и птицу, но разрешает рыбу', '🐠', '["meat", "poultry"]', 3, true),
        (4, 'keto', 'Кето', 'Низкоуглеводная диета, исключает сахар и злаки', '🥑', '["sugar", "grains"]', 4, true),
        (5, 'lactose_free', 'Без лактозы', 'Исключает молочные продукты', '🚫🥛', '["dairy"]', 5, true),
        (6, 'gluten_free', 'Без глютена', 'Исключает продукты с глютеном', '🚫🌾', '["gluten"]', 6, true)
    """)


def downgrade() -> None:
    op.drop_table('user_exclusions')
    op.drop_table('diet_types')
    op.drop_table('exclusion_keywords')
    op.drop_table('exclusion_categories')
