"""
RPA модуль для авторизации в ЛСД
"""

import asyncio
import os
import sys
import json
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import base64
from io import BytesIO
from PIL import Image
import re
from qreader import QReader
import numpy as np

# Добавляем корневую папку проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import logging

logger = logging.getLogger(__name__)


class LSDAuthenticator:
    """Базовый класс для RPA авторизации в ЛСД"""
    
    def __init__(self, lsd_config: Dict[str, Any]):
        self.lsd_config = lsd_config
        self.lsd_name = lsd_config.get("name")
        self.lsd_id = lsd_config.get("id")
        
    async def authenticate(self, phone: str, **kwargs) -> Dict[str, Any]:
        """Основной метод авторизации (переопределяется в наследниках)"""
        raise NotImplementedError
        
    async def get_session_data(self) -> Dict[str, Any]:
        """Получение данных сессии (cookies, tokens)"""
        raise NotImplementedError
    
    async def open_browser_with_cookies(self, cookies: list, url: str) -> Dict[str, Any]:
        """Открытие браузера с загруженными куками"""
        raise NotImplementedError


class YandexLavkaAuthenticator(LSDAuthenticator):
    """RPA авторизация в Яндекс.Лавке через QR-код"""
    
    def __init__(self, lsd_config: Dict[str, Any], headless: bool = True, debug: bool = False):
        super().__init__(lsd_config)
        self.headless = headless  # Можно отключить для визуального контроля
        self.debug = debug
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.base_url = lsd_config.get("base_url")  # Используем base_url напрямую
        
    async def authenticate(self, phone: str, use_saved_cookies: bool = True, **kwargs) -> Dict[str, Any]:
        """Авторизация в Яндекс.Лавке через QR-код или сохраненные куки"""
        try:
            logger.info(f"Starting Yandex.Lavka authentication for phone {phone}")
            
            # 🍪 Проверяем сохраненные куки, если указан user_id
            user_id = kwargs.get('user_id')
            if use_saved_cookies and user_id:
                logger.info(f"🍪 Checking for saved cookies for user {user_id}...")
                saved_cookies = await self.get_saved_cookies(user_id, self.lsd_name)
                
                if saved_cookies:
                    logger.info("✅ Found saved cookies, attempting to use them...")
                    
                    # Пробуем использовать сохраненные куки
                    cookies_result = await self._authenticate_with_saved_cookies(saved_cookies)
                    if cookies_result.get("success"):
                        return cookies_result
                    else:
                        logger.warning("⚠️ Saved cookies failed, proceeding with QR authentication")
                else:
                    logger.info("ℹ️ No saved cookies found, proceeding with QR authentication")
            
            # Проверяем, есть ли base_url в конфигурации
            if not self.base_url:
                logger.warning("No base_url in config, using mock")
                return await self._mock_authenticate(phone)
            
            # Пробуем запустить реальный RPA
            try:
                await self._init_browser()
                result = await self._real_authenticate(phone)
                
                # 🚨 ОПЦИОНАЛЬНО: Для mock режима закрываем сразу, для реального - оставляем открытым
                if result.get("auth_type") == "qr_code_mock":
                    # Мок режим - браузер уже закрыт в _mock_authenticate
                    pass
                else:
                    # Реальный QR - браузер остается открытым для ожидания авторизации
                    # Но запускаем таймер на закрытие через 15 минут
                    asyncio.create_task(self._delayed_cleanup(900))  # 15 минут = 900 секунд
                    logger.info("⏰ Browser will auto-close in 15 minutes if no authentication occurs")
                
                return result
                
            except Exception as e:
                logger.error(f"Real RPA failed: {e}, falling back to mock")
                await self.cleanup()
                return await self._mock_authenticate(phone)
            
        except Exception as e:
            logger.error(f"Error during Yandex.Lavka authentication: {e}")
            # Убеждаемся, что браузер закрыт при ошибках
            await self.cleanup()
            return {"success": False, "error": str(e)}
    
    async def _mock_authenticate(self, phone: str) -> Dict[str, Any]:
        """Мок авторизация (без браузера)"""
        logger.info("Using mock authentication (no browser)")
        
        # 🚨 ВАЖНО: Закрываем браузер, если он был открыт для mock авторизации
        await self.cleanup()
        
        await asyncio.sleep(2)  # Имитируем время работы RPA
        
        mock_qr_url = f"https://passport.yandex.ru/auth/qr?uuid=demo_{phone.replace('+', '')}_{int(datetime.now().timestamp())}"
        
        return {
            "success": True,
            "auth_type": "qr_code_mock",  # Отмечаем как mock
            "qr_url": mock_qr_url,
            "qr_image_base64": None,
            "message": "Отсканируйте QR-код в приложении Яндекс для авторизации (demo режим)"
        }
    
    async def _authenticate_with_saved_cookies(self, saved_cookies: Dict[str, Any]) -> Dict[str, Any]:
        """Попытка авторизации с сохраненными куки"""
        try:
            logger.info("🍪 Attempting authentication with saved cookies...")
            
            # Инициализируем браузер
            await self._init_browser()
            
            # Применяем сохраненные куки
            cookies_applied = await self.apply_saved_cookies_to_context(self.context, saved_cookies)
            
            if not cookies_applied:
                logger.error("❌ Failed to apply saved cookies")
                await self.cleanup()
                return {"success": False, "message": "Ошибка применения сохраненных куки"}
            
            # Переходим напрямую на Лавку
            logger.info("🔄 Testing saved cookies by navigating to Lavka...")
            await self.page.goto("https://lavka.yandex.ru/", timeout=30000)
            await self.page.wait_for_load_state('networkidle', timeout=10000)
            
            current_url = self.page.url
            logger.info(f"Current URL after cookie navigation: {current_url}")
            
            # Проверяем, находимся ли мы на странице Лавки (а не авторизации)
            if "lavka.yandex.ru" in current_url and "passport.yandex.ru" not in current_url:
                logger.info("✅ Saved cookies are valid! Successfully authenticated.")
                
                # Не закрываем браузер, так как он может понадобиться для дальнейших действий
                return {
                    "success": True,
                    "auth_type": "saved_cookies",
                    "message": "Авторизация прошла через сохраненные куки",
                    "current_url": current_url
                }
            else:
                logger.warning(f"⚠️ Saved cookies are expired or invalid. Current URL: {current_url}")
                await self.cleanup()
                return {"success": False, "message": "Сохраненные куки устарели"}
            
        except Exception as e:
            logger.error(f"Error authenticating with saved cookies: {e}")
            await self.cleanup()
            return {"success": False, "message": f"Ошибка авторизации с сохраненными куки: {str(e)}"}
    
    async def _real_authenticate(self, phone: str) -> Dict[str, Any]:
        """Реальная RPA авторизация"""
        logger.info("Using real RPA authentication")
        
        try:
            # Переходим на страницу авторизации
            logger.info(f"Navigating to: {self.base_url}")
            await self.page.goto(self.base_url, timeout=30000)
            
            # Ждем загрузки страницы
            await self.page.wait_for_load_state('networkidle', timeout=30000)
            
            # Логируем текущий URL и заголовок страницы
            current_url = self.page.url
            title = await self.page.title()
            logger.info(f"Page loaded: {current_url}, title: '{title}'")
            
            # 🏃‍♂️ Параллельно обрабатываем куки и ищем QR кнопку
            logger.info("🏃‍♂️ Starting parallel cookie handling and QR button search...")
            
            # Запускаем оба процесса одновременно
            cookie_task = asyncio.create_task(self._handle_cookie_banner_fast())
            qr_button_task = asyncio.create_task(self._find_qr_button_with_wait())
            
            # Ждем завершения обеих задач
            cookie_result, qr_button = await asyncio.gather(cookie_task, qr_button_task, return_exceptions=True)
            
            logger.info(f"🍪 Cookie result: {cookie_result}")
            
            if not qr_button or isinstance(qr_button, Exception):
                logger.error(f"QR button not found: {qr_button}")
                if self.debug:
                    await self.page.screenshot(path="logs/qr_button_not_found.png")
                    logger.info("Screenshot saved to logs/qr_button_not_found.png")
                raise Exception("QR button not found")
            
            await qr_button.click()
            logger.info("🔍 QR button clicked, waiting briefly...")
            await asyncio.sleep(1)  # Сокращаем ожидание
            
            # Извлекаем QR-код
            qr_data = await self._extract_qr_code()
            if not qr_data:
                logger.error("QR code not found, fallback to mock")
                if self.debug:
                    await self.page.screenshot(path="logs/qr_code_not_found.png")
                    logger.info("Screenshot saved to logs/qr_code_not_found.png")
                raise Exception("QR code not found")
            
            logger.info(f"QR code extracted: {qr_data['url']}")
            
            # Возвращаем QR URL для показа пользователю, но НЕ закрываем браузер
            # Браузер остается открытым для ожидания авторизации
            qr_result = {
                "success": True,
                "auth_type": "qr_code",
                "qr_url": qr_data['url'],
                "qr_image_base64": qr_data.get('image_base64'),
                "message": "Отсканируйте QR-код в приложении Яндекс для авторизации"
            }
            
            # Не запускаем в фоне, а ждем авторизации синхронно
            # НО возвращаем QR сначала, а потом ждем в отдельном потоке
            
            # Сохраняем контекст для последующего использования
            self._auth_phone = phone
            
            return qr_result
            
        except Exception as e:
            logger.error(f"RPA failed: {e}")
            raise
    
    async def _handle_cookie_banner_fast(self):
        """Быстрая обработка cookie bannerа"""
        try:
            logger.info("🍪 Fast cookie banner handling...")
            
            # Короткие основные селекторы
            quick_selectors = [
                "//div[contains(text(), 'Accept all')]",
                "//button[contains(text(), 'Accept all')]",
                "//div[contains(text(), 'Allow all')]",
                "//button[contains(text(), 'Allow all')]",
                "//div[contains(text(), 'Принять все')]",
                "//button[contains(text(), 'Принять все')]",
            ]
            
            for selector in quick_selectors:
                try:
                    elements = self.page.locator(selector)
                    element_count = await elements.count()
                    
                    if element_count > 0:
                        for j in range(element_count):
                            element = elements.nth(j)
                            if await element.is_visible():
                                text = await element.inner_text()
                                logger.info(f"🍪 Found cookie button: '{text}', clicking...")
                                
                                await element.click()
                                # Минимальная пауза
                                await asyncio.sleep(0.5)
                                logger.info("✅ Cookie accepted fast!")
                                return "success"
                        
                except Exception as e:
                    logger.debug(f"Fast cookie selector {selector} failed: {e}")
                    continue
            
            logger.info("⚠️ No cookie banner found quickly")
            return "not_found"
            
        except Exception as e:
            logger.debug(f"Fast cookie banner handling failed: {e}")
            return "error"
    
    async def _find_qr_button_with_wait(self) -> Optional[Any]:
        """Поиск QR кнопки с коротким ожиданием"""
        try:
            logger.info("🔍 Searching for QR button with short wait...")
            
            # Пробуем найти сразу
            qr_button = await self._find_qr_button()
            if qr_button:
                return qr_button
            
            # Если не нашли, ждем немного и пробуем еще раз
            await asyncio.sleep(1)
            qr_button = await self._find_qr_button()
            if qr_button:
                return qr_button
            
            # Последняя попытка
            await asyncio.sleep(1)
            return await self._find_qr_button()
            
        except Exception as e:
            logger.error(f"Error in QR button search with wait: {e}")
            return None

        
    async def _init_browser(self):
        """Инициализация браузера"""
        playwright = await async_playwright().start()
        
        # Выбираем режим: headless (скрытый) или headful (визуальный)
        # Минимальные аргументы для максимальной совместимости
        browser_args = [
            '--no-sandbox', 
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled'
        ]
        
        if self.debug:
            browser_args.extend(['--disable-web-security', '--allow-running-insecure-content'])
        
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=browser_args,
            slow_mo=2000 if not self.headless else 0  # Замедляем действия в визуальном режиме
        )
        
        # Минимальный контекст без агрессивной маскировки
        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
        )
        
        self.page = await self.context.new_page()
        
        # Минимальная JavaScript маскировка
        await self.page.add_init_script("""
            // Удаляем webdriver флаг
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true
            });
            
            // Удаляем window.chrome
            if (window.chrome && window.chrome.runtime) {
                delete window.chrome.runtime;
            }
            
            console.log('✅ Яндекс.Лавка: Минимальная маскировка');
        """)
        
        if self.debug:
            logger.info(f"Browser launched in {'headless' if self.headless else 'headful'} mode")  
            logger.info(f"Navigation timeout: 30s, slow_mo: {'2s' if not self.headless else 'disabled'}")
            
            # Для debugging можно слушать события
            self.page.on('console', lambda msg: logger.debug(f"Browser console: {msg.text}"))
            self.page.on('dialog', lambda dialog: logger.debug(f"Browser dialog: {dialog.message}"))
            self.page.on('response', lambda response: 
                logger.debug(f"Response: {response.url} - {response.status}") 
                if response.status >= 400 else None)
        
    async def _find_qr_button(self) -> Optional[Any]:
        """Поиск кнопки 'QR-код' на странице (с поддержкой русского языка)"""
        try:
            # Обновленные селекторы для поиска QR кнопки на русском и английском
            selectors = [
                # Русские варианты (основные)
                "//span[contains(text(), 'QR-код')]//ancestor::button",
                "//button[contains(text(), 'QR-код')]",
                "//span[contains(text(), 'QR-кодом')]//ancestor::button",
                "//button[contains(text(), 'QR-кодом')]",
                "//span[contains(text(), 'по QR')]//ancestor::button",
                "//button[contains(text(), 'по QR')]",
                
                # Английские варианты (резервные)
                "//span[contains(text(), 'QR')]//ancestor::button",
                "//button[contains(text(), 'QR')]",
                "//button[contains(text(), 'QR code')]",
                "//a[contains(text(), 'QR')]",
                
                # CSS селекторы для QR элементов
                "button[data-testid*='qr']",
                "button[class*='qr']",
                "[role='button'][aria-label*='QR']"
            ]
            
            logger.info(f"Searching for QR button using {len(selectors)} selectors (RU + EN)...")
            
            for i, selector in enumerate(selectors, 1):
                try:
                    logger.debug(f"Trying selector {i}/{len(selectors)}: {selector}")
                    
                    elements = self.page.locator(selector)
                    element_count = await elements.count()
                    
                    if element_count > 0:
                        # Проверяем каждый элемент
                        for j in range(element_count):
                            element = elements.nth(j)
                            if await element.is_visible():
                                text = await element.inner_text()
                                logger.info(f"✅ Found QR button: '{text}' (selector {i})")
                                return element
                            
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            logger.warning("❌ QR button not found with any selector")
            
            # Дополнительная диагностика - ищем все кнопки с "QR" в тексте
            await self._debug_qr_buttons()
            
            # Последняя попытка - ищем любые кликабельные элементы с "QR"
            fallback_qr_element = await self._find_qr_button_fallback()
            if fallback_qr_element:
                return fallback_qr_element
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding QR button: {e}")
            return None
            
    async def _debug_qr_buttons(self):
        """Диагностика QR кнопок на странице"""
        try:
            logger.info("🔍 Debugging QR buttons on page...")
            
            # Поиск всех элементов с "QR" в тексте
            all_qr_elements = self.page.locator("//*[contains(text(), 'QR')]")
            element_count = await all_qr_elements.count()
            
            logger.info(f"Found {element_count} elements containing 'QR':")
            
            for i in range(min(element_count, 10)):  # Ограничиваем 10 элементами
                try:
                    element = all_qr_elements.nth(i)
                    if await element.is_visible():
                        text = (await element.inner_text()).strip()[:100]
                        tag_name = await element.evaluate("el => el.tagName")
                        class_name = await element.get_attribute("class") or ""
                        
                        logger.info(f"  {i+1}. <{tag_name.lower()}> text: '{text}'")
                        if class_name:
                            logger.info(f"      class: '{class_name}'")
                        
                        # Проверяем, является ли элемент кнопкой или кликабельным
                        is_clickable = await element.evaluate("""
                            el => {
                                const tagName = el.tagName.toLowerCase();
                                const role = el.getAttribute('role');
                                const onclick = el.onclick || el.getAttribute('onclick');
                                const cursor = window.getComputedStyle(el).cursor;
                                
                                return tagName === 'button' || 
                                       tagName === 'a' || 
                                       role === 'button' || 
                                       onclick || 
                                       cursor === 'pointer';
                            }
                        """)
                        
                        if is_clickable:
                            logger.info(f"      👆 CLICKABLE - this might be our QR button!")
                        
                        logger.info("")
                        
                except Exception as e:
                    logger.debug(f"Could not analyze QR element {i}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in QR button debugging: {e}")
    
    async def _find_qr_button_fallback(self) -> Optional[Any]:
        """Последняя попытка найти QR кнопку - любой кликабельный элемент с QR"""
        try:
            logger.info("🆘 Fallback: searching for ANY clickable element with 'QR'...")
            
            # Поиск всех элементов с QR (русские и английские)
            qr_patterns = [
                "//*[contains(text(), 'QR-код')]",
                "//*[contains(text(), 'QR-кодом')]",
                "//*[contains(text(), 'по QR')]",
                "//*[contains(text(), 'QR')]"
            ]
            
            for pattern in qr_patterns:
                elements = self.page.locator(pattern)
                element_count = await elements.count()
                
                for i in range(element_count):
                    element = elements.nth(i)
                    
                    if await element.is_visible():
                        # Проверяем, кликабельный ли элемент
                        is_clickable = await element.evaluate("""
                            el => {
                                const tagName = el.tagName.toLowerCase();
                                const role = el.getAttribute('role');
                                const onclick = el.onclick || el.getAttribute('onclick');
                                const cursor = window.getComputedStyle(el).cursor;
                                const parent = el.parentElement;
                                
                                // Проверяем сам элемент
                                const selfClickable = tagName === 'button' || 
                                                      tagName === 'a' || 
                                                      role === 'button' || 
                                                      onclick || 
                                                      cursor === 'pointer';
                                
                                // Проверяем родительский элемент
                                const parentClickable = parent && (
                                    parent.tagName.toLowerCase() === 'button' ||
                                    parent.tagName.toLowerCase() === 'a' ||
                                    parent.getAttribute('role') === 'button'
                                );
                                
                                return selfClickable || parentClickable;
                            }
                        """)
                        
                        if is_clickable:
                            text = await element.inner_text()
                            logger.info(f"🎆 Fallback found clickable QR element: '{text.strip()}'")
                            
                            # Если элемент не кнопка, попробуем найти родительскую кнопку
                            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
                            
                            if tag_name in ['button', 'a']:
                                return element
                            else:
                                # Поиск родительской кнопки
                                parent_button = element.locator("xpath=./ancestor::button[1] | ./ancestor::a[1]")
                                if await parent_button.count() > 0:
                                    logger.info("👆 Found parent button for QR element")
                                    return parent_button.first
                                else:
                                    # Используем сам элемент, если он кликабельный
                                    logger.info("👆 Using clickable QR element itself")
                                    return element
            
            logger.warning("❌ Fallback: no clickable QR elements found")
            return None
            
        except Exception as e:
            logger.error(f"Error in QR button fallback search: {e}")
            return None
    
    async def _decode_qr_simple(self, screenshot_path: str) -> Optional[str]:
        """Простое декодирование QR-кода с pyzbar (без QReader)"""
        try:
            from pyzbar import pyzbar
            from PIL import Image
            
            logger.info(f"📱 Decoding QR from: {screenshot_path}")
            
            # Открываем скриншот
            image = Image.open(screenshot_path)
            logger.info(f"Image opened: {image.size}, mode: {image.mode}")
            
            # Пробуем pyzbar на оригинальном изображении
            qr_codes = pyzbar.decode(image)
            
            if qr_codes:
                logger.info(f"✅ pyzbar found {len(qr_codes)} QR codes")
                for i, qr_code in enumerate(qr_codes):
                    qr_data = qr_code.data.decode("utf-8")
                    logger.info(f"QR {i+1}: {qr_data}")
                    if "passport.yandex.ru" in qr_data or len(qr_data) > 20:
                        return qr_data
                        
                # Возвращаем первый QR если ничего не подошло
                return qr_codes[0].data.decode("utf-8")
            
            logger.info("⚠️ pyzbar found no QR codes, trying preprocessing...")
            
            # Пробуем с обработкой изображения
            # 1. Grayscale
            gray_image = image.convert("L")
            qr_codes_gray = pyzbar.decode(gray_image)
            
            if qr_codes_gray:
                logger.info(f"✅ pyzbar found {len(qr_codes_gray)} QR codes (grayscale)")
                for i, qr_code in enumerate(qr_codes_gray):
                    qr_data = qr_code.data.decode("utf-8")
                    logger.info(f"QR (gray) {i+1}: {qr_data}")
                    return qr_data
            
            # 2. Увеличение контрастности
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(gray_image)
            contrast_image = enhancer.enhance(2.0)  # Увеличиваем контраст в 2 раза
            
            qr_codes_contrast = pyzbar.decode(contrast_image)
            if qr_codes_contrast:
                logger.info(f"✅ pyzbar found {len(qr_codes_contrast)} QR codes (contrast)")
                for i, qr_code in enumerate(qr_codes_contrast):
                    qr_data = qr_code.data.decode("utf-8")
                    logger.info(f"QR (contrast) {i+1}: {qr_data}")
                    return qr_data
            
            # 3. Инвертирование цветов
            from PIL import ImageOps
            inverted_image = ImageOps.invert(gray_image)
            
            qr_codes_inverted = pyzbar.decode(inverted_image)
            if qr_codes_inverted:
                logger.info(f"✅ pyzbar found {len(qr_codes_inverted)} QR codes (inverted)")
                for i, qr_code in enumerate(qr_codes_inverted):
                    qr_data = qr_code.data.decode("utf-8")
                    logger.info(f"QR (inverted) {i+1}: {qr_data}")
                    return qr_data
            
            logger.warning("❌ No QR codes found with any method")
            return None
            
        except Exception as e:
            logger.error(f"Error in simple QR decode: {e}")
            return None
            
        except Exception as e:
            logger.debug(f"Error in simple QR decode: {e}")
            return None

    
    async def _analyze_page_buttons(self):
        """Анализ всех кнопок на странице для отладки"""
        try:
            logger.info("🔍 Analyzing all buttons and clickable elements on page...")
            
            # Получаем все кнопки и ссылки
            buttons = self.page.locator("button, a, [role='button']")
            button_count = await buttons.count()
            
            logger.info(f"Found {button_count} clickable elements:")
            
            # Ограничиваем 20 элементами
            max_elements = min(button_count, 20)
            
            for i in range(max_elements):
                try:
                    button = buttons.nth(i)
                    if await button.is_visible():
                        text = (await button.inner_text()).strip()[:50]
                        tag_name = await button.evaluate("el => el.tagName")
                        class_name = await button.get_attribute("class") or ""
                        
                        logger.info(f"  {i+1}. <{tag_name.lower()}> text: '{text}'")
                        if class_name:
                            logger.info(f"      class: '{class_name}'")
                        logger.info("")
                        
                except Exception as e:
                    logger.debug(f"Could not analyze button {i}: {e}")
                    
        except Exception as e:
            logger.error(f"Error analyzing page buttons: {e}")
    
    async def _find_qr_image_in_dom(self) -> Optional[str]:
        """Попытка найти QR изображение напрямую в DOM"""
        try:
            logger.info("🔍 Searching for QR image in DOM...")
            
            # Селекторы для поиска QR изображений
            qr_selectors = [
                "img.QrComponent-image",
                "img[class*=QrComponent]",
                "img[class*=qr]",
                "img[src*=blob]",
                "img[src*=qr]",
                ".qr-code img",
                "[data-testid*=qr] img"
            ]
            
            for selector in qr_selectors:
                try:
                    elements = self.page.locator(selector)
                    element_count = await elements.count()
                    
                    if element_count > 0:
                        logger.info(f"Found {element_count} QR image(s) with selector: {selector}")
                        
                        for i in range(element_count):
                            element = elements.nth(i)
                            if await element.is_visible():
                                src = await element.get_attribute("src")
                                if src:
                                    logger.info(f"✅ Found QR image: {src[:100]}...")
                                    
                                    # Пробуем скачать и декодировать
                                    qr_text = await self._download_and_decode_qr(src)
                                    if qr_text:
                                        logger.info(f"✅ QR decoded from DOM: {qr_text}")
                                        return qr_text
                except Exception as e:
                    logger.debug(f"DOM selector {selector} failed: {e}")
                    continue
            
            logger.info("⚠️ No QR images found in DOM")
            return None
            
        except Exception as e:
            logger.error(f"Error finding QR image in DOM: {e}")
            return None
    
    async def _download_and_decode_qr(self, src_url: str) -> Optional[str]:
        """Скачивание и декодирование QR изображения"""
        try:
            if src_url.startswith("blob:"):
                # Скачиваем blob через JavaScript
                image_data_url = await self.page.evaluate(f"""
                    async (blobUrl) => {{
                        try {{
                            const response = await fetch(blobUrl);
                            const blob = await response.blob();
                            
                            return new Promise((resolve) => {{
                                const reader = new FileReader();
                                reader.onload = () => resolve(reader.result);
                                reader.readAsDataURL(blob);
                            }});
                        }} catch (e) {{
                            return null;
                        }}
                    }}
                """, src_url)
                
                if image_data_url and image_data_url.startswith("data:image"):
                    # Сохраняем изображение
                    import base64
                    image_data = image_data_url.split(",")[1]
                    image_bytes = base64.b64decode(image_data)
                    
                    qr_image_path = "logs/qr_downloaded_image.png"
                    with open(qr_image_path, "wb") as f:
                        f.write(image_bytes)
                    
                    logger.info(f"💾 Downloaded QR image: {len(image_bytes)} bytes")
                    
                    # Декодируем
                    qr_text = await self._decode_qr_simple(qr_image_path)
                    return qr_text
            
            return None
            
        except Exception as e:
            logger.error(f"Error downloading QR image: {e}")
            return None

    async def _extract_qr_code(self) -> Optional[Dict[str, str]]:
        """Извлечение QR-кода: сначала DOM, потом скриншоты"""
        try:
            logger.info("🔍 Extracting QR code...")
            
            # Ждем немного чтобы QR полностью загрузился  
            await asyncio.sleep(2)
            
            # Сначала пробуем найти QR в DOM
            qr_url_from_dom = await self._find_qr_image_in_dom()
            if qr_url_from_dom:
                logger.info(f"✅ QR code found in DOM: {qr_url_from_dom}")
                return {
                    "url": qr_url_from_dom,
                    "image_base64": None
                }
            
            # Если в DOM не нашли, делаем скриншоты
            logger.info("🔍 DOM search failed, trying repeated screenshots...")
            
            max_attempts = 5
            
            for attempt in range(1, max_attempts + 1):
                logger.info(f"📷 Screenshot attempt {attempt}/{max_attempts}")
                
                # Ждем секунду перед скриншотом
                await asyncio.sleep(1)
                
                # Делаем скриншот
                screenshot_path = f"logs/qr_screenshot_attempt_{attempt}_{int(datetime.now().timestamp())}.png"
                await self.page.screenshot(path=screenshot_path)
                logger.info(f"📷 Screenshot {attempt} saved to {screenshot_path}")
                
                # Пробуем декодировать QR
                qr_url = await self._decode_qr_simple(screenshot_path)
                
                if qr_url:
                    logger.info(f"✅ QR code found on attempt {attempt}: {qr_url}")
                    
                    # Читаем скриншот для base64
                    try:
                        with open(screenshot_path, "rb") as f:
                            screenshot_base64 = base64.b64encode(f.read()).decode("utf-8")
                    except:
                        screenshot_base64 = None
                    
                    return {
                        "url": qr_url,
                        "image_base64": screenshot_base64
                    }
                else:
                    logger.info(f"⚠️ No QR found on attempt {attempt}, trying again...")
            
            logger.warning(f"❌ QR code not found after {max_attempts} attempts")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting QR code: {e}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting QR code via repeated screenshots: {e}")
            return None
    
    async def _download_qr_image_simple(self, src_url: str) -> Optional[bytes]:
        """Простое скачивание QR изображения"""
        try:
            logger.info(f"💾 Downloading QR image: {src_url[:100]}...")
            
            if src_url.startswith('blob:'):
                # Для blob URL используем JavaScript
                image_data_url = await self.page.evaluate(f"""
                    async (blobUrl) => {{
                        try {{
                            const response = await fetch(blobUrl);
                            const blob = await response.blob();
                            
                            return new Promise((resolve) => {{
                                const reader = new FileReader();
                                reader.onload = () => resolve(reader.result);
                                reader.readAsDataURL(blob);
                            }});
                        }} catch (e) {{
                            return null;
                        }}
                    }}
                """, src_url)
                
                if image_data_url and image_data_url.startswith('data:image'):
                    header, data = image_data_url.split(',', 1)
                    image_bytes = base64.b64decode(data)
                    logger.info(f"✅ Downloaded blob: {len(image_bytes)} bytes")
                    
                    # Сохраняем
                    try:
                        with open("logs/qr_simple_downloaded.png", "wb") as f:
                            f.write(image_bytes)
                        logger.info("💾 Saved to logs/qr_simple_downloaded.png")
                    except:
                        pass
                    
                    return image_bytes
            
            elif src_url.startswith('http'):
                # Для обычных HTTP URL
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.get(src_url, timeout=10.0)
                    if response.status_code == 200:
                        image_bytes = response.content
                        logger.info(f"✅ Downloaded HTTP: {len(image_bytes)} bytes")
                        
                        # Сохраняем
                        try:
                            with open("logs/qr_simple_downloaded.png", "wb") as f:
                                f.write(image_bytes)
                            logger.info("💾 Saved to logs/qr_simple_downloaded.png")
                        except:
                            pass
                        
                        return image_bytes
            
            logger.warning(f"❌ Unsupported URL format: {src_url[:50]}...")
            return None
            
        except Exception as e:
            logger.error(f"Error downloading QR image: {e}")
            return None
    async def _decode_qr_from_image_data(self, image_data: bytes) -> Optional[str]:
        """Декодирование QR-кода из байтов изображения"""
        try:
            logger.info("🔍 Decoding QR code from image data...")
            
            # Открываем изображение с помощью PIL
            image = Image.open(BytesIO(image_data))
            logger.info(f"Image opened: {image.size}, mode: {image.mode}")
            
            # Конвертируем в numpy array
            image_array = np.array(image)
            
            # Инициализируем QReader
            qreader = QReader()
            
            # Пробуем декодировать
            decoded_text = qreader.detect_and_decode(image=image_array)
            
            if decoded_text and len(decoded_text) > 0:
                # QReader возвращает список, берем первый элемент
                qr_text = decoded_text[0] if isinstance(decoded_text, list) else decoded_text
                
                if qr_text and isinstance(qr_text, str) and len(qr_text) > 10:
                    logger.info(f"🔍 Raw QR decoded: {qr_text}")
                    
                    # Проверяем, что URL корректный (grocery-frontend-standalone)
                    if 'grocery-frontend-standalone' in qr_text and 'passport.yandex.ru' in qr_text:
                        logger.info(f"✅ QR code decoded and validated: {qr_text}")
                        return qr_text
                    else:
                        logger.info(f"🔍 QR decoded but not grocery URL, returning anyway: {qr_text}")
                        # Возвращаем любой URL
                        return qr_text
                    
            logger.warning("❌ No QR code found in image")
            return None
            
        except Exception as e:
            logger.error(f"Error decoding QR from image data: {e}")
            return None
    
    async def wait_for_auth_completion(self, timeout: int = 120) -> Dict[str, Any]:
        """Ожидание завершения авторизации по QR-коду"""
        try:
            start_time = datetime.now()
            
            while (datetime.now() - start_time).seconds < timeout:
                # Проверяем, изменился ли URL (признак успешной авторизации)
                current_url = self.page.url
                
                # Если попали на главную страницу Лавки - авторизация успешна
                if 'lavka.yandex.ru' in current_url or 'grocery' in current_url:
                    logger.info("Yandex.Lavka authentication completed successfully")
                    
                    # Получаем cookies и данные сессии
                    session_data = await self.get_session_data()
                    return {
                        "success": True,
                        "session_data": session_data,
                        "message": "Авторизация завершена успешно"
                    }
                
                await asyncio.sleep(2)
            
            return {
                "success": False, 
                "error": "Timeout waiting for authentication",
                "message": "Время ожидания авторизации истекло"
            }
            
        except Exception as e:
            logger.error(f"Error waiting for auth completion: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_session_data(self) -> Dict[str, Any]:
        """Получение данных сессии после успешной авторизации"""
        try:
            if not self.context:
                return {}
            
            # Получаем все cookies
            cookies = await self.context.cookies()
            
            # Ищем важные токены в Local Storage
            tokens = await self.page.evaluate("""
                () => {
                    const result = {};
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        if (key && (key.includes('token') || key.includes('session') || key.includes('auth'))) {
                            result[key] = localStorage.getItem(key);
                        }
                    }
                    return result;
                }
            """)
            
            return {
                "cookies": {cookie['name']: cookie['value'] for cookie in cookies},
                "local_storage": tokens,
                "user_agent": await self.page.evaluate("navigator.userAgent"),
                "timestamp": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting session data: {e}")
            return {}
    
    @classmethod
    async def get_saved_cookies(cls, user_id: int, lsd_name: str) -> Optional[Dict[str, Any]]:
        """Получение сохраненных куки для повторного использования"""
        try:
            import httpx
            
            # Вызываем user-service API
            user_service_url = "http://localhost:8002"
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{user_service_url}/users/{user_id}/cookies/{lsd_name}"
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        logger.info(f"✅ Retrieved saved cookies for user {user_id}, LSD {lsd_name}")
                        return result.get("data")
                    else:
                        logger.warning(f"⚠️ No saved cookies found for user {user_id}, LSD {lsd_name}")
                        return None
                else:
                    logger.error(f"❌ HTTP error getting saved cookies: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting saved cookies for user {user_id}, LSD {lsd_name}: {e}")
            return None
    
    @classmethod
    async def apply_saved_cookies_to_context(cls, browser_context, saved_cookies: Dict[str, Any]) -> bool:
        """Применение сохраненных куки к браузерному контексту"""
        try:
            if not saved_cookies or not saved_cookies.get("cookies"):
                logger.warning("⚠️ No cookies to apply")
                return False
            
            cookies_data = saved_cookies["cookies"]
            
            # Преобразуем в формат Playwright
            playwright_cookies = []
            
            for name, cookie_info in cookies_data.items():
                if isinstance(cookie_info, dict):
                    playwright_cookie = {
                        "name": name,
                        "value": cookie_info["value"],
                        "domain": cookie_info["domain"],
                        "path": cookie_info.get("path", "/"),
                        "secure": cookie_info.get("secure", False),
                        "httpOnly": cookie_info.get("httpOnly", False),
                        "sameSite": cookie_info.get("sameSite", "Lax")
                    }
                    playwright_cookies.append(playwright_cookie)
                else:
                    # Старый формат - просто значение
                    playwright_cookie = {
                        "name": name,
                        "value": str(cookie_info),
                        "domain": ".lavka.yandex.ru",  # По умолчанию для Яндекс.Лавки
                        "path": "/"
                    }
                    playwright_cookies.append(playwright_cookie)
            
            # Применяем куки
            await browser_context.add_cookies(playwright_cookies)
            logger.info(f"✅ Applied {len(playwright_cookies)} cookies to browser context")
            
            return True
            
        except Exception as e:
            logger.error(f"Error applying saved cookies: {e}")
            return False
    
    async def complete_authentication(self, user_id: int, telegram_id: Optional[int] = None) -> Dict[str, Any]:
        """Завершение авторизации - ожидание, сохранение куки, закрытие браузера"""
        try:
            logger.info("🔄 Starting authentication completion...")
            
            # Ждем редиректа на lavka.yandex.ru
            auth_success = await self._wait_for_authorization()
            
            if auth_success:
                logger.info("🎉 Authentication successful! Now collecting cookies...")
                
                # Ожидаем немного, чтобы страница полностью загрузилась
                await asyncio.sleep(3)
                
                # Сохраняем куки в базу (используем telegram_id для API)
                cookies_saved = await self._save_cookies_to_database(user_id, telegram_id=telegram_id)
                
                # 🚨 ВАЖНО: Закрываем браузер ТОЛЬКО после успешного сохранения кук
                if cookies_saved:
                    logger.info("✅ Cookies saved successfully, closing browser...")
                    await self.cleanup()
                    logger.info("🔄 Browser closed after successful cookie save")
                else:
                    logger.warning("⚠️ Failed to save cookies, keeping browser open for debugging")
                
                return {
                    "success": True,
                    "message": "Авторизация завершена успешно! Куки сохранены." if cookies_saved else "Авторизация завершена, но куки не сохранены.",
                    "cookies_saved": cookies_saved,
                    "final_url": self.page.url if self.page else None
                }
            else:
                logger.info("❌ Authentication timeout, closing browser...")
                await self.cleanup()
                logger.info("🔄 Browser closed after authentication timeout")
                return {
                    "success": False,
                    "message": "Таймаут авторизации - пользователь не отсканировал QR код"
                }
                
        except Exception as e:
            logger.error(f"Error completing authentication: {e}")
            # При ошибке всегда закрываем браузер
            await self.cleanup()
            logger.info("🔄 Browser closed after authentication error")
            return {
                "success": False,
                "message": f"Ошибка завершения авторизации: {str(e)}"
            }
    
    async def start_auth_and_wait_completion(self, user_id: int, phone: str, telegram_id: Optional[int] = None) -> Dict[str, Any]:
        """Полный цикл авторизации: QR код -> ожидание -> сохранение куки -> закрытие браузера"""
        try:
            logger.info(f"🚀 Starting full authentication cycle for user {user_id} (telegram_id: {telegram_id})")
            
            # Шаг 1: Запускаем авторизацию и получаем QR
            auth_result = await self.authenticate(phone, user_id=user_id)
            if not auth_result.get("success"):
                return auth_result
            
            logger.info(f"✅ QR generated: {auth_result.get('qr_url')}")
            
            # 📝 MOCK: В mock режиме симулируем успешный результат И сохраняем mock куки
            if not self.base_url or auth_result.get("auth_type") == "qr_code_mock":
                logger.info("📝 Mock mode: simulating successful authentication with cookie saving")
                
                # Сохраняем mock куки в базу
                mock_cookies_saved = await self._save_mock_cookies_to_database(user_id)
                
                # Имитируем успешное завершение
                mock_completion = {
                    "success": True,
                    "message": "Mock авторизация завершена! Куки сохранены.",
                    "cookies_saved": mock_cookies_saved,
                    "final_url": "https://lavka.yandex.ru/moscow"
                }
                
                return {
                    "success": True,
                    "qr_url": auth_result.get("qr_url"),
                    "qr_image_base64": auth_result.get("qr_image_base64"),
                    "message": mock_completion["message"],
                    "cookies_saved": mock_completion["cookies_saved"],
                    "final_url": mock_completion["final_url"]
                }
            
            # Шаг 2: Ждем, пока пользователь отсканирует QR и произойдет редирект
            completion_result = await self.complete_authentication(user_id, telegram_id=telegram_id)
            
            # Объединяем результаты
            final_result = {
                "success": completion_result.get("success", False),
                "qr_url": auth_result.get("qr_url"),
                "qr_image_base64": auth_result.get("qr_image_base64"),
                "message": completion_result.get("message"),
                "cookies_saved": completion_result.get("cookies_saved", False),
                "final_url": completion_result.get("final_url")
            }
            
            # 📝 НЕ закрываем браузер здесь - это сделано в complete_authentication()
            # logger.info("🔄 Browser cleanup completed after full auth cycle")
            
            return final_result
            
        except Exception as e:
            logger.error(f"Error in full authentication cycle: {e}")
            # При ошибке в полном цикле требуется закрытие браузера
            await self.cleanup()
            logger.info("🔄 Browser closed after full auth cycle error")
            return {
                "success": False,
                "message": f"Ошибка полного цикла авторизации: {str(e)}"
            }

    async def _wait_for_authorization(self) -> bool:
        """Ожидание авторизации пользователя через событие редиректа на base_url (lavka.yandex.ru)"""
        try:
            # 📝 MOCK: Если нет реального браузера, возвращаем mock результат
            if not self.page:
                logger.info("📝 Mock mode: simulating authorization timeout")
                await asyncio.sleep(1)  # Короткая пауза для имитации
                return False  # Мок таймаут
            
            logger.info("🔄 Setting up redirect event listener for base_url...")
            
            # Получаем base_url из конфигурации
            base_url = self.lsd_config.get("base_url", "https://lavka.yandex.ru/")
            base_domain = base_url.replace("https://", "").replace("http://", "").split("/")[0]
            
            logger.info(f"🎯 Target base_url: {base_url}, domain: {base_domain}")
            
            # Флаг для отслеживания успешной авторизации
            auth_completed = asyncio.Event()
            final_url = None
            
            def on_navigation(frame):
                """Обработчик события навигации - основная логика сохранения кук"""
                nonlocal final_url
                url = frame.url
                logger.info(f"🌐 Navigation detected: {url}")
                
                # 🎯 ОСНОВНАЯ ПРОВЕРКА: редирект на base_url (Лавку)
                if base_domain in url and "passport.yandex.ru" not in url:
                    logger.info(f"🎉 SUCCESS! Detected redirect to base_url ({base_domain}): {url}")
                    final_url = url
                    auth_completed.set()
                    return
                    
                # 🎯 АЛЬТЕРНАТИВНАЯ ПРОВЕРКА: grocery + не passport (для совместимости)
                if "grocery" in url and "passport.yandex.ru" not in url:
                    logger.info(f"🎉 SUCCESS! Detected grocery redirect: {url}")
                    final_url = url
                    auth_completed.set()
                    return
            
            def on_response(response):
                """Обработчик HTTP ответов - дополнительная проверка успешных запросов"""
                url = response.url
                if base_domain in url and response.status < 400 and "passport.yandex.ru" not in url:
                    logger.info(f"🎉 SUCCESS! Detected successful response to base_url: {url} (status: {response.status})")
                    nonlocal final_url
                    if not final_url:  # Устанавливаем только если еще не установлен
                        final_url = url
                        auth_completed.set()
            
            # 🔗 Подписываемся на события навигации
            self.page.on("framenavigated", on_navigation)
            self.page.on("response", on_response)
            
            logger.info("⏰ Waiting for authorization (timeout: 10 minutes)...")
            
            try:
                # Ждем событие авторизации с таймаутом 10 минут
                await asyncio.wait_for(auth_completed.wait(), timeout=600)  # 10 минут
                
                logger.info(f"✅ Authorization completed! Final URL: {final_url}")
                
                # Даем время для полной загрузки страницы и установки кук
                logger.info("⏳ Waiting for page to fully load and cookies to be set...")
                await asyncio.sleep(3)
                
                return True
                
            except asyncio.TimeoutError:
                logger.error("❌ Authorization timeout (10 minutes)")
                return False
            finally:
                # 🧹 Отписываемся от событий
                try:
                    self.page.remove_listener("framenavigated", on_navigation)
                    self.page.remove_listener("response", on_response)
                    logger.info("🧹 Event listeners cleaned up")
                except Exception as e:
                    logger.warning(f"⚠️ Error removing listeners: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error in _wait_for_authorization: {e}")
            return False


    async def _call_user_service_save_cookies(self, user_id: int, cookies_dict: dict) -> bool:
        """Вызов user-service API для сохранения куки в базу"""
        try:
            import httpx
            import json
            
            # URL user-service (можно вынести в конфигурацию)
            user_service_url = "http://localhost:8002"
            
            # Подготавливаем данные для отправки
            cookies_data = {
                "lsd_name": self.lsd_name,
                "cookies": cookies_dict,
                "timestamp": int(datetime.now().timestamp())
            }
            
            logger.info(f"📡 Calling user-service to save cookies for user {user_id}")
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{user_service_url}/users/{user_id}/cookies",
                    json=cookies_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        logger.info("✅ Cookies saved to database via user-service")
                        return True
                    else:
                        logger.error(f"❌ User-service returned error: {result.get('error')}")
                        return False
                else:
                    logger.error(f"❌ User-service HTTP error: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error calling user-service to save cookies: {e}")
            return False

    async def _save_mock_cookies_to_database(self, user_id: int) -> bool:
        """Сохранение mock куки в базу данных"""
        try:
            logger.info("🍪 Mock mode: Generating and saving mock cookies...")
            
            # Создаем mock куки
            import time
            timestamp = int(time.time())
            
            mock_cookies_dict = {
                "yandexuid": {
                    "value": f"mock_yandexuid_{timestamp}",
                    "domain": ".yandex.ru",
                    "path": "/",
                    "secure": True,
                    "httpOnly": False,
                    "sameSite": "Lax"
                },
                "sessionid2": {
                    "value": f"mock_session_{user_id}_{timestamp}",
                    "domain": ".yandex.ru", 
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                    "sameSite": "None"
                },
                "Session_id": {
                    "value": f"mock_session_id_{timestamp}",
                    "domain": ".lavka.yandex.ru",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                    "sameSite": "Lax"
                }
            }
            
            # Сохраняем в JSON файл для отладки
            import json
            cookies_file = f"logs/mock_cookies_{self.lsd_name}_{user_id}_{timestamp}.json"
            
            full_data = {
                "user_id": user_id,
                "lsd_name": self.lsd_name,
                "timestamp": timestamp,
                "final_url": "https://lavka.yandex.ru/moscow",
                "cookies": mock_cookies_dict,
                "cookies_count": len(mock_cookies_dict),
                "domains": [".yandex.ru", ".lavka.yandex.ru"],
                "mock": True
            }
            
            with open(cookies_file, "w", encoding="utf-8") as f:
                json.dump(full_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Mock cookies saved to: {cookies_file}")
            
            # Сохраняем куки в базу данных через user-service API
            cookies_saved_to_db = await self._call_user_service_save_cookies(user_id, mock_cookies_dict)
            if cookies_saved_to_db:
                logger.info("🎉 Mock cookies saved to database successfully!")
                return True
            else:
                logger.warning("⚠️ Failed to save mock cookies to database, but have debug file")
                return False
                
        except Exception as e:
            logger.error(f"Error saving mock cookies: {e}")
            return False

    async def _save_cookies_to_database(self, user_id: int, telegram_id: Optional[int] = None) -> bool:
        """Сохранение куки в базу данных"""
        try:
            logger.info("🍪 Collecting cookies from lavka.yandex.ru...")
            current_url = self.page.url if self.page else "unknown"
            logger.info(f"Current page URL: {current_url}")
            
            cookies = await self.context.cookies()
            
            # Преобразуем в удобный формат
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
            
            logger.info(f"✅ Collected {len(cookies_dict)} cookies for domains:")
            domains = set(cookie["domain"] for cookie in cookies)
            for domain in sorted(domains):
                domain_cookies = [c for c in cookies if c["domain"] == domain]
                logger.info(f"  - {domain}: {len(domain_cookies)} cookies")
            
            # Сохраняем в JSON файл для отладки
            import json
            timestamp = int(datetime.now().timestamp())
            cookies_file = f"logs/cookies_{self.lsd_name}_{timestamp}.json"
            
            # Создаем полные данные для сохранения
            full_data = {
                "user_id": user_id,
                "telegram_id": telegram_id,  # 🆕 Добавляем telegram_id
                "lsd_name": self.lsd_name,
                "timestamp": timestamp,
                "final_url": current_url,
                "cookies": cookies_dict,
                "cookies_count": len(cookies_dict),
                "domains": list(domains)
            }
            
            with open(cookies_file, "w", encoding="utf-8") as f:
                json.dump(full_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Debug data saved to: {cookies_file}")
            
            # Сохраняем куки в базу данных через user-service API (используем telegram_id)
            api_user_id = telegram_id if telegram_id else user_id  # 🔄 Приоритет telegram_id
            cookies_saved_to_db = await self._call_user_service_save_cookies(api_user_id, cookies_dict)
            if cookies_saved_to_db:
                logger.info("🎉 Cookies saved to database successfully!")
                return True
            else:
                logger.warning("⚠️ Failed to save cookies to database, but have debug file")
                return False
            
        except Exception as e:
            logger.error(f"Error saving cookies: {e}")
            return False


    async def _delayed_cleanup(self, delay_seconds: int):
        """Отложенное закрытие браузера на случай, если пользователь не отсканирует QR"""
        try:
            logger.info(f"⏰ Delayed cleanup scheduled in {delay_seconds} seconds...")
            await asyncio.sleep(delay_seconds)
            
            # Проверяем, есть ли еще браузер
            if self.browser or self.context or self.page:
                logger.warning("🚨 Auto-closing browser after timeout (user did not complete authentication)")
                await self.cleanup()
            else:
                logger.info("📝 Browser already closed, delayed cleanup skipped")
                
        except asyncio.CancelledError:
            logger.info("ℹ️ Delayed cleanup cancelled (authentication completed)")
        except Exception as e:
            logger.error(f"Error in delayed cleanup: {e}")

    async def cleanup(self):
        """Очистка ресурсов и отписка от событий"""
        try:
            # Отписываемся от событий браузера
            if self.page:
                try:
                    # Очищаем все event listeners
                    self.page.remove_all_listeners("framenavigated")
                    self.page.remove_all_listeners("response")
                    self.page.remove_all_listeners("console")
                    self.page.remove_all_listeners("dialog")
                    logger.debug("Page event listeners removed")
                except Exception as e:
                    logger.debug(f"Error removing page listeners: {e}")
                    
            if self.context:
                await self.context.close()
                logger.debug("Browser context closed")
            if self.browser:
                await self.browser.close()
                logger.debug("Browser closed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            # Обнуляем ссылки
            self.page = None
            self.context = None
            self.browser = None
            logger.info("Cleanup completed")
    
    async def open_browser_with_cookies(self, cookies: list, url: str) -> Dict[str, Any]:
        """Открытие браузера с загруженными куками"""
        try:
            logger.info(f"🌍 Opening browser with {len(cookies)} cookies for {url}")
            
            # Инициализируем браузер в видимом режиме
            self.headless = False  # Видимый браузер для покупок
            await self._init_browser()
            
            # Преобразуем куки в формат Playwright
            playwright_cookies = []
            for cookie in cookies:
                playwright_cookie = {
                    "name": cookie["name"],
                    "value": cookie["value"],
                    "domain": cookie.get("domain", ".lavka.yandex.ru"),
                    "path": cookie.get("path", "/"),
                    "secure": cookie.get("secure", False),
                    "httpOnly": cookie.get("httpOnly", False),
                    "sameSite": cookie.get("sameSite", "Lax")
                }
                playwright_cookies.append(playwright_cookie)
            
            # Применяем куки
            await self.context.add_cookies(playwright_cookies)
            logger.info(f"✅ Applied {len(playwright_cookies)} cookies to browser")
            
            # Переходим на страницу
            await self.page.goto(url, timeout=30000)
            await self.page.wait_for_load_state('networkidle', timeout=10000)
            
            current_url = self.page.url
            logger.info(f"🌍 Browser opened successfully: {current_url}")
            
            # Не закрываем браузер - оставляем для пользователя
            return {
                "success": True,
                "message": f"Браузер открыт с {len(cookies)} куки",
                "current_url": current_url,
                "cookies_loaded": len(cookies)
            }
            
        except Exception as e:
            logger.error(f"Error opening browser with cookies: {e}")
            await self.cleanup()
            return {
                "success": False,
                "message": f"Не удалось открыть браузер: {str(e)}"
            }


# Динамическая фабрика для создания аутентификаторов
class LSDAuthenticatorFactory:
    """Фабрика для создания RPA аутентификаторов на основе конфигурации"""
    
    @classmethod
    def create(cls, lsd_name: str, lsd_config: Dict[str, Any], headless: bool = True, debug: bool = False) -> LSDAuthenticator:
        """Создание аутентификатора для конкретного ЛСД на основе auth_config"""
        
        # Получаем класс аутентификатора из конфигурации
        auth_config = lsd_config.get("auth_config", {})
        authenticator_class_name = auth_config.get("authenticator_class")
        
        if not authenticator_class_name:
            raise ValueError(f"No authenticator_class specified in auth_config for LSD: {lsd_name}")
        
        # Получаем параметры из конфигурации
        requires_headless = auth_config.get("requires_headless", True)
        requires_debug = auth_config.get("requires_debug", False)
        
        # Применяем переданные параметры или из конфигурации
        final_headless = headless if headless is not None else requires_headless
        final_debug = debug if debug is not None else requires_debug
        
        # Динамическое создание аутентификатора
        authenticator_class = cls._get_authenticator_class(authenticator_class_name)
        
        if not authenticator_class:
            raise ValueError(f"Authenticator class {authenticator_class_name} not found for LSD: {lsd_name}")
        
        # Создаем экземпляр аутентификатора
        if authenticator_class_name in ["YandexLavkaAuthenticator", "VkusVillAuthenticator"]:
            return authenticator_class(lsd_config, headless=final_headless, debug=final_debug)
        else:
            return authenticator_class(lsd_config)
    
    @classmethod
    def _get_authenticator_class(cls, class_name: str):
        """Получение класса аутентификатора по имени"""
        
        if class_name == "YandexLavkaAuthenticator":
            return YandexLavkaAuthenticator
        
        elif class_name == "VkusVillAuthenticator":
            try:
                from .vkusvill_authenticator import VkusVillAuthenticator
                return VkusVillAuthenticator
            except ImportError:
                logger.warning(f"VkusVillAuthenticator not found")
                return None
        
        elif class_name == "SamokatAuthenticator":
            try:
                from .samokat_authenticator import SamokatAuthenticator
                return SamokatAuthenticator
            except ImportError:
                logger.warning(f"SamokatAuthenticator not found")
                return None
        
        elif class_name == "PerekrestokAuthenticator":
            try:
                from .perekrestok_authenticator import PerekrestokAuthenticator
                return PerekrestokAuthenticator
            except ImportError:
                logger.warning(f"PerekrestokAuthenticator not found")
                return None
        
        elif class_name == "BaseAuthenticator":
            return LSDAuthenticator
        
        else:
            logger.error(f"Unknown authenticator class: {class_name}")
            return None


# Функция для тестирования
async def test_yandex_lavka_auth():
    """Тест авторизации в Яндекс.Лавке"""
    config = {
        "id": 2,
        "name": "yandex_lavka",
        "display_name": "Яндекс.Лавка"
    }
    
    auth = YandexLavkaAuthenticator(config)
    
    try:
        result = await auth.authenticate("+7 900 123 45 67")
        print(f"Auth result: {result}")
        
        if result.get("success"):
            print(f"QR URL: {result.get('qr_url')}")
            
            # Ждем завершения авторизации
            print("Waiting for auth completion...")
            completion = await auth.wait_for_auth_completion(timeout=60)
            print(f"Completion result: {completion}")
            
    finally:
        await auth.cleanup()


if __name__ == "__main__":
    asyncio.run(test_yandex_lavka_auth())
