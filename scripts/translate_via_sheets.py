#!/usr/bin/env python3
"""
Скрипт для перевода названий продуктов USDA на русский язык.
Использует Google Sheets с формулой =GOOGLETRANSLATE() - бесплатно!
Запуск: python scripts/translate_via_sheets.py
"""
import json
import os
import time
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Файлы
SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CREDENTIALS_FILE = os.path.join(PROJECT_DIR, 'credentials.json')
TOKEN_FILE = os.path.join(PROJECT_DIR, 'token.json')
INPUT_FILE = os.path.join(PROJECT_DIR, 'data', 'products_usda.json')
OUTPUT_FILE = os.path.join(PROJECT_DIR, 'data', 'products_usda_ru.json')
CACHE_FILE = os.path.join(PROJECT_DIR, 'data', 'translations_cache_sheets.json')

# Имя таблицы для перевода
SPREADSHEET_NAME = "USDA_Translations_Temp"
BATCH_SIZE = 500  # Строк за раз (Google Sheets limit ~5M cells)


def get_credentials():
    """Загрузка существующих credentials"""
    if not os.path.exists(TOKEN_FILE):
        raise FileNotFoundError(f"Token file not found: {TOKEN_FILE}")

    with open(TOKEN_FILE, 'r') as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data['token'],
        refresh_token=token_data['refresh_token'],
        token_uri=token_data['token_uri'],
        client_id=token_data['client_id'],
        client_secret=token_data['client_secret'],
        scopes=token_data['scopes']
    )

    # Обновляем токен если нужно
    if creds.expired:
        creds.refresh(Request())
        # Сохраняем обновлённый токен
        token_data['token'] = creds.token
        token_data['expiry'] = creds.expiry.isoformat() if creds.expiry else None
        with open(TOKEN_FILE, 'w') as f:
            json.dump(token_data, f)

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


def create_spreadsheet(sheets_service, drive_service, name: str) -> str:
    """Создание новой таблицы"""
    spreadsheet = sheets_service.spreadsheets().create(body={
        'properties': {'title': name}
    }).execute()
    return spreadsheet['spreadsheetId']


def delete_spreadsheet(drive_service, spreadsheet_id: str):
    """Удаление таблицы"""
    try:
        drive_service.files().delete(fileId=spreadsheet_id).execute()
    except Exception as e:
        print(f"   Не удалось удалить таблицу: {e}")


def find_spreadsheet(drive_service, name: str) -> str | None:
    """Поиск существующей таблицы по имени"""
    results = drive_service.files().list(
        q=f"name='{name}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
        spaces='drive',
        fields='files(id, name)'
    ).execute()
    files = results.get('files', [])
    return files[0]['id'] if files else None


def translate_batch_via_sheets(sheets_service, drive_service, texts: list[str], cache: dict) -> list[str]:
    """Перевод батча через Google Sheets"""
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

    if not to_translate:
        return results

    # Создаём временную таблицу
    spreadsheet_id = find_spreadsheet(drive_service, SPREADSHEET_NAME)
    if not spreadsheet_id:
        spreadsheet_id = create_spreadsheet(sheets_service, drive_service, SPREADSHEET_NAME)

    try:
        # Очищаем таблицу
        sheets_service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range='A:B'
        ).execute()

        # Записываем тексты в колонку A и формулы в колонку B
        values = []
        for text in to_translate:
            # Экранируем кавычки для формулы
            safe_text = text.replace('"', '""')
            values.append([text, f'=GOOGLETRANSLATE(A{len(values)+1},"en","ru")'])

        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range='A1',
            valueInputOption='USER_ENTERED',
            body={'values': values}
        ).execute()

        # Ждём вычисления формул
        time.sleep(2 + len(to_translate) * 0.02)  # ~20ms на перевод

        # Читаем переводы из колонки B
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f'B1:B{len(to_translate)}',
            valueRenderOption='FORMATTED_VALUE'
        ).execute()

        translations = result.get('values', [])

        for i, idx in enumerate(indices):
            if i < len(translations) and translations[i]:
                translated = translations[i][0]
                # Проверяем что перевод не ошибка
                if translated and not translated.startswith('#'):
                    results[idx] = translated
                    cache[to_translate[i]] = translated
                else:
                    results[idx] = to_translate[i]
                    cache[to_translate[i]] = to_translate[i]
            else:
                results[idx] = to_translate[i]
                cache[to_translate[i]] = to_translate[i]

    except Exception as e:
        print(f"\n      Ошибка: {e}")
        for i, idx in enumerate(indices):
            if results[idx] is None:
                results[idx] = to_translate[i]

    return results


def translate_products():
    """Перевод названий продуктов"""
    print("=" * 60)
    print("Перевод названий продуктов USDA на русский")
    print("(через Google Sheets GOOGLETRANSLATE - бесплатно!)")
    print("=" * 60)

    # Авторизация
    print("\n1. Авторизация в Google...")
    try:
        creds = get_credentials()
        sheets_service = build('sheets', 'v4', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)
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
        batch_size = BATCH_SIZE
        batches = (len(names_to_translate) + batch_size - 1) // batch_size
        print(f"   Батчей: {batches} (по {batch_size} названий)")

        translated_count = 0
        start_time = time.time()
        errors = 0

        for i in range(0, len(names_to_translate), batch_size):
            batch = names_to_translate[i:i+batch_size]
            batch_num = i // batch_size + 1

            print(f"\n   Батч {batch_num}/{batches} ({len(batch)} названий)...", end=" ", flush=True)

            try:
                translate_batch_via_sheets(sheets_service, drive_service, batch, cache)
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

            # Сохраняем кэш каждый батч
            save_cache(cache)
            print(f"   [Кэш сохранён: {len(cache)} переводов]")

            # Пауза между батчами
            time.sleep(1)

        print(f"\n   Переведено: {translated_count}")

        # Удаляем временную таблицу
        print("\n   Очистка временных файлов...")
        spreadsheet_id = find_spreadsheet(drive_service, SPREADSHEET_NAME)
        if spreadsheet_id:
            delete_spreadsheet(drive_service, spreadsheet_id)
            print("   ✓ Временная таблица удалена")

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
