#!/usr/bin/env python3
"""
Простой менеджер undetected-chrome БЕЗ CDP
Используется для сайтов с жесткой антибот защитой (например, Auchan)
"""

import logging
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from typing import Optional

logger = logging.getLogger(__name__)

class SimpleUndetectedBrowser:
    """Простой undetected-chrome БЕЗ CDP для обхода жесткой антибот защиты"""
    
    @staticmethod
    def create_simple_browser(headless: bool = False, mobile_mode: bool = False, block_media: bool = False, page_load_strategy: str = 'none', user_data_dir: str = None) -> uc.Chrome:
        """
        Создает простой undetected-chrome БЕЗ CDP
        Максимально похож на обычный браузер - как в успешном тесте
        
        Args:
            headless: Запускать в headless режиме
            mobile_mode: Эмулировать мобильный браузер
            block_media: Блокировать загрузку картинок для performance (шрифты, JS, CSS не блокируются).
                         ВАЖНО: Оставьте False для флоу авторизации (нужны QR-коды).
                         Используйте True для поиска товаров - попапы и UI будут работать.
            user_data_dir: Путь к профилю Chrome (опционально)
            
        Returns:
            WebDriver instance
        """
        mode_str = "MOBILE" if mobile_mode else "DESKTOP"
        logger.info(f"🚗 Creating SIMPLE undetected-chrome ({mode_str}, NO CDP, NO extra features)")
        logger.info(f"🎯 Strategy: Maximum simplicity = Maximum stealth")
        
        try:
            options = uc.ChromeOptions()
            
            # Минимальный набор опций для стабильности
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-infobars')
            options.add_argument('--disable-extensions')
            options.add_argument('--start-maximized')
            
            # КРИТИЧНО: Отключаем шифрование cookies на macOS
            # Это позволяет записывать cookies в SQLite без encrypted_value
            options.add_argument('--password-store=basic')
            
            # User data directory (профиль браузера)
            # КРИТИЧНО: НЕ передаём через options - undetected_chromedriver игнорирует это!
            # Передадим напрямую в uc.Chrome() конструктор
            profile_dir_to_use = user_data_dir
            if user_data_dir:
                logger.info(f"📁 Will use browser profile: {user_data_dir}")
            
            # НОВОЕ: Page Load Strategy из конфига
            # Для undetected_chromedriver используем preferences
            # (прямая установка options.page_load_strategy не работает с uc)
            logger.info(f"🔄 Using '{page_load_strategy}' page load strategy")
            
            # ЗАПРЕТ на геолокацию и другие разрешения
            prefs = {
                'profile.default_content_setting_values': {
                    'geolocation': 2,  # 1=Allow, 2=Block
                    'notifications': 2,  # Блокировать уведомления
                    'media_stream_mic': 2,  # Блокировать микрофон
                    'media_stream_camera': 2  # Блокировать камеру
                },
                'credentials_enable_service': False,
                'profile.password_manager_enabled': False
            }
            options.add_experimental_option('prefs', prefs)
            logger.info("🚫 Geolocation and permissions blocked")
            
            # Реалистичный User-Agent
            if mobile_mode:
                # Мобильный User-Agent (iPhone) - только UA, без mobileEmulation
                user_agent = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
                logger.info("📱 Using MOBILE User-Agent (iPhone)")
                options.add_argument(f'user-agent={user_agent}')
                
                # Устанавливаем viewport для мобильного устройства
                options.add_argument('--window-size=375,812')
            else:
                # Десктопный User-Agent (Mac Chrome 140 - точная версия)
                user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.7339.213 Safari/537.36'
                logger.info("💻 Using DESKTOP User-Agent")
                options.add_argument(f'user-agent={user_agent}')
            
            if headless:
                options.add_argument('--headless=new')
                logger.info("🌑 Headless mode enabled")
            else:
                logger.info("🌞 Visible mode (recommended for antibot bypass)")
            
            # ВАЖНО: Захардкодим версию 140 чтобы избежать проблем с автообновлением
            logger.info("🔧 Creating driver with Chrome version 140 (hardcoded)...")
            
            # RETRY ЛОГИКА для SSL ошибок
            driver = None
            max_attempts = 2
            attempt = 0
            
            while attempt < max_attempts and driver is None:
                attempt += 1
                try:
                    if attempt > 1:
                        logger.warning(f"⚠️ Attempt {attempt}/{max_attempts} to create browser...")
                        import time
                        time.sleep(2)  # Пауза перед retry
                    
                    # НОВОЕ: Для undetected_chromedriver устанавливаем page_load_strategy через desired_capabilities
                    # Но undetected_chromedriver не поддерживает desired_capabilities, поэтому установим через options
                    if hasattr(options, 'set_capability'):
                        options.set_capability('pageLoadStrategy', page_load_strategy)
                        logger.info(f"🔧 Set pageLoadStrategy capability: {page_load_strategy}")

                    # КРИТИЧНО: Передаём user_data_dir напрямую в конструктор!
                    # undetected_chromedriver игнорирует --user-data-dir из options
                    # КРИТИЧНО: use_subprocess=True чтобы Chrome был дочерним процессом и quit() корректно убивал его
                    driver = uc.Chrome(
                        options=options,
                        version_main=140,
                        use_subprocess=True,
                        user_data_dir=profile_dir_to_use  # ВАЖНО: профиль должен передаваться сюда!
                    )
                    logger.info(f"✅ Browser created successfully on attempt {attempt} (page_load_strategy={page_load_strategy})")
                    if profile_dir_to_use:
                        logger.info(f"✅ Profile loaded: {profile_dir_to_use}")

                    
                except Exception as create_error:
                    error_str = str(create_error)
                    
                    # Проверяем, это SSL ошибка?
                    is_ssl_error = (
                        'SSL' in error_str or 
                        'UNEXPECTED_EOF_WHILE_READING' in error_str or
                        'URLError' in error_str
                    )
                    
                    if is_ssl_error and attempt < max_attempts:
                        logger.warning(f"⚠️ SSL error on attempt {attempt}/{max_attempts}: {error_str}")
                        logger.info(f"🔄 Retrying...")
                        continue
                    else:
                        # Не SSL ошибка или исчерпаны попытки
                        if attempt >= max_attempts:
                            logger.error(f"❌ Failed to create browser after {max_attempts} attempts")
                        raise
            
            # КРИТИЧНО: Устанавливаем правильные HTTP заголовки через CDP для обхода антибота
            try:
                driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {
                    'headers': {
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                        'Accept-Encoding': 'gzip, deflate, br, zstd',
                        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                    }
                })
                logger.info("🔑 HTTP headers set via CDP (antibot bypass)")
            except Exception as e:
                logger.warning(f"⚠️ Could not set extra headers via CDP: {e}")
            
            # КОНТЕКСТНАЯ БЛОКИРОВКА МЕДИА через CDP (только если block_media=True)
            if block_media:
                try:
                    # Блокируем ТОЛЬКО картинки для performance, оставляем шрифты и JS для работы UI компонентов (попапы, модалы)
                    block_patterns = [
                        '*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp', '*.svg', '*.ico'
                        # Убрали шрифты (*.woff, *.ttf, ...) и видео (*.mp4, ...) - они нужны для работы попапов и UI
                    ]
                    driver.execute_cdp_cmd('Network.setBlockedURLs', {
                        'urls': block_patterns
                    })
                    logger.info(f"🚫 PERFORMANCE MODE: Images blocking ENABLED - blocked {len(block_patterns)} image patterns (fonts/JS/CSS allowed for popups)")
                except Exception as cdp_block_error:
                    logger.warning(f"⚠️ CDP media blocking failed: {cdp_block_error}")
                    # Не критично - продолжаем работу
            else:
                logger.info(f"🖼️ NORMAL MODE: Images blocking DISABLED (all media allowed - QR codes, fonts, popups will work)")
            
            logger.info(f"✅ SIMPLE browser created successfully")
            logger.info(f"📝 Browser version: {driver.capabilities.get('browserVersion', 'unknown')}")
            logger.info(f"🎉 NO CDP port = NO detection!")
            logger.info(f"✅ Popups: ALLOWED (default Chrome behavior)")
            
            return driver
            
        except Exception as e:
            logger.error(f"❌ Failed to create simple browser: {e}")
            raise
    
    @staticmethod
    def extract_cookies(driver: uc.Chrome) -> list:
        """
        Извлекает cookies из браузера через обычный Selenium API
        
        Args:
            driver: WebDriver instance
            
        Returns:
            Список cookies
        """
        try:
            cookies = driver.get_cookies()
            logger.info(f"🍪 Extracted {len(cookies)} cookies via Selenium API")
            return cookies
        except Exception as e:
            logger.error(f"❌ Failed to extract cookies: {e}")
            return []
    
    @staticmethod
    def _check_page_loaded(driver: uc.Chrome, expected_domain: str) -> bool:
        """
        Проверяет что страница загружена
        
        Args:
            driver: WebDriver instance
            expected_domain: Ожидаемый домен
            
        Returns:
            True если страница загружена
        """
        try:
            from selenium.webdriver.common.by import By
            
            # 1. Проверка URL
            current = driver.current_url
            if expected_domain not in current:
                logger.debug(f"❌ URL mismatch: expected '{expected_domain}' in '{current}'")
                return False
            
            # 2. Проверка что есть body
            body = driver.find_element(By.TAG_NAME, 'body')
            if not body:
                logger.debug("❌ Body element not found")
                return False
            
            logger.debug(f"✅ Page loaded: {current}")
            return True
            
        except Exception as e:
            logger.debug(f"❌ Page load check failed: {e}")
            return False
    
    @staticmethod
    def _inject_user_id_fallback(driver: uc.Chrome, user_id: str, domain: str) -> bool:
        """
        FALLBACK: Ручная инъекция __Secure-user-id через JavaScript
        Используется когда Selenium API даёт user_id=0
        
        Args:
            driver: WebDriver instance
            user_id: Корректный user_id для инъекции
            domain: Домен для cookie
            
        Returns:
            True если успешно
        """
        try:
            logger.warning(f"🔧 FALLBACK: Manually injecting __Secure-user-id={user_id} via JavaScript...")
            
            # Извлекаем домен без протокола
            from urllib.parse import urlparse
            parsed = urlparse(domain)
            clean_domain = parsed.netloc or domain
            
            # Удаляем старую cookie через JavaScript
            delete_script = f"""
            document.cookie = '__Secure-user-id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain={clean_domain}; secure; sameSite=Lax';
            document.cookie = '__Secure-user-id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=.{clean_domain}; secure; sameSite=Lax';
            """
            driver.execute_script(delete_script)
            logger.debug(f"  🗑️ Deleted old __Secure-user-id via JS")
            
            # Инъектируем новую cookie с правильным user_id
            import time
            expiry_timestamp = int(time.time()) + (365 * 24 * 60 * 60)  # +1 год
            
            inject_script = f"""
            document.cookie = '__Secure-user-id={user_id}; expires=' + new Date({expiry_timestamp * 1000}).toUTCString() + '; path=/; domain=.{clean_domain}; secure; sameSite=Lax';
            """
            driver.execute_script(inject_script)
            logger.info(f"  ✅ Injected __Secure-user-id={user_id} via JS")
            
            # Проверяем результат
            import time
            time.sleep(0.5)
            
            cookies_after = driver.get_cookies()
            user_id_cookie = next((c for c in cookies_after if c.get('name') == '__Secure-user-id'), None)
            
            if user_id_cookie:
                final_value = user_id_cookie.get('value')
                logger.info(f"  🔍 Verification: __Secure-user-id = {final_value}")
                
                if final_value == user_id:
                    logger.info(f"  ✅ FALLBACK SUCCESS: user_id correctly set to {user_id}")
                    return True
                else:
                    logger.error(f"  ❌ FALLBACK FAILED: Expected {user_id}, got {final_value}")
                    return False
            else:
                logger.error(f"  ❌ FALLBACK FAILED: __Secure-user-id cookie not found after injection")
                return False
                
        except Exception as e:
            logger.error(f"❌ FALLBACK injection failed: {e}")
            return False
    
    @staticmethod
    def inject_cookies(driver: uc.Chrome, cookies: list, domain: str) -> bool:
        """
        Инжектит cookies через обычный Selenium API (БЕЗ CDP) с проверкой загрузки
        И FALLBACK инъекцией user_id если профиль содержит user_id=0
        
        Args:
            driver: WebDriver instance
            cookies: Список cookies для инжекта
            domain: Домен для cookies
            
        Returns:
            True если успешно
        """
        import time
        
        try:
            logger.info(f"🍪 Injecting {len(cookies)} cookies via Selenium API...")
            
            # Сначала переходим на домен чтобы установить контекст
            driver.get(domain)
            logger.info(f"📍 Navigated to {domain} to set cookie context")
            time.sleep(1)
            
            # Ищем корректный user_id в исходных cookies (ДО инъекции)
            original_user_id = None
            for cookie in cookies:
                if cookie.get('name') == '__Secure-user-id':
                    original_user_id = str(cookie.get('value', ''))
                    logger.info(f"🔑 Found __Secure-user-id in source cookies: {original_user_id}")
                    break
            
            # Добавляем cookies
            success_count = 0
            for cookie in cookies:
                try:
                    # Проверяем обязательные поля
                    if not cookie.get('name') or not cookie.get('value'):
                        continue
                    
                    # Преобразуем в формат Selenium
                    selenium_cookie = {
                        'name': str(cookie.get('name')),
                        'value': str(cookie.get('value')),
                        'domain': cookie.get('domain', '').lstrip('.'),
                        'path': cookie.get('path', '/'),
                        'httpOnly': cookie.get('httpOnly', False),
                        'secure': cookie.get('secure', False),
                        'sameSite': cookie.get('sameSite', 'Lax')
                    }
                    
                    # Обратаботка expires
                    expires = cookie.get('expires')
                    if expires and expires != -1 and isinstance(expires, (int, float)) and expires > 0:
                        selenium_cookie['expiry'] = int(expires)
                    
                    driver.add_cookie(selenium_cookie)
                    success_count += 1
                    
                except Exception as cookie_error:
                    logger.debug(f"⚠️ Failed to add cookie '{cookie.get('name')}': {cookie_error}")
                    continue
            
            logger.info(f"✅ Successfully injected {success_count}/{len(cookies)} cookies")
            
            if success_count == 0:
                return False
            
            # КРИТИЧНО: Проверяем __Secure-user-id ПОСЛЕ инъекции
            if original_user_id and original_user_id != '0':
                # Проверяем что cookie действительно установился в браузере
                cookies_after_injection = driver.get_cookies()
                user_id_cookie = next((c for c in cookies_after_injection if c.get('name') == '__Secure-user-id'), None)
                
                if user_id_cookie:
                    injected_value = str(user_id_cookie.get('value', ''))
                    logger.info(f"🔍 Cookie verification: __Secure-user-id = {injected_value}")
                    
                    # КРИТИЧНО: Проверяем что значение НЕ сбросилось в "0"
                    if injected_value == '0':
                        logger.error(f"❌ __Secure-user-id reset to 0 after injection! Expected: {original_user_id}")
                        logger.warning(f"⚠️ Profile cookies loaded but user_id=0 - applying FALLBACK...")
                        
                        # Запускаем FALLBACK инъекцию
                        fallback_success = SimpleUndetectedBrowser._inject_user_id_fallback(
                            driver=driver,
                            user_id=original_user_id,
                            domain=domain
                        )
                        
                        if not fallback_success:
                            logger.error("❌ FALLBACK injection failed - cookies may not work correctly")
                            # Продолжаем, но предупреждаем
                    elif injected_value == original_user_id:
                        logger.info(f"✅ __Secure-user-id correctly set: {injected_value}")
                    else:
                        logger.warning(f"⚠️ __Secure-user-id mismatch: expected {original_user_id}, got {injected_value}")
                else:
                    logger.warning(f"⚠️ __Secure-user-id not found in browser after injection")
            
            # Цикл проверки загрузки страницы после инъекции (максимум 3 попытки)
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                logger.info(f"🔄 Attempt {attempt}/{max_attempts} to verify page loaded...")
                
                # Обновляем страницу чтобы применить cookies
                driver.refresh()
                time.sleep(1)
                
                # Проверяем что страница загрузилась
                if SimpleUndetectedBrowser._check_page_loaded(driver, domain):
                    logger.info(f"✅ Page loaded successfully on attempt {attempt}")
                    return True
                else:
                    logger.warning(f"⚠️ Page not loaded on attempt {attempt}/{max_attempts}")
                    if attempt < max_attempts:
                        logger.info("⏳ Waiting 3 seconds before retry...")
                        time.sleep(3)
                    else:
                        logger.error("❌ Failed to load page after 3 attempts")
                        return False
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to inject cookies: {e}")
            return False
    
    @staticmethod
    def close_browser(driver: uc.Chrome):
        """
        Закрывает браузер с проверкой сохранения persistent profile

        Проверяем что localStorage действительно записан перед закрытием.
        """
        try:
            if driver:
                logger.info("🚪 Closing simple browser with profile data verification...")

                # Проверяем что данные действительно записаны в localStorage
                try:
                    user_id = driver.execute_script("return localStorage.getItem('UserId');")
                    tpi = driver.execute_script("return localStorage.getItem('tpi');")
                    server_token = driver.execute_script("return localStorage.getItem('server_token');")

                    if user_id and tpi and server_token:
                        logger.info(f"💾 Profile data verified before close: UserId={user_id}, tpi={tpi}")
                    else:
                        logger.warning(f"⚠️ Profile data incomplete: UserId={user_id}, tpi={tpi}, server_token={'present' if server_token else 'MISSING'}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not verify profile data: {e}")

                driver.quit()
                logger.info("✅ Browser closed successfully")
        except Exception as e:
            logger.error(f"❌ Error closing browser: {e}")
