#!/usr/bin/env python3
"""
Утилита для миграции JSON сессий (cookies + localStorage + sessionStorage)
в персистентный Chrome browser profile.

Usage:
    python migrate_json_to_profile.py <telegram_id> <lsd_name>

Example:
    python migrate_json_to_profile.py 99777490 ozon
"""

import sys
import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_json_session(telegram_id: int, lsd_name: str) -> dict:
    """Загружает JSON файл с cookies и storage данными"""
    json_path = Path(__file__).parent.parent.parent / "cookies" / lsd_name / f"{telegram_id}_{lsd_name}.json"

    if not json_path.exists():
        raise FileNotFoundError(f"❌ Session file not found: {json_path}")

    logger.info(f"📄 Loading session from: {json_path}")

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    logger.info(f"✅ Loaded {len(data.get('cookies', []))} cookies")
    logger.info(f"✅ Loaded {len(data.get('localStorage', {}))} localStorage items")
    logger.info(f"✅ Loaded {len(data.get('sessionStorage', {}))} sessionStorage items")

    return data


def create_profile_structure(telegram_id: int, lsd_name: str) -> Path:
    """Создает структуру директорий для Chrome profile"""
    profile_dir = Path(__file__).parent / "browser_profiles" / f"user_{telegram_id}_lsd_{lsd_name}"
    default_dir = profile_dir / "Default"

    # Создаем необходимые директории
    default_dir.mkdir(parents=True, exist_ok=True)
    (default_dir / "Local Storage" / "leveldb").mkdir(parents=True, exist_ok=True)
    (default_dir / "Session Storage").mkdir(parents=True, exist_ok=True)

    logger.info(f"📁 Created profile structure: {profile_dir}")

    return profile_dir


def migrate_cookies_to_sqlite(cookies: list, profile_dir: Path, base_url: str):
    """
    Записывает cookies в Chrome Cookies SQLite database

    Chrome cookies database schema:
    CREATE TABLE cookies(
        creation_utc INTEGER NOT NULL,
        host_key TEXT NOT NULL,
        top_frame_site_key TEXT NOT NULL,
        name TEXT NOT NULL,
        value TEXT NOT NULL,
        encrypted_value BLOB NOT NULL,
        path TEXT NOT NULL,
        expires_utc INTEGER NOT NULL,
        is_secure INTEGER NOT NULL,
        is_httponly INTEGER NOT NULL,
        last_access_utc INTEGER NOT NULL,
        has_expires INTEGER NOT NULL,
        is_persistent INTEGER NOT NULL,
        priority INTEGER NOT NULL,
        samesite INTEGER NOT NULL,
        source_scheme INTEGER NOT NULL,
        source_port INTEGER NOT NULL,
        last_update_utc INTEGER NOT NULL
    );
    """
    cookies_db_path = profile_dir / "Default" / "Cookies"

    logger.info(f"🍪 Writing cookies to: {cookies_db_path}")

    # Создаем новую базу данных
    conn = sqlite3.connect(str(cookies_db_path))
    cursor = conn.cursor()

    # Создаем таблицу cookies (упрощенная схема Chrome 120+)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cookies (
            creation_utc INTEGER NOT NULL,
            host_key TEXT NOT NULL,
            top_frame_site_key TEXT NOT NULL,
            name TEXT NOT NULL,
            value TEXT NOT NULL,
            encrypted_value BLOB DEFAULT '',
            path TEXT NOT NULL,
            expires_utc INTEGER NOT NULL,
            is_secure INTEGER NOT NULL DEFAULT 0,
            is_httponly INTEGER NOT NULL DEFAULT 0,
            last_access_utc INTEGER NOT NULL,
            has_expires INTEGER NOT NULL DEFAULT 1,
            is_persistent INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 1,
            samesite INTEGER NOT NULL DEFAULT -1,
            source_scheme INTEGER NOT NULL DEFAULT 0,
            source_port INTEGER NOT NULL DEFAULT -1,
            last_update_utc INTEGER NOT NULL,
            PRIMARY KEY (host_key, name, path, top_frame_site_key)
        )
    """)

    # Создаем мета-таблицу (требуется Chrome)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT NOT NULL UNIQUE PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # Записываем версию схемы
    cursor.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('version', '22')")
    cursor.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_compatible_version', '22')")

    # Конвертируем Unix timestamp в Chrome timestamp (microseconds since 1601-01-01)
    # Chrome epoch: 1601-01-01 00:00:00 UTC
    # Unix epoch: 1970-01-01 00:00:00 UTC
    # Difference: 11644473600 seconds
    CHROME_EPOCH_OFFSET = 11644473600 * 1000000  # microseconds

    def unix_to_chrome_timestamp(unix_timestamp: int) -> int:
        """Convert Unix timestamp (seconds) to Chrome timestamp (microseconds since 1601)"""
        return (unix_timestamp * 1000000) + CHROME_EPOCH_OFFSET

    now_chrome = unix_to_chrome_timestamp(int(datetime.now().timestamp()))

    # Вставляем cookies
    inserted = 0
    for cookie in cookies:
        try:
            # Извлекаем данные из Selenium cookie format
            domain = cookie.get('domain', '')
            name = cookie.get('name', '')
            value = cookie.get('value', '')
            path = cookie.get('path', '/')
            secure = 1 if cookie.get('secure', False) else 0
            httponly = 1 if cookie.get('httpOnly', False) else 0

            # Expiry может быть в секундах или отсутствовать
            expiry = cookie.get('expiry')
            if expiry:
                expires_utc = unix_to_chrome_timestamp(expiry)
                has_expires = 1
                is_persistent = 1
            else:
                # Session cookie
                expires_utc = 0
                has_expires = 0
                is_persistent = 0

            # SameSite mapping
            samesite_map = {
                'Strict': 1,
                'Lax': 2,
                'None': 3
            }
            samesite = samesite_map.get(cookie.get('sameSite'), -1)

            # Source scheme (0=unset, 1=http, 2=https)
            source_scheme = 2 if secure else 1

            cursor.execute("""
                INSERT OR REPLACE INTO cookies (
                    creation_utc, host_key, top_frame_site_key, name, value, encrypted_value,
                    path, expires_utc, is_secure, is_httponly, last_access_utc,
                    has_expires, is_persistent, priority, samesite, source_scheme,
                    source_port, last_update_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now_chrome,              # creation_utc
                domain,                  # host_key
                domain,                  # top_frame_site_key (same as host_key)
                name,                    # name
                value,                   # value
                b'',                     # encrypted_value (empty for unencrypted)
                path,                    # path
                expires_utc,             # expires_utc
                secure,                  # is_secure
                httponly,                # is_httponly
                now_chrome,              # last_access_utc
                has_expires,             # has_expires
                is_persistent,           # is_persistent
                1,                       # priority (1=medium)
                samesite,                # samesite
                source_scheme,           # source_scheme
                -1,                      # source_port (-1=unspecified)
                now_chrome               # last_update_utc
            ))

            inserted += 1

        except Exception as e:
            logger.warning(f"⚠️ Failed to insert cookie '{name}': {e}")

    conn.commit()
    conn.close()

    logger.info(f"✅ Successfully migrated {inserted}/{len(cookies)} cookies to SQLite")


def migrate_localstorage_to_leveldb(localStorage: dict, profile_dir: Path, base_url: str):
    """
    Записывает localStorage в Chrome LevelDB

    ВАЖНО: Прямая запись в LevelDB очень сложна (бинарный формат, внутренние ключи)
    Вместо этого мы создаем JSON файл, который Chrome может импортировать через:
    - chrome://settings/cookies
    - или через расширение

    Альтернатива: оставляем пустым и заполняем через JS в браузере при первом открытии
    """
    if not localStorage:
        logger.info("ℹ️ No localStorage items to migrate")
        return

    # LevelDB слишком сложен для прямой записи
    # Вместо этого сохраняем JSON для ручного импорта или JS-инъекции
    localstorage_json = profile_dir / "Default" / "localstorage_backup.json"

    with open(localstorage_json, 'w', encoding='utf-8') as f:
        json.dump({
            "origin": base_url,
            "items": localStorage
        }, f, ensure_ascii=False, indent=2)

    logger.info(f"💾 LocalStorage saved to: {localstorage_json}")
    logger.warning("⚠️ LocalStorage will need to be injected via JS on first browser open")


def migrate_session(telegram_id: int, lsd_name: str, base_url: str):
    """Основная функция миграции"""
    logger.info(f"🚀 Starting migration for user {telegram_id} on {lsd_name}")

    try:
        # 1. Загружаем JSON данные
        session_data = load_json_session(telegram_id, lsd_name)

        # 2. Создаем структуру профиля
        profile_dir = create_profile_structure(telegram_id, lsd_name)

        # 3. Мигрируем cookies в SQLite
        cookies = session_data.get('cookies', [])
        if cookies:
            migrate_cookies_to_sqlite(cookies, profile_dir, base_url)
        else:
            logger.warning("⚠️ No cookies found in JSON")

        # 4. Мигрируем localStorage (частично)
        localStorage = session_data.get('localStorage', {})
        if localStorage:
            migrate_localstorage_to_leveldb(localStorage, profile_dir, base_url)

        # 5. sessionStorage обычно не персистится между сессиями
        sessionStorage = session_data.get('sessionStorage', {})
        if sessionStorage:
            logger.info(f"ℹ️ sessionStorage ({len(sessionStorage)} items) will be lost (session-only data)")

        logger.info(f"✅ Migration completed successfully!")
        logger.info(f"📁 Profile location: {profile_dir}")
        logger.info(f"🧪 Test with: POST /browse/open {{telegram_id: {telegram_id}, lsd_name: '{lsd_name}'}}")

        return profile_dir

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python migrate_json_to_profile.py <telegram_id> <lsd_name>")
        print("Example: python migrate_json_to_profile.py 99777490 ozon")
        sys.exit(1)

    telegram_id = int(sys.argv[1])
    lsd_name = sys.argv[2]

    # Определяем base_url для LSD (можно загрузить из БД или hardcode для теста)
    lsd_urls = {
        'ozon': 'https://www.ozon.ru',
        'yandex_lavka': 'https://lavka.yandex.ru',
        'sbermarket': 'https://sbermarket.ru',
        'vkusvill': 'https://vkusvill.ru',
        'metro': 'https://online.metro-cc.ru'
    }

    base_url = lsd_urls.get(lsd_name)
    if not base_url:
        logger.error(f"❌ Unknown LSD: {lsd_name}")
        sys.exit(1)

    migrate_session(telegram_id, lsd_name, base_url)
