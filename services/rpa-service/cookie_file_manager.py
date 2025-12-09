"""
Cookie File Manager - Менеджер для работы с cookies в файловой системе
"""

import json
import os
import tempfile
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
import time

logger = logging.getLogger(__name__)

class CookieFileManager:
    """Менеджер для работы с cookies в файловой системе"""
    
    def __init__(self, base_dir: str = "/Users/ss/GenAI/korzinka/cookies"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        # НЕ логируем инициализацию - вызывает дублирование при reload
    
    def _get_lsd_dir(self, lsd_name: str) -> Path:
        """Получить директорию для ЛСД"""
        lsd_dir = self.base_dir / lsd_name
        lsd_dir.mkdir(parents=True, exist_ok=True)
        return lsd_dir
    
    def _get_filepath(self, telegram_id: int, lsd_name: str) -> Path:
        """Получить путь к файлу cookie"""
        lsd_dir = self._get_lsd_dir(lsd_name)
        return lsd_dir / f"{telegram_id}_{lsd_name}.json"
    
    def _get_relative_path(self, telegram_id: int, lsd_name: str) -> str:
        """Получить относительный путь для хранения в БД"""
        return f"cookies/{lsd_name}/{telegram_id}_{lsd_name}.json"
    
    def clean_cookies(self, cookies: List[Dict[str, Any]], lsd_name: str = None) -> Tuple[List[Dict[str, Any]], int]:
        """
        Очистка кук от протухших и конфликтующих
        
        Удаляет:
        - Истекшие куки (expiry < current_time)
        - Гостевые куки (guest=true, __Secure-user-id=0)
        - Конфликтующие куки для широкого домена (.domain.com) если есть специфичные (www.domain.com)
        
        Args:
            cookies: Список кук для очистки
            lsd_name: Имя ЛСД (для специфичной логики)
            
        Returns:
            Tuple[List[Dict], int]: (очищенные куки, количество удалённых)
        """
        if not cookies:
            return [], 0
        
        current_time = time.time()
        cleaned_cookies = []
        removed_count = 0
        removed_reasons = []
        
        # Собираем информацию о доменах и авторизации
        has_auth_specific_domain = False  # Есть ли авторизованные куки для www.domain
        auth_cookie_names = {'__Secure-access-token', '__Secure-refresh-token', '__Secure-user-id'}
        
        # Первый проход: проверяем есть ли авторизованные куки для специфичного домена
        for cookie in cookies:
            domain = cookie.get('domain', '')
            name = cookie.get('name', '')
            value = str(cookie.get('value', ''))
            
            # Проверяем авторизованные куки на www.domain (не .domain)
            if not domain.startswith('.') and name in auth_cookie_names:
                if name == '__Secure-user-id' and value != '0':
                    has_auth_specific_domain = True
                    break
        
        # Второй проход: фильтруем куки
        for cookie in cookies:
            domain = cookie.get('domain', '')
            name = cookie.get('name', '')
            value = str(cookie.get('value', ''))
            expiry = cookie.get('expiry') or cookie.get('expirationDate')
            
            # 1. Удаляем истекшие куки
            if expiry and float(expiry) < current_time:
                removed_count += 1
                removed_reasons.append(f"{name} (expired: {datetime.fromtimestamp(float(expiry)).strftime('%Y-%m-%d %H:%M')})")
                continue
            
            # 2. Удаляем явные гостевые маркеры
            if name == 'guest' and value == 'true':
                removed_count += 1
                removed_reasons.append(f"{name}=true (guest marker)")
                continue
            
            # 3. Удаляем гостевые токены (__Secure-user-id=0)
            if name == '__Secure-user-id' and value == '0':
                removed_count += 1
                removed_reasons.append(f"{name}=0 on {domain} (guest token)")
                continue
            
            # 4. Если есть авторизованные куки на www.domain, удаляем конфликтующие с .domain
            if has_auth_specific_domain and domain.startswith('.'):
                if name in auth_cookie_names:
                    # Удаляем токены с широкого домена, так как есть специфичные авторизованные
                    removed_count += 1
                    removed_reasons.append(f"{name} on {domain} (conflict with www.domain auth)")
                    continue
            
            # Кука прошла все проверки
            cleaned_cookies.append(cookie)
        
        # Логирование результатов
        if removed_count > 0:
            logger.info(f"🧹 Cleaned {removed_count} cookies from {len(cookies)}:")
            for i, reason in enumerate(removed_reasons[:5], 1):  # Первые 5
                logger.info(f"   {i}. {reason}")
            if len(removed_reasons) > 5:
                logger.info(f"   ... and {len(removed_reasons) - 5} more")
        else:
            logger.info(f"✅ All {len(cookies)} cookies are clean (no expired or conflicting)")
        
        return cleaned_cookies, removed_count
    
    async def save_cookies(
        self, 
        telegram_id: int,
        lsd_name: str,
        lsd_config_id: int,
        cookies: List[Dict[str, Any]],
        local_storage: Optional[Dict[str, str]] = None,
        session_storage: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Атомарная запись cookies в файл
        
        Args:
            telegram_id: ID пользователя в Telegram
            lsd_name: Имя ЛСД (ozon, samokat, etc)
            lsd_config_id: ID конфигурации ЛСД
            cookies: Список cookies
            metadata: Дополнительные метаданные сессии
            
        Returns:
            Tuple[bool, Optional[str]]: (success, relative_file_path)
        """
        filepath = self._get_filepath(telegram_id, lsd_name)
        relative_path = self._get_relative_path(telegram_id, lsd_name)
        
        # ОЧИСТКА: удаляем протухшие и конфликтующие куки перед сохранением
        cleaned_cookies, removed_count = self.clean_cookies(cookies, lsd_name)
        if removed_count > 0:
            logger.info(f"🧹 Removed {removed_count} problematic cookies before saving")
        
        # Проверяем существующий файл для сохранения created_at
        created_at = datetime.now().isoformat()
        if filepath.exists():
            try:
                with open(filepath, 'r') as f:
                    existing_data = json.load(f)
                    created_at = existing_data.get('created_at', created_at)
            except Exception as e:
                logger.warning(f"⚠️ Failed to read existing file for created_at: {e}")
        
        data = {
            "telegram_id": telegram_id,
            "lsd_config_id": lsd_config_id,
            "lsd_name": lsd_name,
            "cookies": cleaned_cookies,  # Используем очищенные куки
            "localStorage": local_storage or {},
            "sessionStorage": session_storage or {},
            "created_at": created_at,
            "updated_at": datetime.now().isoformat(),
            "session_metadata": metadata or {}
        }
        
        try:
            # 1. Записываем во временный файл в той же директории
            lsd_dir = self._get_lsd_dir(lsd_name)
            with tempfile.NamedTemporaryFile(
                mode='w',
                dir=lsd_dir,
                delete=False,
                suffix='.tmp',
                prefix=f'{telegram_id}_'
            ) as tmp_file:
                json.dump(data, tmp_file, indent=2, ensure_ascii=False)
                tmp_path = tmp_file.name
            
            # 2. Атомарно переименовываем (replace гарантирует атомарность)
            os.replace(tmp_path, filepath)
            
            ls_count = len(local_storage) if local_storage else 0
            ss_count = len(session_storage) if session_storage else 0
            logger.info(f"✅ Saved {len(cleaned_cookies)} cookies + {ls_count} localStorage + {ss_count} sessionStorage items to {relative_path}")
            return True, relative_path
            
        except Exception as e:
            logger.error(f"❌ Failed to save cookies to {filepath}: {e}")
            # Удаляем временный файл если он остался
            if 'tmp_path' in locals() and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except:
                    pass
            return False, None
    
    async def load_cookies(
        self,
        telegram_id: int,
        lsd_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Загрузка cookies из файла
        
        Args:
            telegram_id: ID пользователя в Telegram
            lsd_name: Имя ЛСД
            
        Returns:
            Словарь с данными сессии или None если файл не найден
        """
        filepath = self._get_filepath(telegram_id, lsd_name)
        
        if not filepath.exists():
            logger.warning(f"⚠️ Cookie file not found: {self._get_relative_path(telegram_id, lsd_name)}")
            return None
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # ОЧИСТКА: фильтруем куки при загрузке
            original_cookies = data.get('cookies', [])
            cleaned_cookies, removed_count = self.clean_cookies(original_cookies, lsd_name)
            
            if removed_count > 0:
                logger.warning(f"⚠️ Removed {removed_count} expired/conflicting cookies during load")
                # Обновляем данные с очищенными куками
                data['cookies'] = cleaned_cookies
                # Сохраняем обратно в файл (чтобы не загружать их снова в следующий раз)
                try:
                    with open(filepath, 'w') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    logger.info(f"💾 Updated cookie file with cleaned cookies")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to update cookie file: {e}")
            
            cookies_count = len(cleaned_cookies)
            local_storage_count = len(data.get('localStorage', {}))
            session_storage_count = len(data.get('sessionStorage', {}))
            logger.info(f"✅ Loaded {cookies_count} cookies + {local_storage_count} localStorage + {session_storage_count} sessionStorage items from {self._get_relative_path(telegram_id, lsd_name)}")
            
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in {filepath}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to load cookies from {filepath}: {e}")
            return None
    
    async def delete_cookies(
        self,
        telegram_id: int,
        lsd_name: str
    ) -> bool:
        """
        Удаление файла cookies для конкретного ЛСД
        
        Args:
            telegram_id: ID пользователя в Telegram
            lsd_name: Имя ЛСД
            
        Returns:
            True если успешно удалено
        """
        filepath = self._get_filepath(telegram_id, lsd_name)
        
        if not filepath.exists():
            logger.warning(f"⚠️ Cookie file not found for deletion: {self._get_relative_path(telegram_id, lsd_name)}")
            return True  # Уже удалено
        
        try:
            filepath.unlink()
            logger.info(f"🗑️ Deleted cookie file: {self._get_relative_path(telegram_id, lsd_name)}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete cookie file {filepath}: {e}")
            return False
    
    async def delete_user_all_cookies(self, telegram_id: int) -> int:
        """
        Удаление всех cookie файлов пользователя
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            Количество удалённых файлов
        """
        deleted_count = 0
        
        logger.info(f"🗑️ Deleting all cookies for user {telegram_id}...")
        
        for lsd_dir in self.base_dir.iterdir():
            if not lsd_dir.is_dir():
                continue
            
            lsd_name = lsd_dir.name
            filepath = self._get_filepath(telegram_id, lsd_name)
            
            if filepath.exists():
                try:
                    filepath.unlink()
                    deleted_count += 1
                    logger.info(f"   🗑️ Deleted: {self._get_relative_path(telegram_id, lsd_name)}")
                except Exception as e:
                    logger.error(f"   ❌ Failed to delete {filepath}: {e}")
        
        logger.info(f"✅ Deleted {deleted_count} cookie files for user {telegram_id}")
        return deleted_count
    
    async def delete_lsd_all_cookies(self, lsd_name: str) -> int:
        """
        Удаление всей папки ЛСД со всеми cookies
        
        Args:
            lsd_name: Имя ЛСД
            
        Returns:
            Количество удалённых файлов
        """
        lsd_dir = self.base_dir / lsd_name
        
        if not lsd_dir.exists():
            logger.warning(f"⚠️ LSD directory not found: {lsd_name}")
            return 0
        
        deleted_count = 0
        
        logger.info(f"🗑️ Deleting all cookies for LSD '{lsd_name}'...")
        
        try:
            for cookie_file in lsd_dir.glob("*_*.json"):
                try:
                    cookie_file.unlink()
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"   ❌ Failed to delete {cookie_file}: {e}")
            
            # Удаляем саму папку если она пустая
            if not any(lsd_dir.iterdir()):
                lsd_dir.rmdir()
                logger.info(f"   🗑️ Removed empty directory: {lsd_name}")
            
            logger.info(f"✅ Deleted {deleted_count} cookie files for LSD '{lsd_name}'")
            return deleted_count
            
        except Exception as e:
            logger.error(f"❌ Failed to delete LSD cookies: {e}")
            return deleted_count
    
    async def list_user_cookies(self, telegram_id: int) -> List[str]:
        """
        Получить список всех ЛСД, для которых есть cookies у пользователя
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            Список имён ЛСД
        """
        lsd_names = []
        
        for lsd_dir in self.base_dir.iterdir():
            if not lsd_dir.is_dir():
                continue
            
            lsd_name = lsd_dir.name
            filepath = self._get_filepath(telegram_id, lsd_name)
            
            if filepath.exists():
                lsd_names.append(lsd_name)
        
        return lsd_names
    
    def file_exists(self, telegram_id: int, lsd_name: str) -> bool:
        """
        Проверка существования файла cookie
        
        Args:
            telegram_id: ID пользователя в Telegram
            lsd_name: Имя ЛСД
            
        Returns:
            True если файл существует
        """
        filepath = self._get_filepath(telegram_id, lsd_name)
        return filepath.exists()

# Глобальный экземпляр (ленивая инициализация)
_cookie_manager_instance = None

def get_cookie_manager() -> CookieFileManager:
    """Получение глобального экземпляра CookieFileManager"""
    global _cookie_manager_instance
    if _cookie_manager_instance is None:
        _cookie_manager_instance = CookieFileManager()
    return _cookie_manager_instance

# Для обратной совместимости с существующим кодом
cookie_manager = get_cookie_manager()
