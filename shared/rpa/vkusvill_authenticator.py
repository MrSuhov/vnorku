"""
VkusVill RPA аутентификатор с поддержкой SMS верификации
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .universal_rpa_engine import UniversalRPAEngine
from .lsd_authenticator import LSDAuthenticator

logger = logging.getLogger(__name__)


class VkusVillAuthenticator(LSDAuthenticator):
    """RPA авторизация в ВкусВилл через SMS"""
    
    def __init__(self, lsd_config: Dict[str, Any], headless: bool = True, debug: bool = False):
        super().__init__(lsd_config)
        self.headless = headless
        self.debug = debug
        self.rpa_engine = UniversalRPAEngine(headless=headless, debug=debug)
        self.current_session = None
        self.base_url = lsd_config.get("base_url", "https://vkusvill.ru")  # Используем base_url напрямую
        
    async def authenticate(self, phone: str, **kwargs) -> Dict[str, Any]:
        """Авторизация в ВкусВилл через SMS"""
        try:
            logger.info(f"Starting VkusVill authentication for phone {phone}")
            
            # Получаем конфигурацию RPA из lsd_config
            rpa_config = self.lsd_config.get("rpa_config")
            if not rpa_config:
                return await self._mock_authenticate(phone)
                
            # Проверяем mock режим
            if rpa_config.get("mock_mode", False) or rpa_config.get("type") == "mock_sms_flow":
                return await self._mock_authenticate(phone)
                
            # Запускаем RPA сессию
            session = await self.rpa_engine.start_session(rpa_config)
            self.current_session = session
            
            # Выполняем все шаги последовательно
            credentials = {'phone': phone}
            
            steps = rpa_config.get('steps', [])
            for step in steps:
                logger.info(f"Executing step: {step['id']}")
                
                result = await self.rpa_engine.execute_step(session, step, credentials)
                
                # Проверяем, нужен ли пользовательский ввод
                if result.get('status') == 'waiting_for_user_input':
                    logger.info(f"User input required at step {step['id']}")
                    return result  # Возвращаем как есть
                    
                # Проверяем на ошибку
                if result.get('status') == 'error':
                    raise Exception(f"Step {step['id']} failed: {result.get('error')}")
                    
                # Проверяем условие успеха
                if step.get('success'):
                    logger.info(f"Authentication completed successfully at step {step['id']}")
                    return {
                        "status": "completed",
                        "success": True,
                        "message": "Авторизация завершена успешно"
                    }
            
            # Если дошли до конца без явного успеха
            logger.warning("Не найдено явное условие успеха")
            return {
                "status": "completed",
                "success": True,
                "message": "Все шаги выполнены"
            }
            
        except Exception as e:
            logger.error(f"Error during VkusVill authentication: {e}")
            if self.current_session:
                await self.rpa_engine.cleanup_session(self.current_session.id)
            return {"success": False, "error": str(e)}
            
    async def continue_sms_auth(self, session_id: str, sms_code: str) -> Dict[str, Any]:
        """Продолжение авторизации с SMS кодом"""
        try:
            # Используем новый метод RPA движка
            result = await self.rpa_engine.continue_with_user_input(session_id, sms_code)
            return result
            
        except Exception as e:
            logger.error(f"Error continuing SMS auth: {e}")
            return {"success": False, "error": str(e)}
            
    async def _mock_authenticate(self, phone: str) -> Dict[str, Any]:
        """Mock авторизация для тестирования"""
        logger.info("Using mock VkusVill authentication")
        await asyncio.sleep(2)
        
        return {
            "success": True,
            "auth_type": "sms_verification_mock",
            "session_id": f"mock_session_{int(datetime.now().timestamp())}",
            "message": "Mock: SMS код отправлен на ваш телефон (demo режим)",
            "next_step": "enter_sms"
        }
        
    async def _save_cookies(self, session, user_id: int) -> bool:
        """Сохранение куки в базу данных"""
        try:
            if not session.context:
                return False
                
            cookies = await session.context.cookies()
            
            # Преобразуем в формат для API
            cookies_dict = {}
            for cookie in cookies:
                cookies_dict[cookie["name"]] = {
                    "value": cookie["value"],
                    "domain": cookie["domain"],
                    "path": cookie.get("path", "/"),
                    "secure": cookie.get("secure", False),
                    "httpOnly": cookie.get("httpOnly", False),
                    "sameSite": cookie.get("sameSite", "Lax")
                }
                
            # Сохраняем через user-service API
            return await self._call_user_service_save_cookies(user_id, cookies_dict)
            
        except Exception as e:
            logger.error(f"Error saving cookies: {e}")
            return False
            
    async def _call_user_service_save_cookies(self, user_id: int, cookies_dict: dict) -> bool:
        """Вызов user-service API для сохранения куки"""
        try:
            import httpx
            
            user_service_url = "http://localhost:8002"
            
            cookies_data = {
                "lsd_name": self.lsd_name,
                "cookies": cookies_dict,
                "timestamp": int(datetime.now().timestamp())
            }
            
            logger.info(f"Saving VkusVill cookies for user {user_id}")
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{user_service_url}/users/{user_id}/cookies",
                    json=cookies_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        logger.info("VkusVill cookies saved successfully")
                        return True
                        
                logger.error(f"Failed to save VkusVill cookies: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error calling user-service to save cookies: {e}")
            return False
            
    async def get_session_data(self) -> Dict[str, Any]:
        """Получение данных сессии"""
        if not self.current_session or not self.current_session.context:
            return {}
            
        try:
            cookies = await self.current_session.context.cookies()
            return {
                "cookies": {cookie['name']: cookie['value'] for cookie in cookies},
                "timestamp": datetime.utcnow().isoformat(),
                "lsd_name": self.lsd_name
            }
        except Exception as e:
            logger.error(f"Error getting session data: {e}")
            return {}
            
    async def cleanup(self):
        """Очистка ресурсов"""
        if self.current_session:
            await self.rpa_engine.cleanup_session(self.current_session.id)
            self.current_session = None
            
    async def complete_authentication(self, user_id: int, telegram_id: Optional[int] = None) -> Dict[str, Any]:
        """Завершение авторизации - ожидание, сохранение куки, закрытие браузера"""
        try:
            logger.info(f"🔄 Starting VkusVill authentication completion for user {user_id}...")
            
            # Получаем RPA конфигурацию
            rpa_config = self.lsd_config.get("rpa_config")
            
            # Мок режим
            if not rpa_config or rpa_config.get("mock_mode", False) or rpa_config.get("type") == "mock_sms_flow":
                logger.info("🧘 Mock mode: simulating completion with mock cookies save")
                
                # Сохраняем mock куки
                mock_cookies_saved = await self._save_mock_cookies_to_database(user_id, telegram_id)
                
                return {
                    "success": True,
                    "message": "Mock авторизация завершена! Куки сохранены." if mock_cookies_saved else "Mock авторизация завершена, но куки не сохранены.",
                    "cookies_saved": mock_cookies_saved,
                    "final_url": "https://vkusvill.ru/"
                }
            
            # Реальный RPA режим
            logger.info("🎯 Real RPA mode: waiting for authentication completion...")
            
            if not self.current_session:
                return {
                    "success": False,
                    "message": "Нет активной RPA сессии"
                }
            
            # Ожидаем успешной авторизации (простое ожидание)
            logger.info("⏰ Waiting for user to complete SMS authentication...")
            await asyncio.sleep(10)  # Простое ожидание
            
            # Сохраняем куки из сессии
            cookies_saved = await self._save_cookies(self.current_session, user_id)
            
            # Закрываем сессию
            await self.cleanup()
            
            return {
                "success": True,
                "message": "Авторизация завершена успешно!" if cookies_saved else "Авторизация завершена, но куки не сохранены.",
                "cookies_saved": cookies_saved
            }
            
        except Exception as e:
            logger.error(f"Error completing VkusVill authentication: {e}")
            await self.cleanup()
            return {
                "success": False,
                "message": f"Ошибка завершения авторизации: {str(e)}"
            }
            
    async def _save_mock_cookies_to_database(self, user_id: int, telegram_id: Optional[int] = None) -> bool:
        """Сохранение mock куки в базу данных"""
        try:
            logger.info("🍪 Mock mode: Generating and saving VkusVill mock cookies...")
            
            import time
            timestamp = int(time.time())
            
            mock_cookies_dict = {
                "vkusvill_session": {
                    "value": f"mock_vkusvill_session_{user_id}_{timestamp}",
                    "domain": ".vkusvill.ru",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                    "sameSite": "Lax"
                },
                "auth_token": {
                    "value": f"mock_auth_{timestamp}",
                    "domain": "vkusvill.ru",
                    "path": "/",
                    "secure": True,
                    "httpOnly": False,
                    "sameSite": "Lax"
                }
            }
            
            # Используем telegram_id для API если есть
            api_user_id = telegram_id if telegram_id else user_id
            
            # Сохраняем через user-service API
            return await self._call_user_service_save_cookies(api_user_id, mock_cookies_dict)
            
        except Exception as e:
            logger.error(f"Error saving VkusVill mock cookies: {e}")
            return False


# Функция для тестирования
async def test_vkusvill_auth():
    """Тест авторизации в ВкусВилл"""
    
    # Тестовая конфигурация
    rpa_config = {
        "type": "sms_auth_flow",
        "sms_required": True,
        # auth_url заменён на использование base_url
        "success_indicators": [
            {
                "selector": "//button[normalize-space(text())='Кабинет']"
            }
        ],
        "steps": [
            {
                "id": "open_page",
                "action": "navigate",
                "url": "https://vkusvill.ru",
                "wait_for": {
                    "selectors": [
                        "//button[normalize-space(text())='Войти']",
                        "//div[normalize-space(text())='Войти']"
                    ]
                },
                "timeout": 10000
            },
            {
                "id": "click_login",
                "action": "click",
                "selectors": [
                    "//button[normalize-space(text())='Войти']",
                    "//div[normalize-space(text())='Войти']"
                ],
                "wait_for": {
                    "selectors": [
                        "input[type='tel']",
                        "//input[contains(@placeholder, 'телефон')]"
                    ]
                },
                "timeout": 5000
            },
            {
                "id": "uncheck_newsletter",
                "action": "uncheck",
                "selectors": [
                    "input[type='checkbox']:checked"
                ],
                "optional": True
            },
            {
                "id": "enter_phone",
                "action": "type",
                "selectors": [
                    "input[type='tel']",
                    "//input[contains(@placeholder, 'телефон')]"
                ],
                "value": "{phone}",
                "wait_after": 1000
            },
            {
                "id": "click_continue",
                "action": "click",
                "selectors": [
                    "//button[normalize-space(text())='Продолжить']"
                ],
                "wait_for": {
                    "selectors": [
                        "input[name='SMS']",
                        "//input[@name='SMS']"
                    ]
                },
                "timeout": 10000
            },
            {
                "id": "request_sms",
                "action": "request_sms_code",
                "timeout": 60000
            },
            {
                "id": "enter_sms",
                "action": "type",
                "selectors": [
                    "input[name='SMS']",
                    "//input[@name='SMS']"
                ],
                "value": "{sms_code}",
                "wait_after": 2000
            },
            {
                "id": "verify_success",
                "action": "wait_for",
                "selectors": [
                    "//button[normalize-space(text())='Кабинет']"
                ],
                "timeout": 10000,
                "success": True
            }
        ]
    }
    
    config = {
        "id": 3,
        "name": "vkusvill",
        "display_name": "ВкусВилл",
        # auth_url заменён на использование base_url
        "rpa_config": rpa_config
    }
    
    auth = VkusVillAuthenticator(config, headless=False, debug=True)
    
    try:
        # Тест авторизации
        result = await auth.authenticate("+7 900 123 45 67")
        print(f"Auth result: {result}")
        
        if result.get("success") and result.get("session_id"):
            print("Введите SMS код:")
            sms_code = input()
            
            # Продолжаем с SMS кодом
            continue_result = await auth.continue_sms_auth(result["session_id"], sms_code)
            print(f"Continue result: {continue_result}")
            
    finally:
        await auth.cleanup()


if __name__ == "__main__":
    asyncio.run(test_vkusvill_auth())
