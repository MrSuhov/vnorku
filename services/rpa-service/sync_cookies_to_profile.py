#!/usr/bin/env python3
"""
Утилита для синхронизации кук из JSON файла в персистентный профиль Chrome (SQLite DB).

Использование:
    python sync_cookies_to_profile.py <telegram_id> <lsd_name>
"""
import sys
import json
import sqlite3
import os
from pathlib import Path
from typing import Dict, List
import time

def sync_cookies_to_chrome_profile(
    telegram_id: int,
    lsd_name: str,
    json_cookies_path: str,
    chrome_profile_path: str
) -> bool:
    """
    Синхронизирует куки из JSON файла в SQLite базу персистентного профиля Chrome.

    Args:
        telegram_id: ID пользователя Telegram
        lsd_name: Название ЛСД
        json_cookies_path: Путь к JSON файлу с куками
        chrome_profile_path: Путь к персистентному профилю Chrome

    Returns:
        True если синхронизация успешна, False иначе
    """
    try:
        # 1. Читаем куки из JSON
        print(f"📖 Reading cookies from {json_cookies_path}...")
        with open(json_cookies_path, 'r') as f:
            cookie_data = json.load(f)

        cookies = cookie_data.get('cookies', [])
        print(f"✅ Found {len(cookies)} cookies in JSON")

        # 2. Подключаемся к SQLite базе Chrome
        cookies_db_path = Path(chrome_profile_path) / "Default" / "Cookies"

        if not cookies_db_path.exists():
            print(f"❌ Chrome Cookies DB not found: {cookies_db_path}")
            return False

        print(f"📂 Connecting to Chrome Cookies DB: {cookies_db_path}")

        # Важно: закрываем все процессы Chrome перед модификацией DB
        print(f"⚠️ WARNING: Chrome must be closed before syncing cookies!")

        conn = sqlite3.connect(str(cookies_db_path))
        cursor = conn.cursor()

        # 3. Подсчитываем текущие куки
        cursor.execute("SELECT COUNT(*) FROM cookies")
        before_count = cursor.fetchone()[0]
        print(f"📊 Current cookies in Chrome DB: {before_count}")

        # 4. Синхронизируем куки
        synced_count = 0
        skipped_count = 0

        for cookie in cookies:
            name = cookie.get('name')
            value = cookie.get('value')
            domain = cookie.get('domain', '')
            path = cookie.get('path', '/')
            secure = 1 if cookie.get('secure', False) else 0
            httponly = 1 if cookie.get('httpOnly', False) else 0

            # Преобразуем expiry в Chrome формат (микросекунды с 1601-01-01)
            expiry = cookie.get('expiry')
            if expiry:
                # Chrome timestamps are in microseconds since 1601-01-01
                # Unix timestamps are in seconds since 1970-01-01
                # Difference: 11644473600 seconds = 116444736000000000 microseconds
                expires_utc = (expiry * 1000000) + 11644473600000000
            else:
                # Session cookie (expires when browser closes)
                expires_utc = 0

            # Проверяем, существует ли кука
            cursor.execute("""
                SELECT COUNT(*) FROM cookies
                WHERE host_key = ? AND name = ? AND path = ?
            """, (domain, name, path))

            exists = cursor.fetchone()[0] > 0

            if exists:
                # Обновляем существующую куку
                now_utc = int(time.time() * 1000000) + 11644473600000000
                cursor.execute("""
                    UPDATE cookies
                    SET value = ?,
                        expires_utc = ?,
                        is_secure = ?,
                        is_httponly = ?,
                        last_access_utc = ?,
                        last_update_utc = ?,
                        has_expires = ?,
                        is_persistent = ?
                    WHERE host_key = ? AND name = ? AND path = ?
                """, (
                    value,
                    expires_utc,
                    secure,
                    httponly,
                    now_utc,  # last_access_utc
                    now_utc,  # last_update_utc
                    1 if expiry else 0,
                    1 if expiry else 0,
                    domain,
                    name,
                    path
                ))
                print(f"  🔄 Updated: {name} (domain: {domain})")
            else:
                # Вставляем новую куку
                now_utc = int(time.time() * 1000000) + 11644473600000000
                cursor.execute("""
                    INSERT INTO cookies (
                        creation_utc, host_key, top_frame_site_key, name, value, encrypted_value, path,
                        expires_utc, is_secure, is_httponly, last_access_utc,
                        has_expires, is_persistent, priority, samesite, source_scheme,
                        source_port, last_update_utc, source_type, has_cross_site_ancestor
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    now_utc,  # creation_utc
                    domain,  # host_key
                    domain,  # top_frame_site_key
                    name,
                    value,
                    b'',  # encrypted_value (empty for plain text cookies)
                    path,
                    expires_utc,
                    secure,
                    httponly,
                    now_utc,  # last_access_utc
                    1 if expiry else 0,  # has_expires
                    1 if expiry else 0,  # is_persistent
                    1,  # priority (1 = MEDIUM)
                    0,  # samesite (0 = NO_RESTRICTION)
                    2,  # source_scheme (2 = SCHEME_SECURE)
                    443,  # source_port
                    now_utc,  # last_update_utc
                    0,  # source_type (0 = UNKNOWN)
                    0   # has_cross_site_ancestor
                ))
                print(f"  ✅ Inserted: {name} (domain: {domain})")

            synced_count += 1

        # 5. Сохраняем изменения
        conn.commit()

        # 6. Подсчитываем финальные куки
        cursor.execute("SELECT COUNT(*) FROM cookies")
        after_count = cursor.fetchone()[0]

        conn.close()

        print(f"\n✅ Sync completed!")
        print(f"   Before: {before_count} cookies")
        print(f"   After:  {after_count} cookies")
        print(f"   Synced: {synced_count} cookies")
        print(f"   Delta:  +{after_count - before_count} cookies")

        return True

    except Exception as e:
        print(f"❌ Error syncing cookies: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python sync_cookies_to_profile.py <telegram_id> <lsd_name>")
        sys.exit(1)

    telegram_id = int(sys.argv[1])
    lsd_name = sys.argv[2]

    # Paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent  # Go up to project root
    json_cookies_path = project_root / f"cookies/{lsd_name}/{telegram_id}_{lsd_name}.json"
    chrome_profile_path = script_dir / f"browser_profiles/user_{telegram_id}_lsd_{lsd_name}"

    if not json_cookies_path.exists():
        print(f"❌ JSON cookies file not found: {json_cookies_path}")
        sys.exit(1)

    if not chrome_profile_path.exists():
        print(f"❌ Chrome profile not found: {chrome_profile_path}")
        sys.exit(1)

    print(f"🔄 Syncing cookies for user {telegram_id} @ {lsd_name}")
    print(f"   JSON: {json_cookies_path}")
    print(f"   Profile: {chrome_profile_path}")
    print()

    success = sync_cookies_to_chrome_profile(
        telegram_id=telegram_id,
        lsd_name=lsd_name,
        json_cookies_path=str(json_cookies_path),
        chrome_profile_path=str(chrome_profile_path)
    )

    sys.exit(0 if success else 1)
