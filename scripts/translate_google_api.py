#!/usr/bin/env python3
"""
Скрипт для перевода названий продуктов USDA на русский язык.
Использует Google Cloud Translation API (требует GOOGLE_API_KEY).
Запуск: python scripts/translate_google_api.py

Для получения API ключа:
1. Перейдите на https://console.cloud.google.com/
2. Создайте проект
3. Включите Cloud Translation API
4. Создайте API ключ в Credentials
5. Добавьте в .env: GOOGLE_API_KEY=ваш_ключ
"""
import json
import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

INPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'products_usda.json')
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'products_usda_ru.json')
CACHE_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'translations_cache_google.json')

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
TRANSLATE_URL = 'https://translation.googleapis.com/language/translate/v2'


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


def translate_batch_google(texts: list[str], cache: dict) -> list[str]:
    """Перевод батча через Google Translate API"""
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
            # Google API поддерживает батчи до 128 текстов
            response = requests.post(
                TRANSLATE_URL,
                params={'key': GOOGLE_API_KEY},
                json={
                    'q': to_translate,
                    'source': 'en',
                    'target': 'ru',
                    'format': 'text'
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                translations = data['data']['translations']

                for idx, trans in zip(indices, translations):
                    translated_text = trans['translatedText']
                    results[idx] = translated_text
                    # Сохраняем в кэш
                    orig_text = to_translate[indices.index(idx)]
                    cache[orig_text] = translated_text
            else:
                error = response.json().get('error', {})
                raise Exception(f"API Error {response.status_code}: {error.get('message', 'Unknown')}")

        except Exception as e:
            print(f"\n      Ошибка батча: {e}")
            # Fallback - оставляем оригиналы
            for idx, text in zip(indices, to_translate):
                results[idx] = text
                cache[text] = text

    return results


def translate_products():
    """Перевод названий продуктов"""
    print("=" * 60)
    print("Перевод названий продуктов USDA на русский")
    print("(через Google Cloud Translation API)")
    print("=" * 60)

    # Проверяем API ключ
    if not GOOGLE_API_KEY or GOOGLE_API_KEY == 'your_google_api_key':
        print("\n❌ GOOGLE_API_KEY не найден в .env!")
        print("\nДля получения ключа:")
        print("1. https://console.cloud.google.com/")
        print("2. Создайте проект → Включите Cloud Translation API")
        print("3. APIs & Services → Credentials → Create API Key")
        print("4. Добавьте в .env: GOOGLE_API_KEY=ваш_ключ")
        return

    print(f"\n   API Key: {GOOGLE_API_KEY[:10]}...")

    # Загружаем данные
    print("\n1. Загрузка продуктов...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    products = data['products']
    print(f"   Загружено {len(products)} продуктов")

    # Загружаем кэш
    cache = load_cache()
    if cache:
        # Очищаем невалидный кэш
        same_count = sum(1 for en, ru in cache.items() if en == ru)
        if same_count == len(cache) and len(cache) > 100:
            print(f"   Кэш невалидный, очищаю...")
            cache = {}
        else:
            valid_count = len(cache) - same_count
            print(f"   Кэш: {len(cache)} записей (качественных: {valid_count})")

    # Считаем сколько нужно перевести
    names_to_translate = [p['name_en'] for p in products if p['name_en'] not in cache]
    print(f"\n2. Нужно перевести: {len(names_to_translate)} названий")

    if not names_to_translate:
        print("   Все названия уже переведены!")
    else:
        batch_size = 100  # Google API поддерживает до 128
        batches = (len(names_to_translate) + batch_size - 1) // batch_size
        print(f"   Батчей: {batches}")

        translated_count = 0
        start_time = time.time()
        errors = 0

        for i in range(0, len(names_to_translate), batch_size):
            batch = names_to_translate[i:i+batch_size]
            batch_num = i // batch_size + 1

            print(f"\n   Батч {batch_num}/{batches} ({len(batch)} названий)...", end=" ", flush=True)

            try:
                translate_batch_google(batch, cache)
                translated_count += len(batch)

                elapsed = time.time() - start_time
                rate = translated_count / elapsed if elapsed > 0 else 0
                remaining = (len(names_to_translate) - translated_count) / rate if rate > 0 else 0

                print(f"✓ ({rate:.1f}/сек, ~{remaining/60:.0f} мин)")

            except Exception as e:
                errors += 1
                print(f"✗ {e}")
                if errors >= 3:
                    print("\n⚠️ Слишком много ошибок, останавливаю...")
                    break

            # Сохраняем кэш каждые 5 батчей
            if batch_num % 5 == 0:
                save_cache(cache)
                print(f"   [Кэш сохранён: {len(cache)} переводов]")

            # Пауза между батчами
            time.sleep(0.5)

        # Финальное сохранение
        save_cache(cache)
        print(f"\n   Переведено: {translated_count}")

    # Применяем переводы
    print("\n3. Применение переводов...")
    for product in products:
        name_en = product['name_en']
        if name_en in cache:
            product['name'] = cache[name_en]
        else:
            product['name'] = name_en

    # Сохраняем
    print("\n4. Сохранение результата...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"   Сохранено в {OUTPUT_FILE}")

    # Примеры
    print("\n" + "=" * 60)
    print("ПРИМЕРЫ ПЕРЕВОДОВ")
    print("=" * 60)

    examples = [p for p in products if p.get('name') != p.get('name_en')][:15]
    for p in examples:
        en = p.get('name_en', '')[:35]
        ru = p.get('name', '')[:35]
        print(f"   {en:<37} → {ru}")

    print("\n✅ Готово!")


if __name__ == "__main__":
    translate_products()
