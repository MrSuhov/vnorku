#!/usr/bin/env python3
"""
Скрипт для перевода названий продуктов USDA на русский язык.
Использует Google Cloud Translation API с OAuth авторизацией.
Запуск: python scripts/translate_google_oauth.py
"""
import json
import os
import time
import pickle
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Файлы
SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CLIENT_SECRET_FILE = os.path.join(PROJECT_DIR, 'client_secret_228586811715-8honcduq79r59nul1dhefm0m11thamol.apps.googleusercontent.com.json')
TOKEN_FILE = os.path.join(PROJECT_DIR, 'data', 'google_translate_token.pickle')
INPUT_FILE = os.path.join(PROJECT_DIR, 'data', 'products_usda.json')
OUTPUT_FILE = os.path.join(PROJECT_DIR, 'data', 'products_usda_ru.json')
CACHE_FILE = os.path.join(PROJECT_DIR, 'data', 'translations_cache_google.json')

# Scopes для Translation API
SCOPES = ['https://www.googleapis.com/auth/cloud-translation']


def get_credentials():
    """Получение OAuth credentials"""
    creds = None

    # Проверяем сохранённый токен
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    # Если нет валидного токена - авторизуемся
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Сохраняем токен
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)

    return creds


def load_cache() -> dict:
    """Загрузка кэша переводов"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    """Сохранение кэша переводов"""
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def translate_batch(service, texts: list[str], cache: dict) -> list[str]:
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
            response = service.translations().list(
                q=to_translate,
                source='en',
                target='ru',
                format='text'
            ).execute()

            translations = response.get('translations', [])

            for idx, trans in zip(indices, translations):
                translated_text = trans.get('translatedText', to_translate[indices.index(idx)])
                results[idx] = translated_text
                cache[to_translate[indices.index(idx)]] = translated_text

        except Exception as e:
            print(f"\n      Ошибка батча: {e}")
            # Fallback
            for idx, text in zip(indices, to_translate):
                results[idx] = text
                cache[text] = text

    return results


def translate_products():
    """Перевод названий продуктов"""
    print("=" * 60)
    print("Перевод названий продуктов USDA на русский")
    print("(через Google Cloud Translation API + OAuth)")
    print("=" * 60)

    # Проверяем client_secret файл
    if not os.path.exists(CLIENT_SECRET_FILE):
        print(f"\n❌ Файл не найден: {CLIENT_SECRET_FILE}")
        return

    # Авторизация
    print("\n1. Авторизация в Google...")
    try:
        creds = get_credentials()
        service = build('translate', 'v2', credentials=creds)
        print("   ✓ Авторизация успешна")
    except Exception as e:
        print(f"   ❌ Ошибка авторизации: {e}")
        return

    # Загружаем данные
    print("\n2. Загрузка продуктов...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    products = data['products']
    print(f"   Загружено {len(products)} продуктов")

    # Загружаем кэш
    cache = load_cache()
    if cache:
        same_count = sum(1 for en, ru in cache.items() if en == ru)
        if same_count == len(cache) and len(cache) > 100:
            print(f"   Кэш невалидный, очищаю...")
            cache = {}
        else:
            valid_count = len(cache) - same_count
            print(f"   Кэш: {len(cache)} записей (качественных: {valid_count})")

    # Считаем сколько нужно перевести
    names_to_translate = [p['name_en'] for p in products if p['name_en'] not in cache]
    print(f"\n3. Нужно перевести: {len(names_to_translate)} названий")

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
                translate_batch(service, batch, cache)
                translated_count += len(batch)

                elapsed = time.time() - start_time
                rate = translated_count / elapsed if elapsed > 0 else 0
                remaining = (len(names_to_translate) - translated_count) / rate if rate > 0 else 0

                print(f"✓ ({rate:.1f}/сек, ~{remaining/60:.0f} мин)")

            except Exception as e:
                errors += 1
                print(f"✗ {e}")
                if errors >= 5:
                    print("\n⚠️ Слишком много ошибок, останавливаю...")
                    break

            # Сохраняем кэш каждые 5 батчей
            if batch_num % 5 == 0:
                save_cache(cache)
                print(f"   [Кэш сохранён: {len(cache)} переводов]")

            # Пауза
            time.sleep(0.3)

        # Финальное сохранение
        save_cache(cache)
        print(f"\n   Переведено: {translated_count}")

    # Применяем переводы
    print("\n4. Применение переводов...")
    for product in products:
        name_en = product['name_en']
        if name_en in cache:
            product['name'] = cache[name_en]
        else:
            product['name'] = name_en

    # Сохраняем
    print("\n5. Сохранение результата...")
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
