#!/usr/bin/env python3
"""
Скрипт для перевода названий продуктов USDA на русский язык.
Использует бесплатный MyMemory Translation API.
Запуск: python scripts/translate_products_mymemory.py
"""
import json
import os
import time
import urllib.request
import urllib.parse

INPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'products_usda.json')
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'products_usda_ru.json')
CACHE_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'translations_cache.json')


def load_cache() -> dict:
    """Загрузка кэша переводов"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    """Сохранение кэша переводов"""
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def translate_text(text: str) -> str:
    """Перевод текста через MyMemory API"""
    try:
        # MyMemory API бесплатный - до 10,000 слов/день
        encoded_text = urllib.parse.quote(text)
        url = f"https://api.mymemory.translated.net/get?q={encoded_text}&langpair=en|ru"

        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')

        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

        if data['responseStatus'] == 200:
            return data['responseData']['translatedText']
        else:
            return text  # Fallback на оригинал
    except Exception as e:
        return text  # Fallback на оригинал


def translate_products():
    """Перевод названий продуктов"""
    print("=" * 60)
    print("Перевод названий продуктов USDA на русский")
    print("(через бесплатный MyMemory Translation API)")
    print("=" * 60)

    # Загружаем данные
    print("\n1. Загрузка продуктов...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    products = data['products']
    print(f"   Загружено {len(products)} продуктов")

    # Загружаем кэш
    cache = load_cache()
    # Проверяем качество кэша - если все переводы = оригиналу, очищаем
    if cache:
        same_count = sum(1 for en, ru in cache.items() if en == ru)
        if same_count == len(cache):
            print(f"   Кэш невалидный (все {len(cache)} записей без перевода), очищаю...")
            cache = {}
        else:
            print(f"   Кэш содержит {len(cache)} переводов (качественных: {len(cache) - same_count})")

    # Считаем сколько нужно перевести
    names_to_translate = [p['name_en'] for p in products if p['name_en'] not in cache]
    print(f"\n2. Нужно перевести: {len(names_to_translate)} названий")

    if not names_to_translate:
        print("   Все названия уже переведены!")
    else:
        translated_count = 0
        errors = 0
        start_time = time.time()

        for i, name in enumerate(names_to_translate):
            try:
                translated = translate_text(name)
                cache[name] = translated
                translated_count += 1

                # Прогресс каждые 50 переводов
                if (i + 1) % 50 == 0:
                    elapsed = time.time() - start_time
                    rate = translated_count / elapsed if elapsed > 0 else 0
                    remaining = (len(names_to_translate) - i - 1) / rate if rate > 0 else 0
                    print(f"   Переведено: {i + 1}/{len(names_to_translate)} "
                          f"({rate:.1f}/сек, осталось ~{remaining/60:.0f} мин)")

                    # Сохраняем кэш каждые 500 переводов
                    if (i + 1) % 500 == 0:
                        save_cache(cache)
                        print(f"   [Кэш сохранён: {len(cache)} переводов]")

                # Пауза между запросами
                time.sleep(0.3)  # 3 запроса/сек для безопасности

            except Exception as e:
                errors += 1
                cache[name] = name  # Fallback
                if errors <= 5:
                    print(f"   Ошибка: {e}")

        # Финальное сохранение кэша
        save_cache(cache)
        print(f"\n   Переведено: {translated_count} названий")
        if errors:
            print(f"   Ошибок: {errors}")

    # Применяем переводы к продуктам
    print("\n3. Применение переводов...")
    for product in products:
        name_en = product['name_en']
        if name_en in cache:
            product['name'] = cache[name_en]
        else:
            product['name'] = name_en

    # Сохраняем результат
    print("\n4. Сохранение результата...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    file_size = os.path.getsize(OUTPUT_FILE) / 1024 / 1024
    print(f"   Сохранено в {OUTPUT_FILE}")
    print(f"   Размер файла: {file_size:.1f} MB")

    # Примеры переводов
    print("\n" + "=" * 60)
    print("ПРИМЕРЫ ПЕРЕВОДОВ")
    print("=" * 60)

    # Показать хорошие переводы (где отличается от оригинала)
    examples = []
    for p in products:
        if p.get('name') != p.get('name_en'):
            examples.append(p)
        if len(examples) >= 15:
            break

    for p in examples:
        en = p.get('name_en', '')[:35]
        ru = p.get('name', '')[:35]
        print(f"   {en:<37} → {ru}")

    print("\n✅ Перевод завершён!")


if __name__ == "__main__":
    translate_products()
