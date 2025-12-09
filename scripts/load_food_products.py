#!/usr/bin/env python3
"""
Скрипт для загрузки продуктов питания из JSON в базу данных.
Запуск: python scripts/load_food_products.py
"""
import asyncio
import json
import sys
import os

# Добавляем корневую папку проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from shared.database import get_async_session
from shared.database.models import FoodCategory, FoodProduct


# Иконки для категорий
CATEGORY_ICONS = {
    "dairy": "🥛",
    "meat": "🥩",
    "seafood": "🐟",
    "vegetables": "🥬",
    "fruits": "🍎",
    "grains": "🌾",
    "bread": "🍞",
    "eggs": "🥚",
    "oils": "🫒",
    "nuts": "🥜",
    "legumes": "🫘",
    "beverages": "☕"
}


async def load_food_products():
    """Загрузка продуктов питания из JSON в БД"""

    # Путь к JSON файлу
    json_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'products_ru.json'
    )

    if not os.path.exists(json_path):
        print(f"❌ Файл не найден: {json_path}")
        return

    # Читаем JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"📂 Загружено из JSON:")
    print(f"   Категорий: {len(data['categories'])}")
    print(f"   Продуктов: {len(data['products'])}")

    async for db in get_async_session():
        # Загружаем категории
        category_map = {}  # old_id -> new_id

        for cat in data['categories']:
            # Проверяем, есть ли уже такая категория
            result = await db.execute(
                select(FoodCategory).where(FoodCategory.name == cat['name'])
            )
            existing = result.scalar_one_or_none()

            if existing:
                category_map[cat['id']] = existing.id
                print(f"   ✓ Категория '{cat['name']}' уже существует (id={existing.id})")
            else:
                new_cat = FoodCategory(
                    name=cat['name'],
                    name_en=cat.get('name_en'),
                    icon=CATEGORY_ICONS.get(cat.get('name_en'), '📦'),
                    sort_order=cat['id'],
                    is_active=True
                )
                db.add(new_cat)
                await db.flush()  # Получаем ID
                category_map[cat['id']] = new_cat.id
                print(f"   + Добавлена категория '{cat['name']}' (id={new_cat.id})")

        await db.commit()
        print(f"\n✅ Загружено {len(category_map)} категорий")

        # Загружаем продукты
        products_added = 0
        products_skipped = 0

        for prod in data['products']:
            # Проверяем, есть ли уже такой продукт
            result = await db.execute(
                select(FoodProduct).where(FoodProduct.name == prod['name'])
            )
            existing = result.scalar_one_or_none()

            if existing:
                products_skipped += 1
                continue

            new_prod = FoodProduct(
                category_id=category_map[prod['category_id']],
                name=prod['name'],
                calories=prod['calories'],
                protein=prod['protein'],
                fat=prod['fat'],
                carbs=prod['carbs'],
                fiber=prod.get('fiber', 0),
                unit=prod.get('unit', 'г'),
                serving_size=prod.get('serving_size', 100),
                is_active=True,
                source='vnorku_base_v1'
            )
            db.add(new_prod)
            products_added += 1

        await db.commit()

        print(f"\n✅ Результат:")
        print(f"   Добавлено продуктов: {products_added}")
        print(f"   Пропущено (уже есть): {products_skipped}")

        # Статистика
        result = await db.execute(select(FoodProduct))
        total = len(result.scalars().all())
        print(f"\n📊 Всего продуктов в базе: {total}")


if __name__ == "__main__":
    print("🍎 Загрузка продуктов питания в базу данных...\n")
    asyncio.run(load_food_products())
    print("\n✅ Готово!")
