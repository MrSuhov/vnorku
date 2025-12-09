#!/usr/bin/env python3
"""
Скрипт для перевода названий продуктов USDA на русский язык.
Использует бесплатный Google Translate через deep-translator.
Запуск: python scripts/translate_products_free.py
"""
import asyncio
import json
import os
import time
from pathlib import Path

# pip install deep-translator
from deep_translator import GoogleTranslator

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


def translate_batch(texts: list[str], translator: GoogleTranslator, cache: dict) -> list[str]:
    """Перевод батча текстов с использованием кэша"""
    results = []
    to_translate = []
    indices = []

    # Проверяем кэш
    for i, text in enumerate(texts):
        if text in cache:
            results.append(cache[text])
        else:
            results.append(None)
            to_translate.append(text)
            indices.append(i)

    # Переводим то, чего нет в кэше
    if to_translate:
        try:
            # Google Translate принимает список текстов
            # Но для надёжности переводим по одному с паузами
            for idx, text in zip(indices, to_translate):
                try:
                    translated = translator.translate(text)
                    results[idx] = translated
                    cache[text] = translated
                except Exception as e:
                    # Если ошибка - оставляем оригинал
                    results[idx] = text
                    print(f"      Ошибка перевода '{text[:30]}...': {e}")

                # Небольшая пауза между запросами
                time.sleep(0.1)

        except Exception as e:
            print(f"   Ошибка батча: {e}")
            # Заполняем оригиналами
            for idx in indices:
                if results[idx] is None:
                    results[idx] = texts[idx]

    return results


def translate_products():
    """Перевод названий продуктов"""
    print("=" * 60)
    print("Перевод названий продуктов USDA на русский")
    print("(через бесплатный Google Translate)")
    print("=" * 60)

    # Загружаем данные
    print("\n1. Загрузка продуктов...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    products = data['products']
    print(f"   Загружено {len(products)} продуктов")

    # Загружаем кэш
    cache = load_cache()
    print(f"   Кэш содержит {len(cache)} переводов")

    # Считаем сколько нужно перевести
    names_to_translate = [p['name_en'] for p in products if p['name_en'] not in cache]
    print(f"\n2. Нужно перевести: {len(names_to_translate)} названий")

    if not names_to_translate:
        print("   Все названия уже переведены!")
    else:
        # Инициализируем переводчик
        translator = GoogleTranslator(source='en', target='ru')

        batch_size = 50
        batches = (len(names_to_translate) + batch_size - 1) // batch_size
        print(f"   Батчей: {batches}")

        translated_count = 0
        for i in range(0, len(names_to_translate), batch_size):
            batch = names_to_translate[i:i+batch_size]
            batch_num = i // batch_size + 1

            print(f"\n   Батч {batch_num}/{batches} ({len(batch)} названий)...", end=" ", flush=True)

            translate_batch(batch, translator, cache)
            translated_count += len(batch)

            print(f"✓")

            # Сохраняем кэш каждые 10 батчей
            if batch_num % 10 == 0:
                save_cache(cache)
                print(f"   [Кэш сохранён: {len(cache)} переводов]")

            # Пауза между батчами для избежания rate limit
            time.sleep(0.5)

        # Финальное сохранение кэша
        save_cache(cache)
        print(f"\n   Переведено: {translated_count} названий")

    # Применяем переводы к продуктам
    print("\n3. Применение переводов...")
    for product in products:
        name_en = product['name_en']
        if name_en in cache:
            product['name'] = cache[name_en]
        else:
            product['name'] = name_en  # Fallback на английское

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
    for p in products[:10]:
        print(f"   {p.get('name_en', '')[:40]:<40} → {p.get('name', '')[:40]}")

    print("\n✅ Перевод завершён!")


if __name__ == "__main__":
    translate_products()
