#!/usr/bin/env python3
"""
Универсальный модуль для извлечения QR кодов
Поддерживает как Selenium, так и Playwright
"""

import asyncio
import logging
import tempfile
import os
import base64
import io
from typing import Optional, Dict, Any, Union
from PIL import Image
from pyzbar import pyzbar

logger = logging.getLogger(__name__)

class UniversalQRExtractor:
    """Универсальный экстрактор QR кодов для любого браузерного движка"""
    
    @staticmethod
    async def extract_qr_link_universal(
        driver_or_page: Union[Any, Any],  # Selenium WebDriver или Playwright Page
        step: Dict[str, Any],
        step_id: str,
        telegram_id: int,
        engine_type: str = "selenium"  # "selenium" или "playwright"
    ) -> Dict[str, Any]:
        """
        Универсальное извлечение QR кода с поддержкой base64 изображений
        Работает как с Selenium WebDriver, так и с Playwright Page
        """
        try:
            logger.info(f"📱 Universal QR extraction for step {step_id} ({engine_type}) with base64 support")
            
            qr_link = None
            qr_found_method = None
            
            # 🆕 МЕТОД 1: Поиск base64 QR кодов в src атрибутах
            qr_link, qr_found_method = await UniversalQRExtractor._search_base64_qr_codes(
                driver_or_page, engine_type
            )
            
            # 🔄 МЕТОД 2: Классические QR элементы (скриншоты)
            if not qr_link:
                qr_link, qr_found_method = await UniversalQRExtractor._search_standard_qr_elements(
                    driver_or_page, step, engine_type
                )
            
            # 🔄 МЕТОД 3: Полный скриншот страницы (fallback)
            if not qr_link:
                qr_link, qr_found_method = await UniversalQRExtractor._search_full_page_qr(
                    driver_or_page, engine_type
                )
            
            # 📱 Отправляем QR ссылку пользователю
            if qr_link:
                success, message_id = await UniversalQRExtractor._send_qr_link_to_user(
                    telegram_id, qr_link, step.get('prompt', 'Пройдите по ссылке для авторизации')
                )
                
                if success:
                    logger.info(f"✅ Universal QR extraction successful using method: {qr_found_method}")
                    
                    # Сохраняем message_id для последующего удаления
                    if message_id:
                        try:
                            # Используем асинхронную функцию из main.py
                            from main import save_qr_message_id
                            await save_qr_message_id(telegram_id, message_id)
                        except Exception as e:
                            logger.error(f"❌ Error saving QR message_id: {e}")
                            import traceback
                            logger.error(traceback.format_exc())
                    
                    return {
                        'status': 'success',
                        'qr_link': qr_link,
                        'method': qr_found_method,
                        'engine': engine_type,
                        'message': f'QR код найден методом {qr_found_method} и отправлен в бот'
                    }
                else:
                    logger.error(f"❌ Failed to send QR link to user")
                    return {'status': 'error', 'message': 'Failed to send QR link to user'}
            else:
                logger.error(f"❌ No QR code found using any method ({engine_type})")
                return {
                    'status': 'no_qr_found',
                    'message': f'QR код не найден ни одним из методов ({engine_type})'
                }
                
        except Exception as e:
            logger.error(f"❌ Error in universal QR extraction ({engine_type}): {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {'status': 'error', 'message': str(e)}
    
    @staticmethod
    async def _search_base64_qr_codes(driver_or_page, engine_type: str) -> tuple[Optional[str], Optional[str]]:
        """Поиск base64 QR кодов в src атрибутах изображений"""
        try:
            logger.info(f"🔍 Method 1: Searching for base64 QR codes in img src attributes ({engine_type})...")
            
            # Селекторы для поиска изображений с base64 QR кодами
            base64_qr_selectors = [
                'img[src^="data:image/png;base64"]',
                'img[src^="data:image/jpeg;base64"]', 
                'img[src^="data:image/"]',
                'img[alt*="QR"]',
                'img[alt*="qr"]',
                '.qr-code img',
                '.AuthQr-code img',
                '[class*="qr"] img'
            ]
            
            for selector in base64_qr_selectors:
                try:
                    # Получаем элементы в зависимости от движка
                    if engine_type == "selenium":
                        from selenium.webdriver.common.by import By
                        elements = driver_or_page.find_elements(By.CSS_SELECTOR, selector)
                    elif engine_type == "playwright":
                        elements = await driver_or_page.query_selector_all(selector)
                    else:
                        raise ValueError(f"Unknown engine type: {engine_type}")
                    
                    logger.info(f"  🎯 Found {len(elements)} elements with selector: {selector}")
                    
                    for i, element in enumerate(elements):
                        # Проверяем видимость элемента
                        is_visible = False
                        if engine_type == "selenium":
                            is_visible = element.is_displayed()
                        elif engine_type == "playwright":
                            is_visible = await element.is_visible()
                        
                        if is_visible:
                            # Получаем src атрибут
                            src = None
                            if engine_type == "selenium":
                                src = element.get_attribute('src')
                            elif engine_type == "playwright":
                                src = await element.get_attribute('src')
                            
                            if src and src.startswith('data:image/'):
                                logger.info(f"  📸 Found base64 image {i+1}: {src[:50]}...")
                                
                                # Извлекаем base64 данные
                                try:
                                    # Формат: data:image/png;base64,iVBORw0KG...
                                    header, data = src.split(',', 1)
                                    image_data = base64.b64decode(data)
                                    
                                    # Сохраняем во временный файл
                                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                                        temp_file.write(image_data)
                                        temp_image_path = temp_file.name
                                    
                                    # Декодируем QR из base64 изображения
                                    qr_link = await UniversalQRExtractor._decode_qr_from_image(
                                        temp_image_path, f"base64 image {i+1}"
                                    )
                                    
                                    # Удаляем временный файл
                                    try:
                                        os.unlink(temp_image_path)
                                    except:
                                        pass
                                    
                                    if qr_link:
                                        logger.info(f"✅ QR decoded from base64 src: {qr_link[:50]}...")
                                        return qr_link, "base64_src_attribute"
                                        
                                except Exception as decode_error:
                                    logger.debug(f"❌ Base64 decode failed for image {i+1}: {decode_error}")
                                    continue
                                    
                except Exception as e:
                    logger.debug(f"Base64 selector failed '{selector}': {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"⚠️ Base64 QR search failed ({engine_type}): {e}")
        
        return None, None
    
    @staticmethod
    async def _search_standard_qr_elements(driver_or_page, step: Dict[str, Any], engine_type: str) -> tuple[Optional[str], Optional[str]]:
        """Поиск классических QR элементов через скриншоты"""
        try:
            logger.info(f"🔍 Method 2: Searching for standard QR elements ({engine_type})...")
            
            # Классические селекторы QR элементов
            qr_selectors = step.get('selectors', [
                ".qr-code",
                ".AuthQr-code", 
                "[data-testid='qr-code']",
                "img[alt*='QR']",
                "canvas",
                ".qr",
                ".auth-qr-code",
                "[class*='qr-code']",
                "[class*='qr']"
            ])
            
            for selector in qr_selectors:
                try:
                    # Получаем элемент в зависимости от движка
                    element = None
                    if engine_type == "selenium":
                        from selenium.webdriver.common.by import By
                        elements = driver_or_page.find_elements(By.CSS_SELECTOR, selector)
                        for el in elements:
                            if el.is_displayed():
                                element = el
                                break
                    elif engine_type == "playwright":
                        element = await driver_or_page.query_selector(selector)
                        if element and not await element.is_visible():
                            element = None
                    
                    if element:
                        logger.info(f"✅ Found standard QR element with selector: {selector}")
                        
                        # Делаем скриншот элемента
                        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                            qr_screenshot_path = temp_file.name
                        
                        # Скриншот в зависимости от движка
                        if engine_type == "selenium":
                            qr_screenshot = element.screenshot_as_png
                            with open(qr_screenshot_path, 'wb') as f:
                                f.write(qr_screenshot)
                        elif engine_type == "playwright":
                            await element.screenshot(path=qr_screenshot_path)
                        
                        logger.info(f"📸 QR element screenshot: {qr_screenshot_path}")
                        
                        # Декодируем QR из скриншота
                        qr_link = await UniversalQRExtractor._decode_qr_from_image(
                            qr_screenshot_path, "standard QR element"
                        )
                        
                        # Удаляем временный файл
                        try:
                            os.unlink(qr_screenshot_path)
                        except:
                            pass
                        
                        if qr_link:
                            logger.info(f"✅ QR decoded from standard element: {qr_link[:50]}...")
                            return qr_link, "standard_element_screenshot"
                            
                except Exception as e:
                    logger.debug(f"Standard selector failed '{selector}': {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"⚠️ Standard QR element search failed ({engine_type}): {e}")
        
        return None, None
    
    @staticmethod
    async def _search_full_page_qr(driver_or_page, engine_type: str) -> tuple[Optional[str], Optional[str]]:
        """Поиск QR кода через скриншот всей страницы"""
        try:
            logger.info(f"🔍 Method 3: Full page screenshot fallback ({engine_type})...")
            
            # Ждем немного чтобы QR код полностью загрузился
            await asyncio.sleep(2)
            
            # Делаем скриншот всей страницы
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                screenshot_path = temp_file.name
            
            if engine_type == "selenium":
                driver_or_page.save_screenshot(screenshot_path)
            elif engine_type == "playwright":
                await driver_or_page.screenshot(path=screenshot_path, full_page=True)
            
            logger.info(f"📸 Full page screenshot: {screenshot_path}")
            
            # Декодируем QR код из полного скриншота
            qr_link = await UniversalQRExtractor._decode_qr_from_image(screenshot_path, "full page")
            
            # Удаляем временный файл
            try:
                os.unlink(screenshot_path)
            except:
                pass
            
            if qr_link:
                logger.info(f"✅ QR decoded from full page: {qr_link[:50]}...")
                return qr_link, "full_page_screenshot"
                
        except Exception as e:
            logger.warning(f"⚠️ Full page screenshot failed ({engine_type}): {e}")
        
        return None, None
    
    @staticmethod
    async def _decode_qr_from_image(image_path: str, source_name: str) -> Optional[str]:
        """Декодирование QR кода из изображения с несколькими методами"""
        try:
            logger.info(f"🔍 Decoding QR from {source_name}: {image_path}")
            
            # Метод 1: pyzbar
            try:
                image = Image.open(image_path)
                qr_codes = pyzbar.decode(image)
                
                if qr_codes:
                    qr_data = qr_codes[0].data.decode('utf-8')
                    logger.info(f"✅ pyzbar found QR: {qr_data[:50]}...")
                    return qr_data
                else:
                    logger.debug(f"⚠️ pyzbar: no QR codes found in {source_name}")
                    
            except Exception as e:
                logger.warning(f"⚠️ pyzbar failed on {source_name}: {e}")
            
            # Метод 2: QReader (если доступен)
            try:
                from qreader import QReader
                import numpy as np
                
                image = Image.open(image_path)
                image_array = np.array(image)
                qreader = QReader()
                decoded_text = qreader.detect_and_decode(image=image_array)
                
                if decoded_text and len(decoded_text) > 0:
                    qr_text = decoded_text[0] if isinstance(decoded_text, list) else decoded_text
                    if qr_text and isinstance(qr_text, str) and len(qr_text) > 10:
                        logger.info(f"✅ QReader found QR: {qr_text[:50]}...")
                        return qr_text
                else:
                    logger.debug(f"⚠️ QReader: no QR codes found in {source_name}")
                    
            except ImportError:
                logger.debug("⚠️ QReader not available")
            except Exception as e:
                logger.warning(f"⚠️ QReader failed on {source_name}: {e}")
            
            logger.warning(f"❌ All QR decoding methods failed for {source_name}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error in QR decoding for {source_name}: {e}")
            return None
    
    @staticmethod
    async def _send_qr_link_to_user(telegram_id: int, qr_link: str, prompt: str) -> tuple[bool, int | None]:
        """Отправка QR ссылки пользователю через Telegram
        
        Returns:
            tuple[bool, int | None]: (success, message_id)
        """
        try:
            import httpx
            
            logger.info(f"📱 Sending QR link to user {telegram_id}...")
            
            # Отправляем запрос в telegram-bot используя правильный endpoint
            async with httpx.AsyncClient() as client:
                bot_request = {
                    "telegram_id": telegram_id,
                    "qr_link": qr_link,
                    "prompt": prompt  # Используем prompt вместо message/action
                }
                
                # Пробуем сначала новый endpoint
                response = await client.post(
                    "http://localhost:8001/rpa/qr-code-extracted",
                    json=bot_request,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    logger.info("✅ QR link sent successfully via qr-code-extracted endpoint")
                    data = response.json()
                    message_id = data.get("message_id")
                    logger.info(f"🏷️ Received message_id: {message_id}")
                    return True, message_id
                elif response.status_code == 404:
                    logger.info("⚠️ qr-code-extracted endpoint not found, trying send-qr-link...")
                    
                    # Fallback на старый endpoint
                    fallback_request = {
                        "telegram_id": telegram_id,
                        "qr_link": qr_link,
                        "prompt": prompt
                    }
                    
                    response = await client.post(
                        "http://localhost:8001/rpa/send-qr-link",
                        json=fallback_request,
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        logger.info("✅ QR link sent successfully via send-qr-link endpoint")
                        data = response.json()
                        message_id = data.get("message_id")
                        logger.info(f"🏷️ Received message_id: {message_id}")
                        return True, message_id
                    else:
                        logger.error(f"❌ Both endpoints failed: {response.status_code}")
                        return False, None
                else:
                    logger.error(f"❌ Failed to send QR link: HTTP {response.status_code}")
                    return False, None
                
        except Exception as e:
            logger.error(f"❌ Error sending QR link: {e}")
            return False, None


# Удобные wrapper функции для обеих движков
async def extract_qr_with_selenium(driver, step: Dict[str, Any], step_id: str, telegram_id: int) -> Dict[str, Any]:
    """Wrapper для Selenium WebDriver"""
    return await UniversalQRExtractor.extract_qr_link_universal(
        driver, step, step_id, telegram_id, engine_type="selenium"
    )

async def extract_qr_with_playwright(page, step: Dict[str, Any], step_id: str, telegram_id: int) -> Dict[str, Any]:
    """Wrapper для Playwright Page"""
    return await UniversalQRExtractor.extract_qr_link_universal(
        page, step, step_id, telegram_id, engine_type="playwright"
    )

logger.info("📷 Universal QR Extractor loaded - supports both Selenium and Playwright!")
