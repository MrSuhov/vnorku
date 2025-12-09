#!/usr/bin/env python3
"""
Скрипт для перевода названий продуктов USDA на русский язык.
Использует бесплатную библиотеку googletrans (без API ключа).
Запуск: python scripts/translate_googletrans.py
"""
import json
import os
import time
import asyncio
from pathlib import Path

# pip install googletrans==4.0.0-rc1
from googletrans import Translator

INPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'products_usda.json')
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'products_usda_ru.json')
CACHE_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'translations_cache_gt.json')


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


def translate_batch(texts: list[str], translator: Translator, cache: dict) -> list[str]:
    """Перевод батча текстов"""
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
            # googletrans поддерживает батчи
            translations = translator.translate(to_translate, src='en', dest='ru')

            for idx, trans in zip(indices, translations):
                translated_text = trans.text if trans else to_translate[indices.index(idx)]
                results[idx] = translated_text
                cache[to_translate[indices.index(idx)]] = translated_text

        except Exception as e:
            print(f"      Ошибка батча: {e}")
            # Пробуем по одному
            for idx, text in zip(indices, to_translate):
                try:
                    trans = translator.translate(text, src='en', dest='ru')
                    results[idx] = trans.text
                    cache[text] = trans.text
                except Exception as e2:
                    results[idx] = text  # Fallback
                    cache[text] = text
                time.sleep(0.5)

    return results


def translate_products():
    """Перевод названий продуктов"""
    print("=" * 60)
    print("Перевод названий продуктов USDA на русский")
    print("(через googletrans - бесплатно, без API ключа)")
    print("=" * 60)

    # Загружаем данные
    print("\n1. Загрузка продуктов...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    products = data['products']
    print(f"   Загружено {len(products)} продуктов")

    # Загружаем кэш
    cache = load_cache()
    # Очищаем невалидный кэш
    if cache:
        same_count = sum(1 for en, ru in cache.items() if en == ru)
        if same_count == len(cache) and len(cache) > 100:
            print(f"   Кэш невалидный (все {len(cache)} записей без перевода), очищаю...")
            cache = {}
        else:
            valid_count = len(cache) - same_count
            print(f"   Кэш содержит {len(cache)} переводов (качественных: {valid_count})")

    # Считаем сколько нужно перевести
    names_to_translate = [p['name_en'] for p in products if p['name_en'] not in cache]
    print(f"\n2. Нужно перевести: {len(names_to_translate)} названий")

    if not names_to_translate:
        print("   Все названия уже переведены!")
    else:
        # Инициализируем переводчик
        translator = Translator()

        batch_size = 100  # googletrans хорошо работает с батчами
        batches = (len(names_to_translate) + batch_size - 1) // batch_size
        print(f"   Батчей: {batches}")

        translated_count = 0
        start_time = time.time()

        for i in range(0, len(names_to_translate), batch_size):
            batch = names_to_translate[i:i+batch_size]
            batch_num = i // batch_size + 1

            print(f"\n   Батч {batch_num}/{batches} ({len(batch)} названий)...", end=" ", flush=True)

            try:
                translate_batch(batch, translator, cache)
                translated_count += len(batch)

                elapsed = time.time() - start_time
                rate = translated_count / elapsed if elapsed > 0 else 0
                remaining = (len(names_to_translate) - translated_count) / rate if rate > 0 else 0

                print(f"✓ ({rate:.1f}/сек, осталось ~{remaining/60:.0f} мин)")

            except Exception as e:
                print(f"✗ Ошибка: {e}")

            # Сохраняем кэш каждые 5 батчей
            if batch_num % 5 == 0:
                save_cache(cache)
                print(f"   [Кэш сохранён: {len(cache)} переводов]")

            # Пауза между батчами
            time.sleep(1)

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

    examples = []
    for p in products:
        if p.get('name') and p.get('name') != p.get('name_en'):
            examples.append(p)
        if len(examples) >= 20:
            break

    for p in examples:
        en = p.get('name_en', '')[:35]
        ru = p.get('name', '')[:35]
        print(f"   {en:<37} → {ru}")

    print("\n✅ Перевод завершён!")


if __name__ == "__main__":
    translate_products()
