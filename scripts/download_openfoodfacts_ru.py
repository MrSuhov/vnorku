#!/usr/bin/env python3
"""
Скачивание российских продуктов из Open Food Facts API.
Запуск: python scripts/download_openfoodfacts_ru.py
"""
import json
import os
import time
import requests

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'products_openfoodfacts_ru.json')
API_URL = 'https://world.openfoodfacts.org/cgi/search.pl'

# Категории на русском для группировки
CATEGORY_MAPPING = {
    'beverages': 'Напитки',
    'dairies': 'Молочные продукты',
    'meats': 'Мясо',
    'snacks': 'Снеки',
    'desserts': 'Десерты',
    'cereals': 'Крупы и злаки',
    'fruits': 'Фрукты',
    'vegetables': 'Овощи',
    'fats': 'Масла и жиры',
    'seafood': 'Морепродукты',
    'breads': 'Хлеб и выпечка',
    'cheeses': 'Сыры',
    'sauces': 'Соусы',
    'frozen': 'Замороженные продукты',
    'canned': 'Консервы',
    'baby-foods': 'Детское питание',
    'plant-based': 'Растительные продукты',
}


def get_russian_category(categories_tags: list) -> str:
    """Определение русской категории по тегам"""
    if not categories_tags:
        return 'Другое'

    for tag in categories_tags:
        tag_lower = tag.lower().replace('en:', '').replace('ru:', '')
        for key, ru_name in CATEGORY_MAPPING.items():
            if key in tag_lower:
                return ru_name

    return 'Другое'


def download_products():
    """Скачивание продуктов из Open Food Facts"""
    print("=" * 60)
    print("Скачивание российских продуктов из Open Food Facts")
    print("=" * 60)

    # Загружаем существующие данные если есть
    all_products = []
    existing_barcodes = set()

    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                existing = json.load(f)
                all_products = existing.get('products', [])
                existing_barcodes = {p.get('barcode') for p in all_products if p.get('barcode')}
                print(f"\n   Загружено существующих: {len(all_products)} продуктов")
        except:
            pass

    page = 1
    page_size = 100
    max_pages = 300  # Ограничение ~30000 продуктов
    max_errors = 10
    errors = 0

    print(f"\nЗагрузка продуктов (страницами по {page_size})...")

    while page <= max_pages:
        try:
            params = {
                'action': 'process',
                'tagtype_0': 'countries',
                'tag_contains_0': 'contains',
                'tag_0': 'russia',
                'page_size': page_size,
                'page': page,
                'json': 1,
                'fields': 'product_name,product_name_ru,brands,categories_tags,nutriments,code'
            }

            response = requests.get(API_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            products = data.get('products', [])
            if not products:
                print(f"\n   Страница {page}: пустая, завершаю")
                break

            for p in products:
                nutriments = p.get('nutriments', {})

                # Получаем КБЖУ
                calories = nutriments.get('energy-kcal', nutriments.get('energy-kcal_100g', 0))
                protein = nutriments.get('proteins', nutriments.get('proteins_100g', 0))
                fat = nutriments.get('fat', nutriments.get('fat_100g', 0))
                carbs = nutriments.get('carbohydrates', nutriments.get('carbohydrates_100g', 0))

                # Получаем название (предпочитаем русское)
                name = p.get('product_name_ru') or p.get('product_name', '')
                if not name:
                    continue

                # Добавляем бренд если есть
                brand = p.get('brands', '')
                if brand and brand.lower() not in name.lower():
                    name = f"{name} ({brand})"

                # Проверяем что есть хотя бы калории и это не дубликат
                barcode = p.get('code', '')
                if calories and float(calories) > 0 and barcode not in existing_barcodes:
                    existing_barcodes.add(barcode)
                    all_products.append({
                        'name': name[:200],
                        'category': get_russian_category(p.get('categories_tags', [])),
                        'calories': round(float(calories or 0), 1),
                        'protein': round(float(protein or 0), 1),
                        'fat': round(float(fat or 0), 1),
                        'carbs': round(float(carbs or 0), 1),
                        'barcode': p.get('code', ''),
                    })

            if page % 10 == 0:
                print(f"   Страница {page}: загружено {len(all_products)} продуктов")

            page += 1
            time.sleep(0.3)  # Пауза между запросами

        except Exception as e:
            errors += 1
            print(f"\n   Ошибка на странице {page}: {e}")
            if errors >= max_errors:
                print(f"\n   Достигнут лимит ошибок ({max_errors}), сохраняю...")
                break
            page += 1
            time.sleep(2)  # Увеличенная пауза при ошибке

    print(f"\n   Всего загружено: {len(all_products)} продуктов")

    # Группируем по категориям
    categories = {}
    for p in all_products:
        cat = p['category']
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += 1

    categories_list = [{'name': k, 'count': v} for k, v in sorted(categories.items(), key=lambda x: -x[1])]

    # Сохраняем
    result = {
        'source': 'Open Food Facts (Russia)',
        'total_count': len(all_products),
        'categories': categories_list,
        'products': all_products
    }

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n   Сохранено в {OUTPUT_FILE}")

    # Статистика по категориям
    print("\n" + "=" * 60)
    print("КАТЕГОРИИ")
    print("=" * 60)
    for cat in categories_list[:15]:
        print(f"   {cat['name']:<30} {cat['count']:>5} продуктов")

    # Примеры
    print("\n" + "=" * 60)
    print("ПРИМЕРЫ ПРОДУКТОВ")
    print("=" * 60)
    for p in all_products[:15]:
        print(f"   {p['name'][:40]:<42} | К:{p['calories']:>6} Б:{p['protein']:>5} Ж:{p['fat']:>5} У:{p['carbs']:>5}")

    print("\n✅ Готово!")
    return result


if __name__ == "__main__":
    download_products()
