#!/usr/bin/env python3
"""
Миграция для обновления auth_config в lsd_configs
Добавляет поля auth_type и другие параметры
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import sessionmaker
from shared.database.connection import sync_engine
from shared.database.models import LSDConfig
from shared.utils.logging import setup_logging, get_logger

logger = setup_logging()


def update_lsd_auth_configs():
    """Обновление конфигураций авторизации для существующих ЛСД"""
    
    # Новые конфигурации авторизации
    auth_configs = {
        "vkusvill": {
            "auth_type": "sms",
            "auth_method": "sms_verification",
            "phone_required": True,
            "supports_session": True,
            "session_duration": 86400,
            "authenticator_class": "VkusVillAuthenticator",
            "requires_headless": True,
            "requires_debug": True
        },
        "yandex_lavka": {
            "auth_type": "qr",
            "auth_method": "qr_code",
            "phone_required": True,
            "supports_session": True,
            "session_duration": 86400,
            "authenticator_class": "YandexLavkaAuthenticator",
            "requires_headless": True,
            "requires_debug": True
        },
        "samokat": {
            "auth_type": "sms",
            "auth_method": "sms_verification",
            "phone_required": True,
            "supports_session": True,
            "session_duration": 86400,
            "authenticator_class": "SamokatAuthenticator",
            "requires_headless": True,
            "requires_debug": False
        },
        "perekrestok": {
            "auth_type": "sms",
            "auth_method": "sms_verification",
            "phone_required": True,
            "supports_session": True,
            "session_duration": 86400,
            "authenticator_class": "PerekrestokAuthenticator",
            "requires_headless": True,
            "requires_debug": False
        }
    }
    
    # Обновляем RPA конфигурации
    rpa_configs = {
        "vkusvill": {
            "type": "sms_auth_flow",
            "sms_required": True,
            "steps": [
                {
                    "id": "open_page",
                    "action": "navigate",
                    "url": "https://vkusvill.ru",
                    "timeout": 10000
                },
                {
                    "id": "click_login",
                    "action": "click",
                    "selectors": ["//button[normalize-space(text())='Войти']"],
                    "timeout": 5000
                },
                {
                    "id": "enter_phone",
                    "action": "type",
                    "selectors": ["input[type='tel']"],
                    "value": "{phone}",
                    "wait_after": 1000
                },
                {
                    "id": "click_continue",
                    "action": "click",
                    "selectors": ["//button[normalize-space(text())='Продолжить']"],
                    "timeout": 10000
                },
                {
                    "id": "request_sms",
                    "action": "request_sms_code",
                    "requires_user_input": True,
                    "input_type": "sms_code",
                    "prompt": "Введите SMS код из сообщения",
                    "timeout": 300000
                },
                {
                    "id": "enter_sms",
                    "action": "type",
                    "selectors": ["input[name='SMS']"],
                    "value": "{user_input}",
                    "wait_after": 2000
                },
                {
                    "id": "verify_success",
                    "action": "wait_for",
                    "selectors": ["//button[normalize-space(text())='Кабинет']"],
                    "timeout": 10000,
                    "success": True
                }
            ]
        },
        "yandex_lavka": {
            "type": "qr_auth_flow",
            "sms_required": False,
            "steps": [
                {
                    "id": "open_page",
                    "action": "navigate",
                    "url": "https://passport.yandex.ru/auth?origin=lavka_web&retpath=https%3A%2F%2Flavka.yandex.ru%2F",
                    "timeout": 10000
                },
                {
                    "id": "click_qr_button",
                    "action": "click",
                    "selectors": [
                        "//span[contains(text(), 'QR-код')]//ancestor::button",
                        "//button[contains(text(), 'QR-код')]"
                    ],
                    "timeout": 5000
                },
                {
                    "id": "extract_qr",
                    "action": "extract_qr_code",
                    "timeout": 10000
                },
                {
                    "id": "wait_auth",
                    "action": "wait_for_redirect",
                    "target_domains": ["lavka.yandex.ru", "grocery"],
                    "timeout": 600000
                }
            ]
        }
    }
    
    Session = sessionmaker(bind=sync_engine)
    session = Session()
    
    try:
        # Получаем все ЛСД
        lsd_configs = session.query(LSDConfig).all()
        
        for lsd in lsd_configs:
            logger.info(f"Обновляем конфигурацию для {lsd.name}")
            
            # Обновляем auth_config
            if lsd.name in auth_configs:
                lsd.auth_config = auth_configs[lsd.name]
                logger.info(f"  ✅ Обновлен auth_config для {lsd.name}")
            else:
                # Дефолтная конфигурация для неизвестных ЛСД
                lsd.auth_config = {
                    "auth_type": "unknown",
                    "auth_method": "manual",
                    "phone_required": True,
                    "supports_session": False,
                    "authenticator_class": "BaseAuthenticator",
                    "requires_headless": True,
                    "requires_debug": False
                }
                logger.info(f"  ⚠️ Установлена дефолтная auth_config для {lsd.name}")
            
            # Обновляем rpa_config
            if lsd.name in rpa_configs:
                lsd.rpa_config = rpa_configs[lsd.name]
                logger.info(f"  ✅ Обновлен rpa_config для {lsd.name}")
            
            # Устанавливаем auth_url если его нет
            if not lsd.auth_url:
                if lsd.name == "vkusvill":
                    lsd.auth_url = "https://vkusvill.ru"
                elif lsd.name == "yandex_lavka":
                    lsd.auth_url = "https://passport.yandex.ru/auth?origin=lavka_web&retpath=https%3A%2F%2Flavka.yandex.ru%2F"
                else:
                    lsd.auth_url = lsd.base_url
                logger.info(f"  ✅ Установлен auth_url для {lsd.name}: {lsd.auth_url}")
        
        session.commit()
        logger.info("🎉 Миграция auth_config завершена успешно!")
        
        # Показываем результат
        logger.info("\n📊 Результат миграции:")
        for lsd in lsd_configs:
            auth_type = lsd.auth_config.get('auth_type', 'unknown') if lsd.auth_config else 'none'
            authenticator = lsd.auth_config.get('authenticator_class', 'unknown') if lsd.auth_config else 'none'
            logger.info(f"  • {lsd.display_name} ({lsd.name}): {auth_type} -> {authenticator}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении конфигураций: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    update_lsd_auth_configs()
