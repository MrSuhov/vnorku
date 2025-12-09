#!/usr/bin/env python3
"""
Утилита для инъекции cookies в SQLite базу Chrome профиля
Записывает cookies ДО запуска браузера, чтобы Chrome загрузил их при старте
"""

import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def unix_to_chrome_timestamp(unix_timestamp: int) -> int:
    """
    Конвертирует Unix timestamp в Chrome/WebKit timestamp
    
    Chrome использует microseconds с 1601-01-01 (Windows epoch)
    Unix использует seconds с 1970-01-01
    
    Args:
        unix_timestamp: Unix timestamp в секундах
        
    Returns:
        Chrome timestamp в microseconds
    """
    # Разница между Windows epoch (1601) и Unix epoch (1970) в секундах
    EPOCH_DELTA = 11644473600
    
    # Конвертируем в microseconds и добавляем разницу эпох
    chrome_timestamp = (unix_timestamp + EPOCH_DELTA) * 1_000_000
    
    return chrome_timestamp


def sameSite_to_int(same_site: str) -> int:
    """
    Конвертирует sameSite string в int для SQLite
    
    Args:
        same_site: 'None', 'Lax', 'Strict'
        
    Returns:
        0 = None, 1 = Lax, 2 = Strict
    """
    mapping = {
        'None': 0,
        'Lax': 1,
        'Strict': 2
    }
    return mapping.get(same_site, 0)


def get_domains_for_cleanup(base_url: str) -> List[str]:
    """
    Извлекает домены для очистки cookies из base_url
    
    Args:
        base_url: URL вида https://www.ozon.ru/category/...
        
    Returns:
        Список доменов: ['www.ozon.ru', '.ozon.ru']
    """
    # Извлекаем домен из URL
    if '//' in base_url:
        domain = base_url.split('//')[1].split('/')[0]
    else:
        domain = base_url.split('/')[0]
    
    # Генерируем оба варианта
    domains = [domain]  # www.ozon.ru
    
    # Добавляем вариант с точкой в начале
    if not domain.startswith('.'):
        # Если есть www - создаём версию без www с точкой
        if domain.startswith('www.'):
            root_domain = '.' + domain[4:]  # .ozon.ru
            domains.append(root_domain)
        else:
            # Иначе просто добавляем точку
            domains.append('.' + domain)
    
    return domains


def inject_cookies_to_sqlite(
    profile_dir: Path,
    cookies: List[Dict[str, Any]],
    base_url: str
) -> int:
    """
    Инъектирует cookies в SQLite базу Chrome профиля
    
    Args:
        profile_dir: Путь к директории профиля Chrome
        cookies: Список cookies из JSON (формат get_user_cookies)
        base_url: Base URL ЛСД (для определения доменов)
        
    Returns:
        Количество успешно записанных cookies
    """
    cookies_db_path = profile_dir / "Default" / "Cookies"
    
    if not cookies_db_path.exists():
        logger.error(f"❌ Cookies database not found: {cookies_db_path}")
        return 0
    
    logger.info(f"📂 Opening SQLite cookies database: {cookies_db_path}")

    try:
        # Открываем SQLite базу
        conn = sqlite3.connect(str(cookies_db_path))
        cursor = conn.cursor()

        # Проверяем существование таблицы cookies
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cookies'")
        table_exists = cursor.fetchone()

        if not table_exists:
            logger.warning("⚠️ Cookies table does not exist, creating schema...")
            # Создаём схему таблицы cookies как в Chrome
            cursor.execute("""
                CREATE TABLE cookies (
                    creation_utc INTEGER NOT NULL,
                    host_key TEXT NOT NULL,
                    top_frame_site_key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    value TEXT NOT NULL,
                    encrypted_value BLOB DEFAULT '',
                    path TEXT NOT NULL,
                    expires_utc INTEGER NOT NULL,
                    is_secure INTEGER NOT NULL,
                    is_httponly INTEGER NOT NULL,
                    last_access_utc INTEGER NOT NULL,
                    has_expires INTEGER NOT NULL DEFAULT 1,
                    is_persistent INTEGER NOT NULL DEFAULT 1,
                    priority INTEGER NOT NULL DEFAULT 1,
                    samesite INTEGER NOT NULL DEFAULT 0,
                    source_scheme INTEGER NOT NULL DEFAULT 2,
                    source_port INTEGER NOT NULL DEFAULT 443,
                    last_update_utc INTEGER NOT NULL DEFAULT 0,
                    source_type INTEGER NOT NULL DEFAULT 0,
                    has_cross_site_ancestor INTEGER NOT NULL DEFAULT 0,
                    UNIQUE (host_key, top_frame_site_key, name, path)
                )
            """)

            # Создаём индексы для performance
            cursor.execute("CREATE INDEX domain ON cookies(host_key)")
            cursor.execute("CREATE INDEX is_transient ON cookies(is_persistent)")

            conn.commit()
            logger.info("✅ Cookies table schema created successfully")

        # Получаем домены для очистки
        domains_to_clean = get_domains_for_cleanup(base_url)
        logger.info(f"🧹 Cleaning old cookies for domains: {domains_to_clean}")
        
        # Удаляем старые cookies для этих доменов
        for domain in domains_to_clean:
            cursor.execute(
                "DELETE FROM cookies WHERE host_key = ?",
                (domain,)
            )
            deleted = cursor.rowcount
            logger.info(f"   Deleted {deleted} cookies for domain '{domain}'")
        
        # Коммитим удаление
        conn.commit()
        
        # Текущее время для creation_utc и last_access_utc
        current_time = unix_to_chrome_timestamp(int(datetime.now().timestamp()))
        
        # Вставляем новые cookies
        injected_count = 0
        
        for cookie in cookies:
            try:
                # Обязательные поля
                name = cookie.get('name')
                value = cookie.get('value', '')
                
                # КРИТИЧНО: Нормализуем domain
                # Если domain = "www.ozon.ru" -> конвертируем в ".ozon.ru"
                # Это гарантирует что cookie работает для всех субдоменов
                # и НЕ перезаписывается сервером
                raw_domain = cookie.get('domain', domains_to_clean[0])
                if raw_domain.startswith('www.'):
                    # Конвертируем www.example.com -> .example.com
                    domain = '.' + raw_domain[4:]
                    logger.debug(f"   🔄 Normalized domain: {raw_domain} -> {domain}")
                elif not raw_domain.startswith('.'):
                    # Добавляем точку если её нет
                    domain = '.' + raw_domain
                    logger.debug(f"   🔄 Normalized domain: {raw_domain} -> {domain}")
                else:
                    domain = raw_domain
                
                path = cookie.get('path', '/')
                
                # Конвертируем expiry
                expiry = cookie.get('expiry') or cookie.get('expirationDate')
                if expiry:
                    expires_utc = unix_to_chrome_timestamp(int(expiry))
                else:
                    # Если нет expiry - делаем долгоживущую куку (10 лет)
                    expires_utc = current_time + (10 * 365 * 24 * 60 * 60 * 1_000_000)
                
                # Boolean флаги
                is_secure = 1 if cookie.get('secure', False) else 0
                is_httponly = 1 if cookie.get('httpOnly', False) else 0
                
                # SameSite
                same_site_str = cookie.get('sameSite', 'Lax')
                samesite = sameSite_to_int(same_site_str)
                
                # КРИТИЧНО: Логируем для __Secure-user-id ПЕРЕД INSERT
                if name == '__Secure-user-id':
                    logger.info(f"   🔍 BEFORE INSERT: name={name}, value='{value}' (len={len(value)}), domain={domain}")
                
                # Вставляем cookie
                cursor.execute("""
                    INSERT INTO cookies (
                        creation_utc,
                        host_key,
                        top_frame_site_key,
                        name,
                        value,
                        encrypted_value,
                        path,
                        expires_utc,
                        is_secure,
                        is_httponly,
                        last_access_utc,
                        has_expires,
                        is_persistent,
                        priority,
                        samesite,
                        source_scheme,
                        source_port,
                        last_update_utc,
                        source_type,
                        has_cross_site_ancestor
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    current_time,           # creation_utc
                    domain,                 # host_key
                    domain,                 # top_frame_site_key
                    name,                   # name
                    value,                  # value
                    b'',                    # encrypted_value (пусто - Chrome использует value)
                    path,                   # path
                    expires_utc,            # expires_utc
                    is_secure,              # is_secure
                    is_httponly,            # is_httponly
                    current_time,           # last_access_utc
                    1,                      # has_expires
                    1,                      # is_persistent
                    1,                      # priority (Medium)
                    samesite,               # samesite
                    2,                      # source_scheme (2 = https)
                    443,                    # source_port
                    current_time,           # last_update_utc
                    0,                      # source_type (0 = unknown)
                    0                       # has_cross_site_ancestor (0 = false)
                ))
                
                injected_count += 1
                
                # Детальное логирование для __Secure-user-id
                if name == '__Secure-user-id':
                    logger.info(f"   🔑 INJECTED __Secure-user-id: domain={domain}, value={value}")
                    
                    # КРИТИЧНО: Проверяем что записалось в SQLite
                    cursor.execute(
                        "SELECT value FROM cookies WHERE name = ? AND host_key = ? ORDER BY creation_utc DESC LIMIT 1",
                        (name, domain)
                    )
                    result = cursor.fetchone()
                    if result:
                        actual_value = result[0]
                        logger.info(f"   ✅ VERIFIED in SQLite: value='{actual_value}' (len={len(actual_value) if actual_value else 0})")
                        if actual_value != value:
                            logger.error(f"   ❌ VALUE MISMATCH! Expected '{value}', got '{actual_value}'")
                    else:
                        logger.error(f"   ❌ Cookie NOT FOUND in SQLite after INSERT!")
                else:
                    logger.debug(f"   ✅ Injected cookie: {name} (domain={domain})")
                
            except Exception as cookie_error:
                logger.warning(f"   ⚠️ Failed to inject cookie {cookie.get('name')}: {cookie_error}")
                continue
        
        # Коммитим вставку
        conn.commit()
        
        logger.info(f"✅ Successfully injected {injected_count}/{len(cookies)} cookies into SQLite")
        
        return injected_count
        
    except Exception as e:
        logger.error(f"❌ Error injecting cookies to SQLite: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0
        
    finally:
        if 'conn' in locals():
            conn.close()
            logger.debug(f"📪 Closed SQLite connection")
