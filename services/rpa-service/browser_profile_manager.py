#!/usr/bin/env python3
"""
Менеджер браузерных профилей для RPA (Selenium)
Загружает и применяет сохраненные профили браузеров
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class BrowserProfileManager:
    """Менеджер для работы с сохраненными профилями браузеров (только Selenium)"""
    
    def __init__(self, profiles_dir: Optional[Path] = None):
        if profiles_dir is None:
            # По умолчанию ищем профили в папке рядом с этим файлом
            self.profiles_dir = Path(__file__).parent / "browser_profiles"
        else:
            self.profiles_dir = profiles_dir
            
        self.profiles_cache = {}
        # 🚀 Используем агрессивный performance-профиль по умолчанию
        self.default_profile = "performance_aggressive"
        
    def load_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """Загрузка профиля по имени"""
        try:
            # Проверяем кэш
            if profile_name in self.profiles_cache:
                return self.profiles_cache[profile_name]
            
            # Ищем файл профиля
            profile_file = self.profiles_dir / f"{profile_name}.json"
            if not profile_file.exists():
                logger.error(f"Profile file not found: {profile_file}")
                return None
                
            # Загружаем профиль
            with open(profile_file, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)
                
            # Кэшируем профиль
            self.profiles_cache[profile_name] = profile_data
            
            logger.info(f"✅ Loaded browser profile: {profile_name}")
            return profile_data
            
        except Exception as e:
            logger.error(f"❌ Error loading profile {profile_name}: {e}")
            return None
    
    def get_browser_args(self, profile_name: str = None) -> List[str]:
        """Получение аргументов браузера из профиля (для Selenium)"""
        if profile_name is None:
            profile_name = self.default_profile
            
        profile = self.load_profile(profile_name)
        if not profile:
            logger.warning(f"⚠️ Profile {profile_name} not found, using fallback args")
            return self._get_fallback_browser_args()
            
        return profile.get('browser_args', self._get_fallback_browser_args())
    
    def get_profile_from_config(self, rpa_config: dict) -> str:
        """Извлечение имени профиля из RPA конфигурации или возврат дефолтного"""
        profile_name = rpa_config.get('browser_profile')
        if profile_name:
            logger.info(f"🎭 Using custom browser profile: {profile_name}")
            return profile_name
        else:
            logger.info(f"🎭 Using default browser profile: {self.default_profile}")
            return self.default_profile
    
    def get_context_options(self, profile_name: str = None) -> Dict[str, Any]:
        """Получение опций контекста из профиля (для Selenium compatibility)"""
        if profile_name is None:
            profile_name = self.default_profile
            
        profile = self.load_profile(profile_name)
        if not profile:
            logger.warning(f"⚠️ Profile {profile_name} not found, using fallback options")
            return self._get_fallback_context_options()
            
        return profile.get('context_options', self._get_fallback_context_options())
    
    def list_profiles(self) -> List[str]:
        """Список доступных профилей"""
        try:
            profiles = []
            for profile_file in self.profiles_dir.glob("*.json"):
                profiles.append(profile_file.stem)
            return profiles
        except Exception as e:
            logger.error(f"❌ Error listing profiles: {e}")
            return []
    
    def get_profile_info(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """Получение информации о профиле"""
        profile = self.load_profile(profile_name)
        if not profile:
            return None
            
        return {
            'name': profile.get('profile_name', profile_name),
            'description': profile.get('description', 'No description'),
            'created_at': profile.get('created_at', 'Unknown'),
            'tested_sites': profile.get('tested_sites', []),
            'user_agent': profile.get('context_options', {}).get('user_agent', 'Unknown')
        }
    
    def _get_fallback_browser_args(self) -> List[str]:
        """Резервные аргументы браузера для Selenium"""
        return [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--exclude-switches=enable-automation',
            '--disable-extensions',
            '--no-first-run',
            '--no-default-browser-check'
        ]
    
    def _get_fallback_context_options(self) -> Dict[str, Any]:
        """Резервные опции контекста (для compatibility)"""
        return {
            'prefs': {
                'credentials_enable_service': False,
                'profile.password_manager_enabled': False
            },
            'locale': 'ru-RU'
        }

# Глобальный экземпляр менеджера профилей
profile_manager = BrowserProfileManager()
