"""
Унифицированные helper функции для RPA авторизации
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Больше не нужно - используем поллинг БД

async def save_page_html_dump(driver, step_id: str, reason: str = "debug") -> str:
    """Сохраняет HTML страницы для отладки
    
    Args:
        driver: Selenium WebDriver
        step_id: ID шага RPA для идентификации
        reason: Причина сохранения (debug, timeout, error)
        
    Returns:
        str: Путь к сохраненному файлу
    """
    try:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"/Users/ss/GenAI/korzinka/logs/rpa_page_dump_{step_id}_{reason}_{timestamp}.html"
        
        html_content = driver.page_source
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.warning(f"📄 Page HTML saved to: {log_file}")
        return log_file
        
    except Exception as e:
        logger.error(f"❌ Failed to save HTML dump: {e}")
        return ""

async def execute_unified_click_step(driver, wait, step: dict, step_id: str) -> bool:
    """Унифицированное выполнение клика по элементу с непрерывным поиском"""
    import time
    selectors = step.get('selectors', [])
    if not selectors:
        logger.warning(f"⚠️ No selectors for click step {step_id}")
        return False
    
    # Получаем кастомный таймаут для шага (в мс)
    step_timeout = step.get('timeout', 15000) / 1000  # Конвертируем мс в с
    logger.info(f"⏱️ Starting click step {step_id} with {step_timeout}s timeout")
    
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    
    start_time = time.time()
    
    # ПРАВИЛЬНАЯ ЛОГИКА: непрерывная проверка всех селекторов
    while True:
        current_time = time.time()
        elapsed = current_time - start_time
        
        # Проверяем общий таймаут
        if elapsed >= step_timeout:
            logger.error(f"❌ TIMEOUT after {elapsed:.2f}s: No clickable selectors found for step {step_id}")
            
            # Сохраняем HTML страницы для анализа
            await save_page_html_dump(driver, step_id, "timeout")
            
            return False
            
        # Проверяем каждый селектор БЕЗ ожидания (is_displayed + is_enabled)
        for i, selector in enumerate(selectors, 1):
            try:
                # Ищем элемент БЕЗ ожидания
                if selector.startswith('//'):
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                # Проверяем каждый найденный элемент
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        # Нашли кликабельный элемент!
                        logger.info(f"✅ FOUND clickable element in {elapsed:.2f}s: {selector}")
                        
                        try:
                            # Скролл к элементу
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                            await asyncio.sleep(0.1)
                            
                            # Пробуем обычный клик
                            try:
                                element.click()
                                total_elapsed = time.time() - start_time
                                logger.info(f"✅ CLICKED successfully in {total_elapsed:.2f}s: {selector}")
                                return True
                            except Exception as regular_click_error:
                                # Обычный клик не сработал - логируем и пробуем JS клик
                                error_str = str(regular_click_error)
                                logger.warning(f"⚠️ Regular click failed for {selector}: {regular_click_error}")
                                
                                # Сохраняем HTML при ElementClickInterceptedException
                                if 'element click intercepted' in error_str.lower():
                                    logger.error(f"🚨 ElementClickInterceptedException detected - saving HTML dump")
                                    await save_page_html_dump(driver, step_id, "click_intercepted")
                                
                                logger.info(f"🔄 Trying JavaScript click as fallback...")
                                
                                try:
                                    # Fallback на JavaScript клик с минимальным набором событий
                                    driver.execute_script("""
                                        var element = arguments[0];
                                        // Триггерим базовые события клика
                                        element.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true}));
                                        element.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true}));
                                        element.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                                    """, element)
                                    await asyncio.sleep(0.3)
                                    
                                    total_elapsed = time.time() - start_time
                                    logger.info(f"✅ JS CLICKED with events successfully in {total_elapsed:.2f}s: {selector}")
                                    return True
                                except Exception as js_click_error:
                                    logger.error(f"❌ JS click also failed for {selector}: {js_click_error}")
                                    continue
                            
                        except Exception as click_error:
                            logger.error(f"❌ Fatal error during click for {selector}: {click_error}")
                            continue
                            
            except Exception as e:
                logger.debug(f"⚠️ Error checking selector {selector}: {e}")
                continue
        
        # Небольшая пауза перед следующей итерацией
        await asyncio.sleep(0.5)  # Проверяем каждые 0.5 сек

async def execute_unified_hover_step(driver, wait, step: dict, step_id: str) -> bool:
    """Унифицированное наведение курсора на элемент"""
    import time
    selectors = step.get('selectors', [])
    if not selectors:
        logger.warning(f"⚠️ No selectors for hover step {step_id}")
        return False
    
    # Получаем кастомный таймаут для шага (в мс)
    step_timeout = step.get('timeout', 10000) / 1000  # Конвертируем мс в с
    logger.info(f"⏱️ Starting hover step {step_id} with {step_timeout}s timeout")
    
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    
    start_time = time.time()
    
    try:
        # ПРАВИЛЬНАЯ ЛОГИКА: непрерывная проверка всех селекторов
        while True:
            current_time = time.time()
            elapsed = current_time - start_time
            
            # Проверяем общий таймаут
            if elapsed >= step_timeout:
                logger.error(f"❌ TIMEOUT after {elapsed:.2f}s: No hoverable selectors found for step {step_id}")
                return False
                
            # Проверяем каждый селектор БЕЗ ожидания (is_displayed + is_enabled)
            for i, selector in enumerate(selectors, 1):
                try:
                    # Ищем элемент БЕЗ ожидания
                    if selector.startswith('//'):
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    # Проверяем каждый найденный элемент
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            # Нашли элемент для наведения!
                            logger.info(f"✅ FOUND hoverable element in {elapsed:.2f}s: {selector}")
                            
                            try:
                                # Скролл к элементу
                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                                await asyncio.sleep(0.1)
                                
                                # Наведение курсора
                                actions = ActionChains(driver)
                                actions.move_to_element(element).perform()
                                
                                total_elapsed = time.time() - start_time
                                logger.info(f"✅ HOVERED successfully in {total_elapsed:.2f}s: {selector}")
                                
                                # КЛЮЧЕВОЕ ПОПРАВЛЕНИЕ: немедленно выходим!
                                logger.info(f"✅ HOVER FUNCTION RETURNING TRUE - success!")
                                return True
                                
                            except Exception as hover_error:
                                logger.warning(f"⚠️ Hover action failed for {selector}: {hover_error}")
                                continue
                                
                except Exception as e:
                    logger.debug(f"⚠️ Error checking selector {selector}: {e}")
                    continue
            
            # Небольшая пауза перед следующей итерацией
            await asyncio.sleep(0.5)  # Проверяем каждые 0.5 сек
            
    except Exception as global_error:
        logger.error(f"❌ CRITICAL ERROR in hover step {step_id}: {global_error}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def execute_scroll_step(driver, step: dict, step_id: str) -> bool:
    """Выполнение скролла к элементу"""
    selectors = step.get('selectors', [])
    if not selectors:
        return False
    
    from selenium.webdriver.common.by import By
    
    for selector in selectors:
        try:
            if selector.startswith('//'):
                elements = driver.find_elements(By.XPATH, selector)
            else:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
            
            if elements:
                driver.execute_script("arguments[0].scrollIntoView(true);", elements[0])
                await asyncio.sleep(0.5)
                logger.info(f"✅ Scrolled to element with selector: {selector}")
                return True
                
        except Exception as e:
            logger.debug(f"⚠️ Scroll selector failed '{selector}': {e}")
            continue
    
    return False

async def execute_unified_wait_for_step(driver, wait, step: dict, step_id: str) -> bool:
    """Унифицированное ожидание появления элемента с БЫСТРЫМ поиском"""
    import time
    selectors = step.get('selectors', [])
    if not selectors:
        logger.warning(f"⚠️ No selectors for wait_for step {step_id}")
        return False
    
    # Получаем кастомный таймаут
    step_timeout = step.get('timeout', 15000) / 1000
    logger.info(f"⚡ FAST wait_for step {step_id} with {step_timeout}s timeout")
    
    from selenium.webdriver.common.by import By
    
    start_time = time.time()
    iteration = 0
    
    # БЫСТРЫЙ поиск элемента - без задержек!
    while True:
        iteration += 1
        current_time = time.time()
        elapsed = current_time - start_time
        
        # Проверяем общий таймаут
        if elapsed >= step_timeout:
            logger.error(f"❌ TIMEOUT after {elapsed:.2f}s: No elements found for wait_for step {step_id} (checked {iteration} iterations)")
            
            # Сохраняем HTML страницы для анализа
            await save_page_html_dump(driver, step_id, "timeout")
            
            return False
        
        # Проверяем каждый селектор МГНОВЕННО
        for i, selector in enumerate(selectors, 1):
            try:
                if selector.startswith('//'):
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                # Проверяем найденные элементы СРАЗУ
                for j, element in enumerate(elements, 1):
                    try:
                        if element.is_displayed():
                            logger.info(f"⚡ INSTANT SUCCESS in {elapsed:.2f}s: [{i}] {selector} (element {j})")
                            return True
                    except Exception:
                        continue
                        
            except Exception:
                continue
        
        # МИНИМАЛЬНАЯ пауза только если ничего не найдено - 0.1 сек вместо 0.5!
        await asyncio.sleep(0.1)

async def execute_unified_clear_step(driver, wait, step: dict, step_id: str) -> bool:
    """Унифицированная очистка поля ввода"""
    selectors = step.get('selectors', [])
    if not selectors:
        logger.warning(f"⚠️ No selectors for clear_and_wait step {step_id}")
        return False
    
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    
    for selector in selectors:
        try:
            if selector.startswith('//'):
                element = wait.until(EC.presence_of_element_located((By.XPATH, selector)))
            else:
                element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            
            element.clear()
            logger.info(f"✅ Cleared field with selector: {selector}")
            return True
            
        except (TimeoutException, NoSuchElementException):
            logger.debug(f"⚠️ Clear selector failed: {selector}")
            continue
    
    logger.warning(f"⚠️ Could not clear field for step {step_id}")
    return False

async def get_user_phone_number_internal(telegram_id: int) -> Optional[str]:
    """Получение номера телефона пользователя из базы данных (внутренняя)"""
    try:
        from shared.database import get_async_session
        from shared.database.models import User
        from sqlalchemy import select
        
        async for db in get_async_session():
            result = await db.execute(
                select(User.phone).where(User.telegram_id == telegram_id)
            )
            phone = result.scalar_one_or_none()
            
            if phone:
                logger.info(f"📱 Found phone number for user {telegram_id}: {phone[:3]}***{phone[-4:]}")
                return phone
            else:
                logger.error(f"❌ No phone number found for user {telegram_id}")
                return None
                
    except Exception as e:
        logger.error(f"❌ Database error getting phone number: {e}")
        return None

async def get_user_address_internal(telegram_id: int) -> Optional[str]:
    """Получение адреса пользователя из базы данных (внутренняя)"""
    try:
        from shared.database import get_async_session
        from shared.database.models import User
        from sqlalchemy import select
        
        async for db in get_async_session():
            result = await db.execute(
                select(User.address).where(User.telegram_id == telegram_id)
            )
            address = result.scalar_one_or_none()
            
            if address:
                logger.info(f"🏠 Found address for user {telegram_id}: {address[:30]}...")
                return address
            else:
                logger.error(f"❌ No address found for user {telegram_id}")
                return None
                
    except Exception as e:
        logger.error(f"❌ Database error getting address: {e}")
        return None

async def get_user_zipcode_internal(telegram_id: int) -> Optional[str]:
    """Извлечение почтового индекса из адреса пользователя"""
    try:
        address = await get_user_address_internal(telegram_id)
        
        if address and ',' in address:
            # Адрес в формате "117335, Профсоюзная 32"
            zipcode = address.split(',')[0].strip()
            
            # Проверяем, что это действительно индекс (6 цифр)
            if zipcode.isdigit() and len(zipcode) == 6:
                logger.info(f"📮 Extracted zipcode for user {telegram_id}: {zipcode}")
                return zipcode
            else:
                logger.warning(f"⚠️ Invalid zipcode format extracted: '{zipcode}'")
                return None
        else:
            logger.error(f"❌ Cannot extract zipcode from address for user {telegram_id}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error extracting zipcode: {e}")
        return None

async def get_user_apartment_internal(telegram_id: int) -> Optional[str]:
    """Получение номера квартиры пользователя из базы данных (внутренняя)"""
    try:
        from shared.database import get_async_session
        from shared.database.models import User
        from sqlalchemy import select
        
        async for db in get_async_session():
            result = await db.execute(
                select(User.apartment).where(User.telegram_id == telegram_id)
            )
            apartment = result.scalar_one_or_none()
            
            if apartment:
                logger.info(f"🏠 Found apartment for user {telegram_id}: {apartment}")
                return apartment
            else:
                logger.warning(f"⚠️ No apartment found for user {telegram_id}")
                return ""
                
    except Exception as e:
        logger.error(f"❌ Database error getting apartment: {e}")
        return ""

async def get_user_address_wo_zipcode_internal(telegram_id: int) -> Optional[str]:
    """Извлечение адреса без почтового индекса"""
    try:
        address = await get_user_address_internal(telegram_id)
        
        if address and ',' in address:
            # Адрес в формате "117335, Профсоюзная 32"
            parts = address.split(',', 1)  # Разделяем только по первой запятой
            
            if len(parts) == 2:
                zipcode_part = parts[0].strip()
                address_part = parts[1].strip()
                
                # Проверяем, что первая часть действительно индекс (6 цифр)
                if zipcode_part.isdigit() and len(zipcode_part) == 6:
                    logger.info(f"🏠 Extracted address without zipcode for user {telegram_id}: {address_part}")
                    return address_part
                else:
                    # Индекс не найден, возвращаем весь адрес
                    logger.warning(f"⚠️ No valid zipcode found, returning full address: {address}")
                    return address
            else:
                # Нет запятой после индекса
                logger.warning(f"⚠️ Address format unexpected: {address}")
                return address
        else:
            # Нет запятой - возвращаем адрес как есть
            if address:
                logger.info(f"🏠 No comma in address, returning as-is: {address}")
                return address
            else:
                logger.error(f"❌ No address found for user {telegram_id}")
                return None
            
    except Exception as e:
        logger.error(f"❌ Error extracting address without zipcode: {e}")
        return None

async def execute_unified_phone_input_step(driver, wait, step: dict, step_id: str, telegram_id: int) -> bool:
    """Унифицированный ввод номера телефона - устаревшая, используйте execute_unified_input_step"""
    return await execute_unified_input_step(driver, wait, step, step_id, telegram_id)

async def execute_unified_input_step(driver, wait, step: dict, step_id: str, telegram_id: int) -> bool:
    """
    Универсальный ввод текста с поддержкой плейсхолдеров:
    - {phone_without_7} - номер без +7
    - {phone} - полный номер с +7
    - {address} - полный адрес пользователя
    - {zipcode} - почтовый индекс (извлекается из адреса)
    - {address_wo_zipcode} - адрес без почтового индекса
    - {sms_code} - полный SMS код
    - {sms_code_digit_1}, {sms_code_digit_2}, {sms_code_digit_3}, {sms_code_digit_4} - отдельные цифры SMS кода
    
    Используется для action: "type" (быстрый ввод через send_keys)
    """
    # Получаем текст из конфига (text или value)
    text_template = step.get('text', step.get('value', ''))
    
    if not text_template:
        logger.error(f"❌ No text/value found in step {step_id}")
        return False
    
    logger.info(f"✏️ Processing input step {step_id} with template: {text_template}")
    
    # Заменяем плейсхолдеры на реальные значения
    final_text = text_template
    
    # Обработка {phone_without_7}
    if '{phone_without_7}' in final_text:
        phone = await get_user_phone_number_internal(telegram_id)
        if not phone:
            logger.error(f"❌ Cannot replace {{phone_without_7}} - no phone found")
            return False
        clean_phone = phone.replace('+7', '').replace('+', '')
        final_text = final_text.replace('{phone_without_7}', clean_phone)
        logger.info(f"📞 Replaced {{phone_without_7}} with {clean_phone[:3]}***{clean_phone[-4:]}")
    
    # Обработка {phone}
    if '{phone}' in final_text:
        phone = await get_user_phone_number_internal(telegram_id)
        if not phone:
            logger.error(f"❌ Cannot replace {{phone}} - no phone found")
            return False
        final_text = final_text.replace('{phone}', phone)
        logger.info(f"📞 Replaced {{phone}} with {phone[:3]}***{phone[-4:]}")
    
    # Обработка {address}
    if '{address}' in final_text:
        address = await get_user_address_internal(telegram_id)
        if not address:
            logger.error(f"❌ Cannot replace {{address}} - no address found")
            return False
        final_text = final_text.replace('{address}', address)
        logger.info(f"🏠 Replaced {{address}} with: {address[:50]}...")
    
    # Обработка {zipcode}
    if '{zipcode}' in final_text:
        zipcode = await get_user_zipcode_internal(telegram_id)
        if not zipcode:
            logger.error(f"❌ Cannot replace {{zipcode}} - no zipcode found")
            return False
        final_text = final_text.replace('{zipcode}', zipcode)
        logger.info(f"📮 Replaced {{zipcode}} with: {zipcode}")
    
    # Обработка {apartment}
    if '{apartment}' in final_text:
        apartment = await get_user_apartment_internal(telegram_id)
        if apartment is None:
            apartment = ""
        final_text = final_text.replace('{apartment}', apartment)
        logger.info(f"🏠 Replaced {{apartment}} with: {apartment}")
    
    # Обработка {address_wo_zipcode}
    if '{address_wo_zipcode}' in final_text:
        address_wo_zipcode = await get_user_address_wo_zipcode_internal(telegram_id)
        if not address_wo_zipcode:
            logger.error(f"❌ Cannot replace {{address_wo_zipcode}} - no address found")
            return False
        final_text = final_text.replace('{address_wo_zipcode}', address_wo_zipcode)
        logger.info(f"🏠 Replaced {{address_wo_zipcode}} with: {address_wo_zipcode[:50]}...")
    
    # Обработка {sms_code} и его цифр
    if '{sms_code' in final_text:
        sms_code = await get_user_sms_code(telegram_id)
        if not sms_code:
            logger.error(f"❌ Cannot replace {{sms_code}} placeholders - no SMS code found")
            return False
        
        # Заменяем полный код
        if '{sms_code}' in final_text:
            final_text = final_text.replace('{sms_code}', sms_code)
            logger.info(f"📱 Replaced {{sms_code}} with: {sms_code}")
        
        # Заменяем отдельные цифры (если код состоит из 4 цифр)
        if len(sms_code) >= 4:
            if '{sms_code_digit_1}' in final_text:
                final_text = final_text.replace('{sms_code_digit_1}', sms_code[0])
                logger.info(f"📱 Replaced {{sms_code_digit_1}} with: {sms_code[0]}")
            if '{sms_code_digit_2}' in final_text:
                final_text = final_text.replace('{sms_code_digit_2}', sms_code[1])
                logger.info(f"📱 Replaced {{sms_code_digit_2}} with: {sms_code[1]}")
            if '{sms_code_digit_3}' in final_text:
                final_text = final_text.replace('{sms_code_digit_3}', sms_code[2])
                logger.info(f"📱 Replaced {{sms_code_digit_3}} with: {sms_code[2]}")
            if '{sms_code_digit_4}' in final_text:
                final_text = final_text.replace('{sms_code_digit_4}', sms_code[3])
                logger.info(f"📱 Replaced {{sms_code_digit_4}} with: {sms_code[3]}")
    
    # Вводим текст в селектор
    selectors = step.get('selectors', [])
    if not selectors:
        logger.warning(f"⚠️ No selectors for input step {step_id}")
        return False
    
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    
    step_timeout = step.get('timeout', 10000) / 1000
    logger.info(f"⏱️ Starting input step {step_id} with {step_timeout}s timeout")
    
    for selector in selectors:
        try:
            if selector.startswith('//'):
                element = wait.until(EC.presence_of_element_located((By.XPATH, selector)))
            else:
                element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            
            logger.info(f"📍 Found element with selector: {selector}")
            
            # Ожидаем, пока элемент станет interactable (visible + enabled)
            try:
                element = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, selector) if selector.startswith('//') else (By.CSS_SELECTOR, selector)
                ))
                logger.info(f"✅ Element is now interactable: {selector}")
            except TimeoutException:
                logger.warning(f"⚠️ Element not interactable after waiting: {selector}")
                continue
            
            # Очистка и ввод
            try:
                element.clear()
                logger.info(f"🧹 Element cleared: {selector}")
            except Exception as clear_error:
                logger.warning(f"⚠️ Could not clear element: {clear_error}, proceeding with input anyway")
            
            element.send_keys(final_text)
            logger.info(f"✅ Successfully entered text (instant) into: {selector}")
            
            # Пауза после ввода
            wait_after = step.get('wait_after', 500) / 1000
            if wait_after > 0:
                import asyncio
                await asyncio.sleep(wait_after)
            
            return True
            
        except (TimeoutException, NoSuchElementException) as e:
            logger.warning(f"⚠️ Could not find element with selector: {selector}")
            continue
    
    logger.error(f"❌ Failed to enter text - no selectors worked")
    return False

async def execute_unified_human_input_step(driver, wait, step: dict, step_id: str, telegram_id: int) -> bool:
    """
    Посимвольный ввод текста (имитация человеческого ввода) с поддержкой плейсхолдеров.
    Вводит каждый символ отдельно и триггерит JS события для корректной работы с реактивными формами.
    
    Используется для action: "human_input"
    
    Поддерживаемые плейсхолдеры такие же как в execute_unified_input_step:
    - {phone_without_7}, {phone}, {address}, {zipcode}, {address_wo_zipcode}
    - {sms_code}, {sms_code_digit_1}, {sms_code_digit_2}, {sms_code_digit_3}, {sms_code_digit_4}
    """
    # Получаем текст из конфига (text или value)
    text_template = step.get('text', step.get('value', ''))
    
    if not text_template:
        logger.error(f"❌ No text/value found in step {step_id}")
        return False
    
    logger.info(f"✏️ Processing human_input step {step_id} with template: {text_template}")
    
    # Заменяем плейсхолдеры на реальные значения (используем ту же логику)
    final_text = text_template
    
    # Обработка {phone_without_7}
    if '{phone_without_7}' in final_text:
        phone = await get_user_phone_number_internal(telegram_id)
        if not phone:
            logger.error(f"❌ Cannot replace {{phone_without_7}} - no phone found")
            return False
        clean_phone = phone.replace('+7', '').replace('+', '')
        final_text = final_text.replace('{phone_without_7}', clean_phone)
        logger.info(f"📞 Replaced {{phone_without_7}} with {clean_phone[:3]}***{clean_phone[-4:]}")
    
    # Обработка {phone}
    if '{phone}' in final_text:
        phone = await get_user_phone_number_internal(telegram_id)
        if not phone:
            logger.error(f"❌ Cannot replace {{phone}} - no phone found")
            return False
        final_text = final_text.replace('{phone}', phone)
        logger.info(f"📞 Replaced {{phone}} with {phone[:3]}***{phone[-4:]}")
    
    # Обработка {address}
    if '{address}' in final_text:
        address = await get_user_address_internal(telegram_id)
        if not address:
            logger.error(f"❌ Cannot replace {{address}} - no address found")
            return False
        final_text = final_text.replace('{address}', address)
        logger.info(f"🏠 Replaced {{address}} with: {address[:50]}...")
    
    # Обработка {zipcode}
    if '{zipcode}' in final_text:
        zipcode = await get_user_zipcode_internal(telegram_id)
        if not zipcode:
            logger.error(f"❌ Cannot replace {{zipcode}} - no zipcode found")
            return False
        final_text = final_text.replace('{zipcode}', zipcode)
        logger.info(f"📮 Replaced {{zipcode}} with: {zipcode}")
    
    # Обработка {apartment}
    if '{apartment}' in final_text:
        apartment = await get_user_apartment_internal(telegram_id)
        if apartment is None:
            apartment = ""
        final_text = final_text.replace('{apartment}', apartment)
        logger.info(f"🏠 Replaced {{apartment}} with: {apartment}")
    
    # Обработка {address_wo_zipcode}
    if '{address_wo_zipcode}' in final_text:
        address_wo_zipcode = await get_user_address_wo_zipcode_internal(telegram_id)
        if not address_wo_zipcode:
            logger.error(f"❌ Cannot replace {{address_wo_zipcode}} - no address found")
            return False
        final_text = final_text.replace('{address_wo_zipcode}', address_wo_zipcode)
        logger.info(f"🏠 Replaced {{address_wo_zipcode}} with: {address_wo_zipcode[:50]}...")
    
    # Обработка {sms_code} и его цифр
    if '{sms_code' in final_text:
        sms_code = await get_user_sms_code(telegram_id)
        if not sms_code:
            logger.error(f"❌ Cannot replace {{sms_code}} placeholders - no SMS code found")
            return False
        
        # Заменяем полный код
        if '{sms_code}' in final_text:
            final_text = final_text.replace('{sms_code}', sms_code)
            logger.info(f"📱 Replaced {{sms_code}} with: {sms_code}")
        
        # Заменяем отдельные цифры (если код состоит из 4 цифр)
        if len(sms_code) >= 4:
            if '{sms_code_digit_1}' in final_text:
                final_text = final_text.replace('{sms_code_digit_1}', sms_code[0])
                logger.info(f"📱 Replaced {{sms_code_digit_1}} with: {sms_code[0]}")
            if '{sms_code_digit_2}' in final_text:
                final_text = final_text.replace('{sms_code_digit_2}', sms_code[1])
                logger.info(f"📱 Replaced {{sms_code_digit_2}} with: {sms_code[1]}")
            if '{sms_code_digit_3}' in final_text:
                final_text = final_text.replace('{sms_code_digit_3}', sms_code[2])
                logger.info(f"📱 Replaced {{sms_code_digit_3}} with: {sms_code[2]}")
            if '{sms_code_digit_4}' in final_text:
                final_text = final_text.replace('{sms_code_digit_4}', sms_code[3])
                logger.info(f"📱 Replaced {{sms_code_digit_4}} with: {sms_code[3]}")
    
    # Посимвольный ввод в селектор
    selectors = step.get('selectors', [])
    if not selectors:
        logger.warning(f"⚠️ No selectors for human_input step {step_id}")
        return False
    
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    
    step_timeout = step.get('timeout', 10000) / 1000
    logger.info(f"⏱️ Starting human_input step {step_id} with {step_timeout}s timeout")
    
    for selector in selectors:
        try:
            if selector.startswith('//'):
                element = wait.until(EC.presence_of_element_located((By.XPATH, selector)))
            else:
                element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            
            logger.info(f"📍 Found element with selector: {selector}")
            
            # Проверяем текущее значение поля
            current_value = element.get_attribute('value')
            logger.info(f"📝 Current field value: '{current_value}'")
            
            # ПОСИМВОЛЬНЫЙ ВВОД через симуляцию клавиатурных событий (для обхода input mask)
            logger.info(f"⌨️ Starting keyboard simulation input: {len(final_text)} chars")
            
            # Проверяем, нужно ли dispatch'ить события для автокомплита
            dispatch_events = step.get('dispatch_events', False)
            if dispatch_events:
                logger.info(f"🔔 dispatch_events enabled - will trigger input/change/keyup events after each character")
            
            # Фокусируем элемент ПЕРЕД началом ввода
            driver.execute_script("arguments[0].focus();", element)
            await asyncio.sleep(0.3)  # Даём время на фокус
            logger.info(f"🎯 Element focused, ready for input")
            
            for i, char in enumerate(final_text):
                # Симулируем реальный ввод через KeyboardEvent
                if dispatch_events:
                    # С dispatch событий для автокомплита - используем нативный setter
                    driver.execute_script("""
                        var element = arguments[0];
                        var char = arguments[1];
                        
                        // Получаем текущее значение
                        var currentValue = element.value;
                        var newValue = currentValue + char;
                        
                        // ВАЖНО: используем нативный setter для триггера React
                        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                        nativeInputValueSetter.call(element, newValue);
                        
                        // Создаем и отправляем все необходимые события
                        var inputEvent = new Event('input', { bubbles: true });
                        element.dispatchEvent(inputEvent);
                        
                        var changeEvent = new Event('change', { bubbles: true });
                        element.dispatchEvent(changeEvent);
                        
                        // Дополнительно отправляем keyup для полноты
                        var keyupEvent = new KeyboardEvent('keyup', {
                            key: char,
                            bubbles: true
                        });
                        element.dispatchEvent(keyupEvent);
                    """, element, char)
                else:
                    # Без dispatch событий (старое поведение)
                    driver.execute_script("""
                        var element = arguments[0];
                        var char = arguments[1];
                        
                        // Получаем код клавиши
                        var keyCode = char.charCodeAt(0);
                        
                        // Создаем события клавиатуры с правильными параметрами
                        var keydownEvent = new KeyboardEvent('keydown', {
                            key: char,
                            code: 'Digit' + char,
                            keyCode: keyCode,
                            which: keyCode,
                            bubbles: true,
                            cancelable: true
                        });
                        
                        var keypressEvent = new KeyboardEvent('keypress', {
                            key: char,
                            code: 'Digit' + char,
                            keyCode: keyCode,
                            which: keyCode,
                            bubbles: true,
                            cancelable: true
                        });
                        
                        var inputEvent = new InputEvent('input', {
                            data: char,
                            bubbles: true,
                            cancelable: true
                        });
                        
                        var keyupEvent = new KeyboardEvent('keyup', {
                            key: char,
                            code: 'Digit' + char,
                            keyCode: keyCode,
                            which: keyCode,
                            bubbles: true,
                            cancelable: true
                        });
                        
                        // Диспатчим события в правильном порядке
                        element.dispatchEvent(keydownEvent);
                        element.dispatchEvent(keypressEvent);
                        
                        // Устанавливаем значение
                        var currentValue = element.value;
                        element.value = currentValue + char;
                        
                        element.dispatchEvent(inputEvent);
                        element.dispatchEvent(keyupEvent);
                        
                        // Триггерим change событие
                        var changeEvent = new Event('change', { bubbles: true });
                        element.dispatchEvent(changeEvent);
                    """, element, char)
                
                # Проверяем текущее значение после ввода символа
                current_value = element.get_attribute('value')
                logger.info(f"  [{i+1}/{len(final_text)}] Simulated '{char}', field value now: '{current_value}'")
                
                # Задержка между символами для имитации человеческого ввода
                await asyncio.sleep(0.2)
            
            # Если включен dispatch_events, то события уже были отправлены после каждого символа
            # Ничего дополнительного делать не нужно
            
            logger.info(f"✅ Successfully entered text (human-like, {len(final_text)} chars) into: {selector}")
            
            # Пауза после ввода
            wait_after = step.get('wait_after', 500) / 1000
            if wait_after > 0:
                await asyncio.sleep(wait_after)
            
            return True
            
        except (TimeoutException, NoSuchElementException) as e:
            logger.warning(f"⚠️ Could not find element with selector: {selector}")
            continue
        except Exception as e:
            logger.error(f"❌ Error during human_input with selector {selector}: {e}")
            # Сохраняем HTML при ошибке
            await save_page_html_dump(driver, step_id, "error")
            continue
    
    logger.error(f"❌ Failed to enter text (human_input) - no selectors worked")
    # Сохраняем HTML при общей ошибке
    await save_page_html_dump(driver, step_id, "failed")
    return False

async def request_unified_sms_code(telegram_id: int, lsd_name: str, step: dict) -> Optional[str]:
    """Унифицированный запрос SMS кода от пользователя через Telegram - Поллинг БД"""
    try:
        prompt = step.get('prompt', f'Введите SMS код для авторизации в {lsd_name}')
        timeout = step.get('timeout', 180000) // 1000  # конвертируем мс в секунды - увеличено до 3 минут
        
        logger.info(f"📱 Requesting SMS code from user {telegram_id} via DB polling...")
        
        # Очищаем старые SMS коды в БД перед запросом
        await clear_user_sms_code(telegram_id)
        
        # Отправляем запрос в telegram-bot (с пустым session_id для совместимости)
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8001/rpa/user-input-request",
                json={
                    "telegram_id": telegram_id,
                    "message": prompt,
                    "session_id": "",  # Пустой для совместимости
                    "input_type": "sms_code",
                    "action": "request_sms_code"
                },
                timeout=10.0
            )
            
        if response.status_code != 200:
            logger.error(f"❌ Failed to send SMS request to telegram-bot: {response.status_code}")
            return None
        
        # Ожидаем получения SMS кода через поллинг БД
        logger.info(f"⏳ Waiting up to {timeout}s for SMS code via DB polling...")
        
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Проверяем БД каждую секунду
            sms_code = await get_user_sms_code(telegram_id)
            
            if sms_code:
                logger.info(f"✅ SMS code found in database from user {telegram_id}")
                # НЕ очищаем код - он нужен для следующих шагов ввода
                # await clear_user_sms_code(telegram_id)
                return sms_code
            
            # Короткая пауза перед следующей проверкой
            await asyncio.sleep(1)
        
        logger.warning(f"⏰ Timeout waiting for SMS code from user {telegram_id}")
        return None
        
    except Exception as e:
        logger.error(f"❌ Error requesting SMS code: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

async def get_user_sms_code(telegram_id: int) -> Optional[str]:
    """Получение SMS кода из БД"""
    try:
        from shared.database import get_async_session  # Прямой импорт
        from shared.database.models import User
        from sqlalchemy import select
        
        async for db in get_async_session():
            result = await db.execute(
                select(User.sms_code).where(User.telegram_id == telegram_id)
            )
            sms_code = result.scalar_one_or_none()
            
            return sms_code if sms_code else None
            
    except Exception as e:
        logger.error(f"❌ Error getting SMS code from DB: {e}")
        return None

async def clear_user_sms_code(telegram_id: int) -> bool:
    """Очистка SMS кода в БД"""
    try:
        from shared.database import get_async_session  # Прямой импорт
        from shared.database.models import User
        from sqlalchemy import update
        
        async for db in get_async_session():
            result = await db.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(sms_code=None)
            )
            await db.commit()
            
            return result.rowcount > 0
            
    except Exception as e:
        logger.error(f"❌ Error clearing SMS code from DB: {e}")
        return False

async def execute_unified_sms_input_step(driver, wait, step: dict, step_id: str, sms_code: str) -> bool:
    """Унифицированный ввод SMS кода (с поддержкой ВкусВилл селекторов)"""
    selectors = step.get('selectors', [])
    if not selectors:
        logger.warning(f"⚠️ No selectors for SMS input step {step_id}")
        return False
    
    logger.info(f"📱 UNIFIED SMS INPUT: Entering SMS code '{sms_code}' for step '{step_id}'")
    
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    
    # Расширенные селекторы для всех ЛСД (включая ВкусВилл)
    unified_sms_selectors = selectors + [
        # ВкусВилл селекторы
        "input[name='SMS']",
        "//input[@name='SMS']",
        ".VV_AuthModal20FormConfirm__SMSControl",
        "//input[contains(@class, 'VV_AuthModal20FormConfirm__SMSControl')]",
        "input[type='tel'][maxlength='6']",
        # Самокат селекторы  
        "input[type=\"text\"][inputmode=\"numeric\"][autocomplete=\"one-time-code\"]",
        "input[type=\"text\"][inputmode=\"numeric\"][autocomplete=\"one-time-code\"][pattern=\"\\d{1}\"]",
        # Универсальные селекторы
        "input[inputmode='numeric']",
        "//input[contains(@placeholder, 'код')]",
        "//input[contains(@placeholder, 'СМС')]",
        "//input[contains(@placeholder, 'sms')]"
    ]
    
    logger.info(f"🔍 Trying {len(unified_sms_selectors)} unified SMS selectors")
    
    # Проверяем, нужен ли посимвольный ввод
    individual_inputs = step.get('individual_inputs', False)
    
    # Автоматическое определение individual_inputs по селекторам
    if not individual_inputs:
        # Проверяем селекторы на признаки отдельных полей для каждой цифры
        individual_indicators = ['code1', 'code2', 'code3', 'code4', 'digit', '[1]', '[2]', '[3]', '[4]']
        for selector in unified_sms_selectors:
            if any(indicator in selector for indicator in individual_indicators):
                individual_inputs = True
                logger.info(f"📱 Автоматически определили individual_inputs=True по селектору: {selector}")
                break
    
    if individual_inputs:
        # Посимвольный ввод для отдельных полей (Пятерочка, Самокат)
        logger.info(f"📱 Using individual character input for SMS code: {sms_code}")
        
        # Начинаем с первого поля из селекторов
        first_field_found = None
        first_field_selector = None
        
        # Находим первое поле среди селекторов из конфига
        for selector in selectors:  # Используем селекторы из конфига, не unified
            try:
                if selector.startswith('//'):
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        first_field_found = element
                        first_field_selector = selector
                        logger.info(f"📱 Найдено первое поле SMS: {selector}")
                        break
                        
                if first_field_found:
                    break
                    
            except Exception as e:
                logger.debug(f"⚠️ Ошибка поиска по селектору {selector}: {e}")
                continue
        
        if not first_field_found:
            logger.error("❌ Не найдено первое поле для SMS кода")
            return False
        
        # Теперь вводим по одному символу в каждое поле
        for i, char in enumerate(sms_code):
            try:
                # Генерируем селектор для i-го поля
                if 'code1' in first_field_selector:
                    # Пятерочка стиль: code1, code2, code3, code4
                    field_num = i + 1
                    if '#code1' in first_field_selector:
                        current_selector = f"input#code{field_num}"
                    else:
                        current_selector = f"input[name='code{field_num}']"
                else:
                    # Общий случай - ищем по индексу
                    current_selector = selectors[min(i, len(selectors) - 1)]
                
                logger.info(f"📱 Вводим символ '{char}' в поле {i+1}: {current_selector}")
                
                # Находим текущее поле
                if current_selector.startswith('//'):
                    field_elements = driver.find_elements(By.XPATH, current_selector)
                else:
                    field_elements = driver.find_elements(By.CSS_SELECTOR, current_selector)
                
                field_found = False
                for field_element in field_elements:
                    if field_element.is_displayed() and field_element.is_enabled():
                        # Очищаем поле и вводим символ
                        field_element.clear()
                        field_element.send_keys(char)
                        
                        # Проверяем успешность ввода
                        actual_value = field_element.get_attribute('value')
                        if actual_value == char:
                            logger.info(f"✅ Символ '{char}' успешно введен в поле {i+1}")
                            field_found = True
                            break
                        else:
                            logger.warning(f"⚠️ Ожидали '{char}', получили '{actual_value}' в поле {i+1}")
                
                if not field_found:
                    logger.error(f"❌ Не удалось найти поле {i+1} для символа '{char}'")
                    return False
                
                # Пауза между символами
                await asyncio.sleep(0.3)
                
            except Exception as e:
                logger.error(f"❌ Ошибка ввода символа '{char}': {e}")
                return False
        
        logger.info(f"✅ Успешно введен SMS код по символям")
        return True
    
    else:
        # Обычный ввод в одно поле (ВкусВилл и другие)
        for i, selector in enumerate(unified_sms_selectors, 1):
            try:
                logger.info(f"📱 [{i}] Trying SMS selector: {selector}")
                
                # Найти элемент
                if selector.startswith('//'):
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                if not elements:
                    logger.debug(f"   ❌ No elements found with selector: {selector}")
                    continue
                    
                logger.info(f"   ✅ Found {len(elements)} elements with selector: {selector}")
                
                # Пробуем каждый найденный элемент
                for j, element in enumerate(elements, 1):
                    try:
                        # Проверяем видимость и доступность
                        if not element.is_displayed():
                            logger.debug(f"   [{j}] Element not visible, skipping")
                            continue
                            
                        if not element.is_enabled():
                            logger.debug(f"   [{j}] Element not enabled, skipping")
                            continue
                        
                        logger.info(f"   [{j}] Element is visible and enabled - attempting input")
                        
                        # Скролл к элементу
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                        await asyncio.sleep(0.3)
                        
                        # Фокус на элемент
                        element.click()
                        await asyncio.sleep(0.2)
                        
                        # Очистка поля
                        element.clear()
                        await asyncio.sleep(0.2)
                        
                        # Ввод SMS кода
                        element.send_keys(sms_code)
                        await asyncio.sleep(0.5)
                        
                        # Проверка успешности ввода
                        current_value = element.get_attribute('value')
                        logger.info(f"   📝 Input result: expected='{sms_code}', actual='{current_value}'")
                        
                        if current_value == sms_code:
                            logger.info(f"✅ UNIFIED SMS INPUT SUCCESS with selector [{i}] element [{j}]: {selector}")
                            return True
                        else:
                            logger.warning(f"   ⚠️ Value mismatch, trying next element...")
                            
                    except Exception as element_error:
                        logger.warning(f"   ❌ Error with element [{j}]: {element_error}")
                        continue
                        
            except Exception as selector_error:
                logger.warning(f"❌ Selector [{i}] failed: {selector_error}")
                continue
    
    logger.error(f"❌ UNIFIED SMS INPUT FAILED: Could not enter SMS code with any selector")
    return False

async def execute_unified_auth_verification(driver, step: dict, wait) -> bool:
    """Унифицированная проверка успешности авторизации"""
    try:
        selectors = step.get('selectors', [])
        if not selectors:
            logger.warning(f"⚠️ No selectors for auth verification")
            return False
        
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
        
        for selector in selectors:
            try:
                if selector.startswith('//'):
                    element = wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                else:
                    element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                
                logger.info(f"✅ Auth verification successful with selector: {selector}")
                return True
                
            except TimeoutException:
                logger.debug(f"⚠️ Auth verification selector failed: {selector}")
                continue
        
        logger.warning(f"⚠️ Could not verify auth success")
        return False
        
    except Exception as e:
        logger.error(f"❌ Error in auth verification: {e}")
        return False

async def execute_unified_qr_extraction_step(driver, step: dict, step_id: str, telegram_id: int) -> bool:
    """Унифицированное извлечение QR кода через новую универсальную функцию extract_qr()"""
    try:
        from universal_rpa_engine import extract_qr
        
        logger.info(f"🚀 Using universal extract_qr() function for step {step_id}")
        
        # Используем новую универсальную функцию
        result = await extract_qr(
            driver_or_page=driver,
            step=step,
            step_id=step_id,
            telegram_id=telegram_id
        )
        
        # Проверяем результат
        if result.get('status') == 'success':
            logger.info(f"✅ Universal QR extraction successful: method={result.get('method')}, engine={result.get('engine')}")
            return True
        else:
            logger.error(f"❌ Universal QR extraction failed: {result.get('message')}")
            return False
            
    except ImportError as e:
        logger.error(f"❌ Missing universal_rpa_engine module: {e}")
        logger.error("⚠️ Falling back to old QR extraction logic...")
        
        # Fallback на старую логику
        return await _execute_legacy_qr_extraction(driver, step, step_id, telegram_id)
        
    except Exception as e:
        logger.error(f"❌ Error in unified QR extraction: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def _execute_legacy_qr_extraction(driver, step: dict, step_id: str, telegram_id: int) -> bool:
    """Старая логика QR экстракции как fallback"""
    try:
        from selenium.webdriver.common.by import By
        import tempfile
        from PIL import Image
        import io
        from pyzbar import pyzbar
        
        logger.info(f"📱 Using legacy QR extraction for step {step_id}")
        
        # Классическая логика поиска QR элементов
        qr_selectors = step.get('selectors', [
            ".qr-code", ".AuthQr-code", "[data-testid='qr-code']",
            "img[alt*='QR']", "canvas", ".qr", ".auth-qr-code",
            "[class*='qr-code']", "[class*='qr']"
        ])
        
        qr_element = None
        for selector in qr_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed():
                        qr_element = element
                        logger.info(f"✅ Found QR element with selector: {selector}")
                        break
                if qr_element:
                    break
            except Exception as e:
                logger.debug(f"⚠️ QR selector failed '{selector}': {e}")
                continue
        
        if not qr_element:
            logger.error(f"❌ No QR code element found")
            return False
        
        # Создаем скриншот QR кода
        logger.info(f"📷 Taking screenshot of QR code element...")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", qr_element)
        await asyncio.sleep(1)
        
        qr_screenshot = qr_element.screenshot_as_png
        qr_image = Image.open(io.BytesIO(qr_screenshot))
        
        # Распознаем QR код
        qr_codes = pyzbar.decode(qr_image)
        if not qr_codes:
            # Попробуем улучшить изображение
            qr_image = qr_image.convert('L')
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(qr_image)
            qr_image = enhancer.enhance(2.0)
            qr_codes = pyzbar.decode(qr_image)
            
        if not qr_codes:
            logger.error("❌ Could not decode QR code from image")
            return False
        
        qr_data = qr_codes[0].data.decode('utf-8')
        logger.info(f"✅ Legacy QR code decoded: {qr_data[:50]}...")
        
        # Отправляем ссылку пользователю
        success, message_id = await send_qr_link_to_user(
            telegram_id, qr_data, step.get('prompt', 'Пройдите по ссылке для авторизации')
        )
        
        if success:
            logger.info(f"✅ Legacy QR link sent successfully, message_id={message_id}")
            
            # Сохраняем message_id для последующего удаления
            if message_id:
                from main import qr_message_ids
                qr_message_ids[telegram_id] = message_id
                logger.info(f"💾 Saved QR message_id {message_id} for user {telegram_id}")
            
            return True
        else:
            logger.error("❌ Failed to send legacy QR link")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error in legacy QR extraction: {e}")
        return False

async def send_qr_link_to_user(telegram_id: int, qr_link: str, prompt: str) -> tuple[bool, int | None]:
    """Отправляет QR ссылку пользователю через Telegram (обновленный endpoint)
    
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
                "action": "qr_code_extracted",
                "message": f"Для авторизации пройдите по ссылке\n{qr_link}"
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

async def execute_unified_iframe_step(driver, wait, step: dict, step_id: str) -> bool:
    """Унифицированное переключение на iframe"""
    import time
    selectors = step.get('selectors', [])
    if not selectors:
        logger.warning(f"⚠️ No selectors for iframe step {step_id}")
        return False
    
    step_timeout = step.get('timeout', 10000) / 1000  # Конвертируем мс в с
    logger.info(f"🔲 Starting iframe switch step {step_id} with {step_timeout}s timeout")
    
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    
    start_time = time.time()
    
    # Сначала возвращаемся к основному контенту (на всякий случай)
    try:
        driver.switch_to.default_content()
        logger.info("🔄 Switched to default content")
    except Exception as e:
        logger.debug(f"⚠️ Error switching to default content: {e}")
    
    # Ищем iframe
    while True:
        current_time = time.time()
        elapsed = current_time - start_time
        
        if elapsed >= step_timeout:
            logger.error(f"❌ TIMEOUT after {elapsed:.2f}s: No iframe found for step {step_id}")
            return False
        
        for i, selector in enumerate(selectors, 1):
            try:
                logger.info(f"🔍 [{i}] Trying iframe selector: {selector}")
                
                if selector.startswith('//'):
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                logger.info(f"   Found {len(elements)} iframe elements")
                
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: если нашли iframe элементы, сразу пробуем переключиться
                if len(elements) > 0:
                    for j, iframe_element in enumerate(elements, 1):
                        try:
                            if iframe_element.is_displayed():
                                logger.info(f"   [{j}] Iframe is visible, attempting switch...")
                                
                                # Переключаемся на iframe
                                try:
                                    driver.switch_to.frame(iframe_element)
                                except Exception as switch_err:
                                    # Обрабатываем stale element - повторяем поиск
                                    if "stale element" in str(switch_err).lower():
                                        logger.debug(f"   [{j}] Stale element detected, will retry in next iteration")
                                        continue
                                    else:
                                        raise
                                
                                # Проверяем успешность переключения
                                await asyncio.sleep(0.3)
                                
                                # Проверяем, что мы внутри iframe (ищем body)
                                try:
                                    body = driver.find_element(By.TAG_NAME, "body")
                                    if body:
                                        total_elapsed = time.time() - start_time
                                        logger.info(f"✅ SWITCHED to iframe successfully in {total_elapsed:.2f}s: {selector} (element {j})")
                                        # НЕМЕДЛЕННО ВЫХОДИМ ИЗ ФУНКЦИИ!
                                        return True
                                except Exception as body_check_error:
                                    logger.debug(f"   ⚠️ Body check failed: {body_check_error}")
                                    # Возвращаемся к основному контенту и пробуем следующий
                                    driver.switch_to.default_content()
                                    continue
                            else:
                                logger.debug(f"   [{j}] Iframe not visible")
                                
                        except Exception as switch_error:
                            logger.warning(f"   ❌ Error switching to iframe [{j}]: {switch_error}")
                            # Возвращаемся к основному контенту
                            try:
                                driver.switch_to.default_content()
                            except:
                                pass
                            continue
                        
            except Exception as selector_error:
                logger.debug(f"⚠️ Iframe selector [{i}] failed: {selector_error}")
                continue
        
        # Пауза перед следующей итерацией (уменьшена до 0.2с для быстрого реагирования)
        await asyncio.sleep(0.2)

async def execute_unified_iframe_back_step(driver, wait, step: dict, step_id: str) -> bool:
    """Унифицированное возвращение к основному контенту из iframe"""
    logger.info(f"🔄 Switching back to main content for step {step_id}")
    
    try:
        # Переключаемся на основной контент
        driver.switch_to.default_content()
        
        # Небольшая пауза для стабильности
        await asyncio.sleep(0.5)
        
        # Проверяем, что мы в основном контенте (ищем body)
        try:
            from selenium.webdriver.common.by import By
            body = driver.find_element(By.TAG_NAME, "body")
            if body:
                logger.info(f"✅ Successfully switched back to main content")
                return True
        except Exception as body_check_error:
            logger.warning(f"⚠️ Main content body check failed: {body_check_error}")
            # Возвращаем True всё равно, т.к. switch_to.default_content() обычно работает
            return True
            
    except Exception as e:
        logger.warning(f"⚠️ Error switching back to main content: {e}")
        # Не критичная ошибка, возвращаем True
        return True

async def execute_save_address_step(driver, step: dict, step_id: str, telegram_id: int) -> bool:
    """
    Новый action: save_address
    Извлекает адрес доставки по селекторам из конфига и сохраняет в user_sessions.default_delivery_address
    """
    try:
        logger.info(f"🏠 Executing save_address step {step_id} for user {telegram_id}")
        
        # Получаем настройки из конфига step
        address_config = step.get('address', {})
        if not address_config:
            logger.error(f"❌ No address configuration found in step {step_id}")
            return False
        
        from selenium.webdriver.common.by import By
        
        # Извлекаем части адреса по селекторам
        address_parts = []
        
        for selector_name, selector_xpath in address_config.items():
            try:
                logger.info(f"🔍 Looking for {selector_name} with selector: {selector_xpath}")
                
                # Ищем элементы по XPath
                elements = driver.find_elements(By.XPATH, selector_xpath)
                
                if elements:
                    # Берем первый видимый элемент
                    for element in elements:
                        if element.is_displayed():
                            element_text = element.text.strip()
                            if element_text:
                                address_parts.append(element_text)
                                logger.info(f"✅ Found {selector_name}: '{element_text}'")
                                break
                    else:
                        logger.warning(f"⚠️ No visible elements found for {selector_name}")
                else:
                    logger.warning(f"⚠️ No elements found for {selector_name} with selector: {selector_xpath}")
                    
            except Exception as e:
                logger.error(f"❌ Error extracting {selector_name}: {e}")
                continue
        
        if not address_parts:
            logger.error(f"❌ No address parts extracted for step {step_id}")
            return False
        
        # Объединяем части адреса через пробел
        user_address = ' '.join(address_parts)
        logger.info(f"🏠 Assembled address: '{user_address}'")
        
        # Сохраняем адрес в базу данных
        success = await save_user_address_to_db(telegram_id, user_address, step.get('lsd_config_id'))
        
        if success:
            logger.info(f"✅ Successfully saved address for user {telegram_id}: {user_address}")
            return True
        else:
            logger.error(f"❌ Failed to save address to database")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error in save_address step {step_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def save_user_address_to_db(telegram_id: int, address: str, lsd_config_id: int = None) -> bool:
    """
    Сохраняет адрес пользователя в таблицу user_sessions
    """
    try:
        from shared.database import get_async_session  # Прямой импорт
        from shared.database.models import UserSession
        from sqlalchemy import select, update
        
        logger.info(f"💾 Saving address for user {telegram_id}, lsd_config_id={lsd_config_id}")
        
        async for db in get_async_session():
            if lsd_config_id:
                # Если указан lsd_config_id, обновляем конкретную сессию ЛСД
                result = await db.execute(
                    select(UserSession).where(
                        UserSession.telegram_id == telegram_id,
                        UserSession.lsd_config_id == lsd_config_id
                    )
                )
                session = result.scalar_one_or_none()
                
                if session:
                    # Обновляем существующую сессию
                    session.default_delivery_address = address
                    logger.info(f"📝 Updated existing session {session.id} with address")
                else:
                    logger.warning(f"⚠️ No session found for user {telegram_id} and lsd_config_id {lsd_config_id}")
                    return False
            else:
                # Если lsd_config_id не указан, обновляем все сессии пользователя
                result = await db.execute(
                    update(UserSession)
                    .where(UserSession.telegram_id == telegram_id)
                    .values(default_delivery_address=address)
                )
                
                if result.rowcount > 0:
                    logger.info(f"📝 Updated {result.rowcount} sessions for user {telegram_id}")
                else:
                    logger.warning(f"⚠️ No sessions found for user {telegram_id}")
                    return False
            
            await db.commit()
            logger.info(f"✅ Address saved successfully: '{address}'")
            return True
            
    except Exception as e:
        logger.error(f"❌ Database error saving address: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

# Module loaded - no logging on import to avoid duplication
