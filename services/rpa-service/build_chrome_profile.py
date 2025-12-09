#!/usr/bin/env python3
"""
Конвертер: cookies JSON → Chrome Browser Profile

Создаёт готовый профиль браузера Chrome из сохранённых cookies/localStorage/sessionStorage
Вместо runtime инъекции через CDP, мы заранее подготавливаем профиль на диске.

Использование:
    python3 build_chrome_profile.py --user-id 99777490 --lsd-name perek
"""

import os
import sys
import json
import sqlite3
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Базовая директория проекта
BASE_DIR = Path(__file__).parent.parent.parent
COOKIES_DIR = BASE_DIR / "cookies"
PROFILES_DIR = BASE_DIR / "services" / "rpa-service" / "browser_profiles"


def load_cookie_file(user_id: int, lsd_name: str) -> dict:
    """
    Загружает файл с куками для пользователя и ЛСД
    
    Returns:
        {
            "cookies": [...],
            "localStorage": {...},
            "sessionStorage": {...}
        }
    """
    cookie_file = COOKIES_DIR / lsd_name / f"{user_id}_{lsd_name}.json"
    
    if not cookie_file.exists():
        raise FileNotFoundError(f"Cookie file not found: {cookie_file}")
    
    with open(cookie_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"✅ Loaded cookie file: {cookie_file}")
    print(f"   Cookies: {len(data.get('cookies', []))}")
    print(f"   localStorage: {len(data.get('localStorage', {}))}")
    print(f"   sessionStorage: {len(data.get('sessionStorage', {}))}")
    
    return data


def create_chrome_profile_structure(profile_path: Path):
    """
    Создаёт базовую структуру профиля Chrome
    """
    profile_path.mkdir(parents=True, exist_ok=True)
    
    # Создаём минимальные директории
    (profile_path / "Default").mkdir(exist_ok=True)
    (profile_path / "Default" / "Local Storage").mkdir(exist_ok=True)
    (profile_path / "Default" / "Session Storage").mkdir(exist_ok=True)
    
    print(f"✅ Created profile structure at: {profile_path}")


def create_cookies_db(profile_path: Path, cookies: list, lsd_name: str):
    """
    Создаёт SQLite базу данных с куками в формате Chrome
    
    Chrome Cookies DB Schema:
    - host_key: домен (например: .perekrestok.ru)
    - name: имя куки
    - value: значение (зашифровано в реальном Chrome, но для Selenium не обязательно)
    - path: путь
    - expires_utc: timestamp в microseconds (Webkit/Chrome format)
    - is_secure: 0/1
    - is_httponly: 0/1
    - samesite: 0 (no restriction), 1 (lax), 2 (strict)
    - has_expires: 0/1
    - is_persistent: 0/1
    """
    db_path = profile_path / "Default" / "Cookies"
    
    # Удаляем старую БД если есть
    if db_path.exists():
        db_path.unlink()
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Создаём таблицу cookies (упрощённая схема для Selenium)
    cursor.execute("""
        CREATE TABLE cookies (
            creation_utc INTEGER NOT NULL,
            host_key TEXT NOT NULL,
            name TEXT NOT NULL,
            value TEXT NOT NULL,
            path TEXT NOT NULL,
            expires_utc INTEGER NOT NULL,
            is_secure INTEGER NOT NULL,
            is_httponly INTEGER NOT NULL,
            last_access_utc INTEGER NOT NULL,
            has_expires INTEGER NOT NULL DEFAULT 1,
            is_persistent INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 1,
            samesite INTEGER NOT NULL DEFAULT -1,
            source_scheme INTEGER NOT NULL DEFAULT 0,
            is_same_party INTEGER NOT NULL DEFAULT 0
        )
    """)
    
    # Создаём индекс для быстрого поиска (без UNIQUE чтобы разрешить дубликаты)
    cursor.execute("""
        CREATE INDEX idx_cookies_lookup ON cookies(host_key, name, path)
    """)
    
    # Вставляем куки
    now_utc = int(datetime.now().timestamp() * 1000000)  # Chrome timestamp format (microseconds)
    
    inserted = 0
    for cookie in cookies:
        try:
            # Подготавливаем данные
            host_key = cookie.get('domain', f'.{lsd_name}.ru')
            # НЕ добавляем точку автоматически - используем как есть
            # Chrome хранит домены БЕЗ точки для www.ozon.ru и С точкой для .ozon.ru
            
            name = cookie.get('name', '')
            value = cookie.get('value', '')
            path = cookie.get('path', '/')
            
            # Expires: конвертируем в Chrome timestamp
            if 'expirationDate' in cookie:
                expires = int(float(cookie['expirationDate']) * 1000000)
            elif 'expiry' in cookie:
                expires = int(float(cookie['expiry']) * 1000000)
            else:
                # По умолчанию: через 1 год
                expires = int((datetime.now() + timedelta(days=365)).timestamp() * 1000000)
            
            is_secure = 1 if cookie.get('secure', False) else 0
            is_httponly = 1 if cookie.get('httpOnly', False) else 0
            
            # SameSite
            samesite_map = {'Strict': 1, 'Lax': 0, 'None': -1}
            samesite = samesite_map.get(cookie.get('sameSite', 'None'), -1)
            
            # Вставляем куку
            cursor.execute("""
                INSERT INTO cookies (
                    creation_utc, host_key, name, value, path, expires_utc,
                    is_secure, is_httponly, last_access_utc, has_expires,
                    is_persistent, priority, samesite, source_scheme, is_same_party
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now_utc, host_key, name, value, path, expires,
                is_secure, is_httponly, now_utc, 1, 1, 1, samesite, 0, 0
            ))
            
            inserted += 1
            
        except Exception as e:
            print(f"⚠️ Failed to insert cookie '{cookie.get('name', 'unknown')}': {e}")
            continue
    
    conn.commit()
    conn.close()
    
    print(f"✅ Created Cookies database with {inserted}/{len(cookies)} cookies")


def create_local_storage(profile_path: Path, local_storage: dict, lsd_name: str):
    """
    Создаёт levelDB для localStorage
    
    Chrome использует LevelDB для хранения localStorage, но это сложно.
    АЛЬТЕРНАТИВА: При первом запуске браузера инъектируем localStorage через JS
    (один раз, потом браузер сам сохранит в LevelDB)
    
    Создаём JSON файл с localStorage для последующей инъекции
    """
    if not local_storage:
        print("📝 No localStorage to save")
        return
    
    ls_file = profile_path / "localStorage_inject.json"
    with open(ls_file, 'w', encoding='utf-8') as f:
        json.dump(local_storage, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Saved localStorage for injection: {len(local_storage)} items")
    print(f"   (Will be injected on first browser start)")


def create_preferences(profile_path: Path, lsd_name: str):
    """
    Создаёт файл Preferences для Chrome профиля
    """
    prefs_file = profile_path / "Default" / "Preferences"
    
    preferences = {
        "profile": {
            "name": f"User Profile - {lsd_name}",
            "managed_user_id": "",
            "content_settings": {
                "exceptions": {
                    "notifications": {}
                }
            }
        },
        "browser": {
            "check_default_browser": False,
            "show_update_promotion_info_bar": False
        },
        "download": {
            "prompt_for_download": False
        }
    }
    
    with open(prefs_file, 'w', encoding='utf-8') as f:
        json.dump(preferences, f, indent=2)
    
    print(f"✅ Created Preferences file")


def build_profile(user_id: int, lsd_name: str, output_dir: Path = None):
    """
    Главная функция: собирает готовый профиль Chrome
    """
    print(f"\n{'='*60}")
    print(f"🔨 Building Chrome Profile")
    print(f"   User ID: {user_id}")
    print(f"   LSD: {lsd_name}")
    print(f"{'='*60}\n")
    
    # 1. Загружаем данные
    data = load_cookie_file(user_id, lsd_name)
    
    # 2. Определяем путь к профилю
    if output_dir:
        profile_path = output_dir
    else:
        profile_path = PROFILES_DIR / f"user_{user_id}_lsd_{lsd_name}"
    
    # 3. Создаём структуру профиля
    create_chrome_profile_structure(profile_path)
    
    # 4. Создаём Cookies DB
    create_cookies_db(profile_path, data.get('cookies', []), lsd_name)
    
    # 5. Сохраняем localStorage для инъекции
    create_local_storage(profile_path, data.get('localStorage', {}), lsd_name)
    
    # 6. Создаём Preferences
    create_preferences(profile_path, lsd_name)
    
    print(f"\n{'='*60}")
    print(f"✅ Profile built successfully!")
    print(f"📁 Location: {profile_path}")
    print(f"\n💡 Usage:")
    print(f"   chrome_options.add_argument('--user-data-dir={profile_path}')")
    print(f"{'='*60}\n")
    
    return profile_path


def main():
    parser = argparse.ArgumentParser(
        description="Build Chrome browser profile from saved cookies/localStorage"
    )
    parser.add_argument('--user-id', type=int, required=True, help='Telegram user ID')
    parser.add_argument('--lsd-name', type=str, required=True, help='LSD name (e.g., perek, samokat)')
    parser.add_argument('--output', type=str, help='Custom output directory (optional)')
    
    args = parser.parse_args()
    
    output_dir = Path(args.output) if args.output else None
    
    try:
        profile_path = build_profile(args.user_id, args.lsd_name, output_dir)
        return 0
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
