#!/usr/bin/env python3
"""
Скрипт для загрузки переведённых продуктов USDA в базу данных.
Запуск: python scripts/load_usda_products.py
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, text
from shared.database import get_async_session
from shared.database.models import FoodCategory, FoodProduct


# Пробуем переведённый файл, если нет - используем оригинал
INPUT_FILE_RU = os.path.join(os.path.dirname(__file__), '..', 'data', 'products_usda_ru.json')
INPUT_FILE_EN = os.path.join(os.path.dirname(__file__), '..', 'data', 'products_usda.json')
INPUT_FILE = INPUT_FILE_RU if os.path.exists(INPUT_FILE_RU) else INPUT_FILE_EN


async def load_usda_products():
    """Загрузка продуктов USDA в БД"""
    print("=" * 60)
    print("Загрузка продуктов USDA в базу данных")
    print("=" * 60)

    # Проверяем наличие файла
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Файл не найден: {INPUT_FILE}")
        print("   Сначала запустите: python scripts/translate_products.py")
        return

    # Загружаем данные
    print("\n1. Загрузка JSON...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    categories = data['categories']
    products = data['products']

    print(f"   Категорий: {len(categories)}")
    print(f"   Продуктов: {len(products)}")

    async for db in get_async_session():
        # Очищаем существующие данные (опционально)
        print("\n2. Очистка существующих данных...")
        await db.execute(text("DELETE FROM food_products"))
        await db.execute(text("DELETE FROM food_categories"))
        await db.commit()
        print("   ✓ Таблицы очищены")

        # Загружаем категории
        print("\n3. Загрузка категорий...")
        category_map = {}  # code -> id

        for i, cat in enumerate(categories):
            new_cat = FoodCategory(
                name=cat['name'],
                name_en=cat['name_en'],
                icon=cat['icon'],
                sort_order=i + 1,
                is_active=True
            )
            db.add(new_cat)
            await db.flush()
            category_map[cat['code']] = new_cat.id
            # Также маппим по id из USDA
            category_map[str(cat['id'])] = new_cat.id

        await db.commit()
        print(f"   ✓ Загружено {len(categories)} категорий")

        # Загружаем продукты батчами
        print("\n4. Загрузка продуктов...")
        batch_size = 500
        loaded = 0
        skipped = 0

        for i in range(0, len(products), batch_size):
            batch = products[i:i+batch_size]

            for prod in batch:
                cat_id = category_map.get(prod['category_id'])
                if not cat_id:
                    skipped += 1
                    continue

                # Используем русское название если есть, иначе английское
                name = prod.get('name') or prod.get('name_en', 'Unknown')
                if len(name) > 200:
                    name = name[:197] + "..."

                new_prod = FoodProduct(
                    category_id=cat_id,
                    name=name,
                    calories=prod['calories'],
                    protein=prod['protein'],
                    fat=prod['fat'],
                    carbs=prod['carbs'],
                    fiber=prod.get('fiber', 0),
                    unit='г',
                    serving_size=100,
                    is_active=True,
                    source='USDA SR Legacy'
                )
                db.add(new_prod)
                loaded += 1

            await db.commit()
            print(f"   Загружено: {loaded} / {len(products)}", end="\r")

        print(f"\n   ✓ Загружено: {loaded} продуктов")
        if skipped:
            print(f"   ⚠ Пропущено (нет категории): {skipped}")

        # Статистика
        print("\n" + "=" * 60)
        print("СТАТИСТИКА")
        print("=" * 60)

        result = await db.execute(
            text("""
                SELECT fc.name, fc.icon, COUNT(fp.id) as count
                FROM food_categories fc
                LEFT JOIN food_products fp ON fp.category_id = fc.id
                GROUP BY fc.id, fc.name, fc.icon
                ORDER BY count DESC
            """)
        )
        rows = result.fetchall()

        print(f"\n{'Категория':<40} {'Продуктов':>10}")
        print("-" * 52)
        total = 0
        for row in rows:
            print(f"{row.icon} {row.name:<37} {row.count:>10}")
            total += row.count
        print("-" * 52)
        print(f"{'ВСЕГО':<40} {total:>10}")

        break

    print("\n✅ Загрузка завершена!")


if __name__ == "__main__":
    print("🍎 Загрузка продуктов USDA в базу данных...\n")
    asyncio.run(load_usda_products())
