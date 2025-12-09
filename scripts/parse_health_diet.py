#!/usr/bin/env python3
"""
Парсер базы продуктов с health-diet.ru
Запуск: python scripts/parse_health_diet.py
"""
import json
import os
import time
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'products_health_diet.json')
BASE_URL = 'https://health-diet.ru'

# Актуальные категории продуктов на health-diet.ru (декабрь 2024)
CATEGORIES = [
    ('Баранина и дичь', '/base_of_food/food_24507/'),
    ('Говядина и телятина', '/base_of_food/food_24502/'),
    ('Свинина', '/base_of_food/food_24504/'),
    ('Птица', '/base_of_food/food_24505/'),
    ('Колбасные изделия', '/base_of_food/food_24506/'),
    ('Мясные субпродукты', '/base_of_food/food_24508/'),
    ('Молочные продукты', '/base_of_food/food_24519/'),
    ('Сыры', '/base_of_food/food_24520/'),
    ('Яйца', '/base_of_food/food_24521/'),
    ('Рыба и морепродукты', '/base_of_food/food_24509/'),
    ('Икра и морепродукты', '/base_of_food/food_24510/'),
    ('Овощи', '/base_of_food/food_24511/'),
    ('Зелень', '/base_of_food/food_24512/'),
    ('Фрукты', '/base_of_food/food_24513/'),
    ('Ягоды', '/base_of_food/food_24514/'),
    ('Орехи и семечки', '/base_of_food/food_24515/'),
    ('Сухофрукты', '/base_of_food/food_24516/'),
    ('Грибы', '/base_of_food/food_24517/'),
    ('Бобовые', '/base_of_food/food_24518/'),
    ('Крупы и каши', '/base_of_food/food_24522/'),
    ('Мука и макароны', '/base_of_food/food_24523/'),
    ('Хлеб и выпечка', '/base_of_food/food_24524/'),
    ('Кондитерские изделия', '/base_of_food/food_24525/'),
    ('Масла и жиры', '/base_of_food/food_24526/'),
    ('Соусы и приправы', '/base_of_food/food_24527/'),
    ('Напитки', '/base_of_food/food_24528/'),
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
}


def parse_number(text: str) -> float:
    """Парсинг числа из текста"""
    if not text:
        return 0.0
    # Убираем пробелы, заменяем запятую на точку
    text = text.strip().replace(',', '.').replace(' ', '')
    # Извлекаем число
    match = re.search(r'[\d.]+', text)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return 0.0
    return 0.0


def parse_category_page(url: str, category_name: str, retries: int = 3) -> list:
    """Парсинг страницы категории с retry"""
    products = []

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30, verify=False)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            break
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            print(f"      Ошибка после {retries} попыток: {e}")
            return products

    try:

        # Ищем таблицу с продуктами
        table = soup.find('table', class_='uk-table')
        if not table:
            # Альтернативный селектор
            table = soup.find('table')

        if not table:
            print(f"      Таблица не найдена на {url}")
            return products

        rows = table.find_all('tr')[1:]  # Пропускаем заголовок

        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 5:
                try:
                    name_cell = cols[0]
                    name = name_cell.get_text(strip=True)

                    # Извлекаем КБЖУ (порядок: Калорийность | Белки | Жиры | Углеводы)
                    calories = parse_number(cols[1].get_text())
                    protein = parse_number(cols[2].get_text())
                    fat = parse_number(cols[3].get_text())
                    carbs = parse_number(cols[4].get_text())

                    if name and calories > 0:
                        products.append({
                            'name': name,
                            'category': category_name,
                            'calories': round(calories, 1),
                            'protein': round(protein, 1),
                            'fat': round(fat, 1),
                            'carbs': round(carbs, 1),
                        })
                except Exception as e:
                    continue

    except Exception as e:
        pass

    return products


def parse_all_products():
    """Парсинг всех категорий"""
    print("=" * 60)
    print("Парсинг базы продуктов health-diet.ru")
    print("=" * 60)

    all_products = []
    categories_data = []

    for i, (cat_name, cat_path) in enumerate(CATEGORIES, 1):
        url = urljoin(BASE_URL, cat_path)
        print(f"\n{i}/{len(CATEGORIES)} {cat_name}...", end=" ", flush=True)

        products = parse_category_page(url, cat_name)
        print(f"✓ {len(products)} продуктов")

        if products:
            all_products.extend(products)
            categories_data.append({
                'id': i,
                'name': cat_name,
                'count': len(products)
            })

        # Пауза между запросами
        time.sleep(0.5)

    # Сохраняем результат
    print(f"\n\nВсего собрано: {len(all_products)} продуктов")

    result = {
        'source': 'health-diet.ru',
        'categories': categories_data,
        'products': all_products
    }

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Сохранено в {OUTPUT_FILE}")

    # Примеры
    print("\n" + "=" * 60)
    print("ПРИМЕРЫ ПРОДУКТОВ")
    print("=" * 60)

    for p in all_products[:15]:
        print(f"   {p['name'][:40]:<42} | К:{p['calories']:>5} Б:{p['protein']:>5} Ж:{p['fat']:>5} У:{p['carbs']:>5}")

    print("\n✅ Готово!")
    return result


if __name__ == "__main__":
    parse_all_products()
