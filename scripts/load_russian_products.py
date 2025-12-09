#!/usr/bin/env python3
"""
Загрузка российских продуктов из собранных баз в БД.
Объединяет данные из health-diet.ru и Open Food Facts.
Запуск: python scripts/load_russian_products.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, text
from shared.database import get_async_session
from shared.database.models import FoodCategory, FoodProduct

# Файлы с данными
HEALTH_DIET_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'products_health_diet.json')
OPENFOODFACTS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'products_openfoodfacts_ru.json')

# Маппинг категорий на стандартные
CATEGORY_MAPPING = {
    # health-diet.ru категории
    'Баранина и дичь': 'Мясо и птица',
    'Говядина и телятина': 'Мясо и птица',
    'Свинина': 'Мясо и птица',
    'Птица': 'Мясо и птица',
    'Колбасные изделия': 'Мясо и птица',
    'Мясные субпродукты': 'Мясо и птица',
    'Молочные продукты': 'Молочные продукты',
    'Сыры': 'Молочные продукты',
    'Яйца': 'Яйца',
    'Рыба и морепродукты': 'Рыба и морепродукты',
    'Икра и морепродукты': 'Рыба и морепродукты',
    'Овощи': 'Овощи',
    'Зелень': 'Овощи',
    'Фрукты': 'Фрукты',
    'Ягоды': 'Фрукты',
    'Орехи и семечки': 'Орехи и семена',
    'Сухофрукты': 'Фрукты',
    'Грибы': 'Овощи',
    'Бобовые': 'Бобовые',
    'Крупы и каши': 'Крупы и злаки',
    'Мука и макароны': 'Крупы и злаки',
    'Хлеб и выпечка': 'Хлеб и выпечка',
    'Кондитерские изделия': 'Сладости и десерты',
    'Масла и жиры': 'Масла и жиры',
    'Соусы и приправы': 'Соусы и приправы',
    'Напитки': 'Напитки',
    # Open Food Facts категории
    'Мясо': 'Мясо и птица',
    'Снеки': 'Снеки и закуски',
    'Десерты': 'Сладости и десерты',
    'Морепродукты': 'Рыба и морепродукты',
    'Замороженные продукты': 'Замороженные продукты',
    'Консервы': 'Консервы',
    'Другое': 'Другое',
}


async def load_products():
    """Загрузка продуктов в БД"""
    print("=" * 60)
    print("Загрузка российских продуктов в базу данных")
    print("=" * 60)

    # Собираем все продукты
    all_products = []
    seen_names = set()

    # Загружаем health-diet.ru
    if os.path.exists(HEALTH_DIET_FILE):
        print(f"\n1. Загрузка {HEALTH_DIET_FILE}...")
        with open(HEALTH_DIET_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for p in data.get('products', []):
            name = p['name'][:200].strip()
            if name and name not in seen_names:
                seen_names.add(name)
                all_products.append({
                    'name': name,
                    'category': CATEGORY_MAPPING.get(p.get('category', ''), 'Другое'),
                    'calories': p.get('calories', 0),
                    'protein': p.get('protein', 0),
                    'fat': p.get('fat', 0),
                    'carbs': p.get('carbs', 0),
                    'source': 'health-diet.ru'
                })
        print(f"   Загружено: {len(all_products)} продуктов")

    # Загружаем Open Food Facts
    if os.path.exists(OPENFOODFACTS_FILE):
        print(f"\n2. Загрузка {OPENFOODFACTS_FILE}...")
        with open(OPENFOODFACTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        added = 0
        for p in data.get('products', []):
            name = p['name'][:200].strip()
            # Очищаем HTML entities
            name = name.replace('&quot;', '"').replace('&amp;', '&')
            if name and name not in seen_names:
                seen_names.add(name)
                all_products.append({
                    'name': name,
                    'category': CATEGORY_MAPPING.get(p.get('category', ''), 'Другое'),
                    'calories': p.get('calories', 0),
                    'protein': p.get('protein', 0),
                    'fat': p.get('fat', 0),
                    'carbs': p.get('carbs', 0),
                    'source': 'openfoodfacts'
                })
                added += 1
        print(f"   Добавлено: {added} продуктов")

    print(f"\n   Всего уникальных продуктов: {len(all_products)}")

    # Подключаемся к БД
    print("\n3. Подключение к базе данных...")
    async for session in get_async_session():
        # Получаем существующие категории
        result = await session.execute(select(FoodCategory))
        existing_categories = {cat.name: cat.id for cat in result.scalars().all()}
        print(f"   Существующих категорий: {len(existing_categories)}")

        # Создаём недостающие категории
        needed_categories = set(p['category'] for p in all_products)
        new_categories = needed_categories - set(existing_categories.keys())

        if new_categories:
            print(f"\n4. Создание новых категорий: {len(new_categories)}")
            for cat_name in sorted(new_categories):
                new_cat = FoodCategory(name=cat_name)
                session.add(new_cat)
            await session.commit()

            # Обновляем маппинг
            result = await session.execute(select(FoodCategory))
            existing_categories = {cat.name: cat.id for cat in result.scalars().all()}
            print(f"   Создано категорий: {len(new_categories)}")

        # Очищаем старые продукты
        print("\n5. Очистка старых продуктов...")
        await session.execute(text("DELETE FROM food_products"))
        await session.commit()
        print("   Старые продукты удалены")

        # Загружаем новые продукты
        print(f"\n6. Загрузка {len(all_products)} продуктов...")
        batch_size = 500
        loaded = 0
        skipped = 0

        for i in range(0, len(all_products), batch_size):
            batch = all_products[i:i+batch_size]

            for prod in batch:
                cat_id = existing_categories.get(prod['category'])
                if not cat_id:
                    skipped += 1
                    continue

                new_prod = FoodProduct(
                    category_id=cat_id,
                    name=prod['name'],
                    calories=prod['calories'],
                    protein=prod['protein'],
                    fat=prod['fat'],
                    carbs=prod['carbs'],
                )
                session.add(new_prod)
                loaded += 1

            await session.commit()
            print(f"   Загружено: {loaded}/{len(all_products)}")

        print(f"\n   Итого загружено: {loaded}")
        if skipped:
            print(f"   Пропущено: {skipped}")

    # Статистика по категориям
    print("\n" + "=" * 60)
    print("СТАТИСТИКА ПО КАТЕГОРИЯМ")
    print("=" * 60)

    category_stats = {}
    for p in all_products:
        cat = p['category']
        category_stats[cat] = category_stats.get(cat, 0) + 1

    for cat, count in sorted(category_stats.items(), key=lambda x: -x[1]):
        print(f"   {cat:<30} {count:>5} продуктов")

    print("\n✅ Загрузка завершена!")


if __name__ == "__main__":
    asyncio.run(load_products())
