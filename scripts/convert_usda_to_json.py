#!/usr/bin/env python3
"""
Скрипт для конвертации USDA FoodData Central SR Legacy в формат JSON.
Создаёт products_usda.json с ~7800 продуктами.
"""
import csv
import json
import os
from collections import defaultdict

# Пути к файлам USDA
USDA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'usda',
                        'FoodData_Central_sr_legacy_food_csv_2018-04')
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'products_usda.json')

# ID нутриентов
NUTRIENT_IDS = {
    '1008': 'calories',  # Energy (KCAL)
    '1003': 'protein',   # Protein (G)
    '1004': 'fat',       # Total lipid (fat) (G)
    '1005': 'carbs',     # Carbohydrate, by difference (G)
    '1079': 'fiber',     # Fiber, total dietary (G)
}

# Маппинг категорий USDA -> наши категории
CATEGORY_MAPPING = {
    '0100': {'name': 'Молочные продукты и яйца', 'name_en': 'dairy_eggs', 'icon': '🥛'},
    '0200': {'name': 'Специи и травы', 'name_en': 'spices', 'icon': '🌿'},
    '0300': {'name': 'Детское питание', 'name_en': 'baby_food', 'icon': '🍼'},
    '0400': {'name': 'Масла и жиры', 'name_en': 'oils', 'icon': '🫒'},
    '0500': {'name': 'Птица', 'name_en': 'poultry', 'icon': '🍗'},
    '0600': {'name': 'Супы и соусы', 'name_en': 'soups', 'icon': '🍲'},
    '0700': {'name': 'Колбасы и мясные изделия', 'name_en': 'sausages', 'icon': '🌭'},
    '0800': {'name': 'Завтраки и хлопья', 'name_en': 'cereals', 'icon': '🥣'},
    '0900': {'name': 'Фрукты и соки', 'name_en': 'fruits', 'icon': '🍎'},
    '1000': {'name': 'Свинина', 'name_en': 'pork', 'icon': '🥓'},
    '1100': {'name': 'Овощи', 'name_en': 'vegetables', 'icon': '🥬'},
    '1200': {'name': 'Орехи и семена', 'name_en': 'nuts', 'icon': '🥜'},
    '1300': {'name': 'Говядина', 'name_en': 'beef', 'icon': '🥩'},
    '1400': {'name': 'Напитки', 'name_en': 'beverages', 'icon': '🥤'},
    '1500': {'name': 'Рыба и морепродукты', 'name_en': 'seafood', 'icon': '🐟'},
    '1600': {'name': 'Бобовые', 'name_en': 'legumes', 'icon': '🫘'},
    '1700': {'name': 'Баранина и дичь', 'name_en': 'lamb', 'icon': '🍖'},
    '1800': {'name': 'Выпечка', 'name_en': 'baked', 'icon': '🍞'},
    '1900': {'name': 'Сладости', 'name_en': 'sweets', 'icon': '🍫'},
    '2000': {'name': 'Крупы и злаки', 'name_en': 'grains', 'icon': '🌾'},
    '2100': {'name': 'Фастфуд', 'name_en': 'fastfood', 'icon': '🍔'},
    '2200': {'name': 'Готовые блюда', 'name_en': 'prepared', 'icon': '🍱'},
    '2500': {'name': 'Закуски', 'name_en': 'snacks', 'icon': '🍿'},
    '3500': {'name': 'Индейка', 'name_en': 'turkey', 'icon': '🦃'},
    '3600': {'name': 'Телятина', 'name_en': 'veal', 'icon': '🥩'},
    '1100': {'name': 'Овощи', 'name_en': 'vegetables', 'icon': '🥬'},
}


def load_categories():
    """Загрузка категорий из CSV"""
    categories = {}
    with open(os.path.join(USDA_DIR, 'food_category.csv'), 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cat_id = row['id']
            code = row['code']
            mapping = CATEGORY_MAPPING.get(code, {
                'name': row['description'],
                'name_en': code,
                'icon': '📦'
            })
            categories[cat_id] = {
                'id': int(cat_id),
                'code': code,
                'name': mapping['name'],
                'name_en': mapping['name_en'],
                'icon': mapping['icon'],
                'original_name': row['description']
            }
    return categories


def load_foods():
    """Загрузка продуктов из CSV"""
    foods = {}
    with open(os.path.join(USDA_DIR, 'food.csv'), 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            fdc_id = row['fdc_id']
            foods[fdc_id] = {
                'fdc_id': fdc_id,
                'name_en': row['description'],
                'category_id': row['food_category_id'],
                'calories': 0,
                'protein': 0,
                'fat': 0,
                'carbs': 0,
                'fiber': 0
            }
    return foods


def load_nutrients(foods):
    """Загрузка нутриентов и добавление к продуктам"""
    print(f"Загрузка нутриентов из food_nutrient.csv...")
    count = 0
    with open(os.path.join(USDA_DIR, 'food_nutrient.csv'), 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            fdc_id = row['fdc_id']
            nutrient_id = row['nutrient_id']

            if fdc_id in foods and nutrient_id in NUTRIENT_IDS:
                try:
                    amount = float(row['amount']) if row['amount'] else 0
                    field = NUTRIENT_IDS[nutrient_id]
                    foods[fdc_id][field] = round(amount, 2)
                    count += 1
                except ValueError:
                    pass
    print(f"Загружено {count} записей нутриентов")
    return foods


def main():
    print("=" * 60)
    print("Конвертация USDA FoodData Central SR Legacy в JSON")
    print("=" * 60)

    # Загрузка данных
    print("\n1. Загрузка категорий...")
    categories = load_categories()
    print(f"   Загружено {len(categories)} категорий")

    print("\n2. Загрузка продуктов...")
    foods = load_foods()
    print(f"   Загружено {len(foods)} продуктов")

    print("\n3. Загрузка нутриентов...")
    foods = load_nutrients(foods)

    # Фильтруем продукты без калорий
    valid_foods = {k: v for k, v in foods.items() if v['calories'] > 0}
    print(f"\n4. Продуктов с калориями: {len(valid_foods)}")

    # Группируем по категориям
    products_by_category = defaultdict(list)
    for fdc_id, food in valid_foods.items():
        cat_id = food['category_id']
        if cat_id in categories:
            products_by_category[cat_id].append(food)

    # Формируем итоговый JSON
    result = {
        'source': 'USDA FoodData Central SR Legacy 2018-04',
        'total_products': len(valid_foods),
        'categories': list(categories.values()),
        'products': list(valid_foods.values())
    }

    # Сохраняем
    print(f"\n5. Сохранение в {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Статистика
    print("\n" + "=" * 60)
    print("СТАТИСТИКА:")
    print("=" * 60)
    print(f"Всего категорий: {len(categories)}")
    print(f"Всего продуктов: {len(valid_foods)}")
    print("\nПо категориям:")
    for cat_id, cat in sorted(categories.items(), key=lambda x: x[1]['code']):
        count = len(products_by_category.get(cat_id, []))
        if count > 0:
            print(f"  {cat['icon']} {cat['name']}: {count}")

    print(f"\n✅ Файл сохранён: {OUTPUT_FILE}")
    print(f"   Размер: {os.path.getsize(OUTPUT_FILE) / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
