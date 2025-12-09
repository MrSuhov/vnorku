#!/usr/bin/env python3
"""
ИСПРАВЛЕННЫЙ Selenium-based браузер менеджер с undetected-chromedriver
ИСПРАВЛЕНИЯ:
- Убрана проблема "you cannot reuse the ChromeOptions object"
- Упрощена логика создания браузера
- Оптимизирована загрузка кук для избежания "Request Header Or Cookie Too Large"
- Добавлена оптимизированная загрузка кук ПЕРЕД переходом на целевой URL
"""

import asyncio
import logging
import time
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException
import random

# Импорт настроек для использования глобальных RPA настроек
try:
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from config.settings import settings
except ImportError:
    # Fallback если не удается импортировать settings
    settings = None

logger = logging.getLogger(__name__)

class UndetectedBrowserManager:
    """ИСПРАВЛЕННЫЙ менеджер браузера с undetected-chromedriver для обхода антибот-систем"""
    
    def __init__(self, headless: bool = None, debug: bool = None):
        # Используем глобальные настройки если не переданы
        if headless is None:
            self.headless = settings.rpa_headless if settings else False
        else:
            self.headless = headless
            
        if debug is None:
            self.debug = settings.rpa_debug if settings else True
        else:
            self.debug = debug
        self.driver = None
        self.is_active = False
        self.session_id = None  # Уникальный ID сессии для отслеживания
        self.logger = logger  # Добавляем logger как атрибут класса
        
        # Добавим диагностику версий
        try:
            import undetected_chromedriver as uc_version_check
            logger.info(f"🔧 Undetected ChromeDriver module loaded from: {uc_version_check.__file__}")
            logger.info(f"🔧 Chrome headless mode: {'ON' if headless else 'OFF'}")
        except Exception as version_error:
            logger.warning(f"⚠️ Version check failed: {version_error}")

    async def check_authentication_status(self, driver) -> Dict[str, Any]:
        """
        Проверяет статус аутентификации пользователя
        """
        try:
            # Проверяем наличие элементов профиля (пользователь авторизован)
            profile_selectors = [
                "//div[contains(@class, 'ProfileButton')]//span[not(text()='Войти')]",
                "//span[text()='Профиль']",
                "//button[contains(@class, 'profile')]",
                "[data-testid='profile-button']",
                ".profile-menu",
                ".user-profile"
            ]
            
            authenticated = False
            profile_element = None
            
            for selector in profile_selectors:
                try:
                    if selector.startswith('//'):
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements:
                        profile_element = elements[0]
                        authenticated = True
                        self.logger.info(f"✅ DIAGNOSTIC: Found profile element with selector: {selector}")
                        break
                except Exception as e:
                    continue
            
            # Дополнительная проверка - ищем кнопку "Войти" (значит НЕ авторизован)
            login_selectors = [
                "//span[text()='Войти']",
                "//button[contains(text(), 'Войти')]",
                "[data-testid='login-button']",
                ".login-button"
            ]
            
            login_found = False
            for selector in login_selectors:
                try:
                    if selector.startswith('//'):
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements and elements[0].is_displayed():
                        login_found = True
                        self.logger.warning(f"❌ DIAGNOSTIC: Found login button - user NOT authenticated (selector: {selector})")
                        break
                except Exception as e:
                    continue
            
            # Финальное решение
            final_authenticated = authenticated and not login_found
            
            return {
                'authenticated': final_authenticated,
                'profile_found': authenticated,
                'login_button_found': login_found,
                'profile_element': profile_element.text if profile_element else None
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error checking authentication status: {e}")
            return {'authenticated': False, 'error': str(e)}
        
    async def create_undetected_browser(self, 
                                      profile_name: str = None, 
                                      proxy: str = None,
                                      user_data_dir: str = None) -> uc.Chrome:
        """ИСПРАВЛЕННОЕ создание undetected Chrome браузера с поддержкой профилей"""
        
        logger.info(f"🚗 Creating FIXED undetected Chrome browser (profile: {profile_name})")
        
        # Импортируем profile_manager
        try:
            from browser_profile_manager import profile_manager
        except ImportError:
            logger.warning("⚠️ Could not import profile_manager, using default settings")
            profile_manager = None
        
        # Превентивная очистка старых Chrome процессов
        try:
            await self._cleanup_chrome_processes()
        except Exception as cleanup_error:
            logger.debug(f"⚠️ Chrome cleanup warning: {cleanup_error}")
        
        try:
            logger.info("🚀 Launching FIXED undetected Chrome...")
            
            # Получаем браузерные аргументы из профиля
            if profile_manager and profile_name:
                logger.info(f"🎭 Using browser profile: {profile_name}")
                browser_args = profile_manager.get_browser_args(profile_name)
                context_options = profile_manager.get_context_options(profile_name)
                logger.info(f"🔧 Profile browser args: {len(browser_args)} arguments")
                logger.info(f"🔧 Profile context options: {len(context_options)} options")
            else:
                logger.info("🎭 Using default browser settings (no profile)")
                browser_args = None
                context_options = None
            
            # Попытка создания драйвера с SSL retry логикой
            max_download_retries = 3
            driver = None
            
            for download_attempt in range(max_download_retries):
                try:
                    logger.info(f"🔄 Download attempt {download_attempt + 1}/{max_download_retries}")
                    
                    # ИСПРАВЛЕНИЕ: КАЖДЫЙ РАЗ СОЗДАЕМ НОВЫЕ ОПЦИИ
                    options = uc.ChromeOptions()
                    
                    # Применяем опции из профиля ИЛИ стандартные
                    if browser_args:
                        logger.info(f"🎭 Applying {len(browser_args)} profile arguments")
                        for arg in browser_args:
                            options.add_argument(arg)
                    else:
                        logger.info("🎭 Applying default browser arguments")
                        # Минимальные опции для стабильности
                        default_args = [
                            '--no-sandbox',
                            '--disable-dev-shm-usage',
                            '--window-size=2560,1600',
                            '--disable-extensions',
                            '--disable-plugins',
                            '--disable-background-networking',
                            '--disable-default-apps',
                            '--no-default-browser-check',
                            '--no-first-run',
                            '--memory-pressure-off',
                            '--max_old_space_size=4096',
                            '--disable-features=Translate',
                            '--disable-translate',
                            '--disable-popup-blocking',
                            '--disable-notifications',
                            '--disable-infobars',
                            '--disable-background-timer-throttling',
                            '--disable-renderer-backgrounding',
                            '--disable-backgrounding-occluded-windows',
                            '--disable-features=TranslateUI',
                            '--disable-domain-reliability',
                            '--disable-blink-features=AutomationControlled'
                        ]
                        for arg in default_args:
                            options.add_argument(arg)
                    
                    # Применяем prefs из профиля ИЛИ стандартные
                    if context_options and 'prefs' in context_options:
                        logger.info("🎭 Applying profile prefs")
                        options.add_experimental_option('prefs', context_options['prefs'])
                    else:
                        logger.info("🎭 Applying default prefs")
                        # Настройки через prefs
                        default_prefs = {
                            'translate_enabled': False,
                            'translate.enabled': False,
                            'translate.default_target_language': 'ru',
                            'credentials_enable_service': False,
                            'profile.password_manager_enabled': False,
                            'profile.default_content_setting_values.notifications': 2,
                            'intl.accept_languages': 'ru-RU,ru,en-US,en',
                        }
                        options.add_experimental_option('prefs', default_prefs)
                    
                    # Создаем драйвер с явной версией 140
                    driver = uc.Chrome(
                        options=options,
                        headless=self.headless,
                        use_subprocess=True,
                        log_level=3,
                        version_main=140  # FIXED: явно указываем версию 140
                    )
                    
                    logger.info("✅ FIXED Undetected Chrome downloaded and launched successfully")
                    break  # Успех!
                    
                except Exception as download_error:
                    logger.warning(f"⚠️ Download attempt {download_attempt + 1} failed: {download_error}")
                    
                    if driver:
                        try:
                            driver.quit()
                        except:
                            pass
                        driver = None
                    
                    if download_attempt < max_download_retries - 1:
                        logger.info(f"🔄 Retrying download in 3 seconds...")
                        await asyncio.sleep(3)
                    else:
                        logger.error(f"❌ All download attempts failed after {max_download_retries} tries")
                        raise Exception(f"ChromeDriver download failed after {max_download_retries} attempts: {download_error}")
            
            if not driver:
                raise Exception("Driver was not created successfully")
            
            # Проверяем что браузер работает
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await asyncio.sleep(2 + attempt)
                    test_result = driver.current_url or "about:blank"
                    logger.info(f"👨‍💻 Browser test successful on attempt {attempt + 1}: {test_result}")
                    break
                except Exception as test_error:
                    logger.warning(f"⚠️ Browser test failed on attempt {attempt + 1}: {test_error}")
                    
                    if attempt < max_retries - 1:
                        logger.info(f"🔄 Retrying browser test (attempt {attempt + 2}/{max_retries}) after pause...")
                        await asyncio.sleep(3 + attempt)
                    else:
                        logger.error(f"❌ All browser test attempts failed after {max_retries} tries")
                        try:
                            driver.quit()
                        except:
                            pass
                        raise Exception(f"Browser test failed after {max_retries} attempts: {test_error}")
            
            self.driver = driver
            self.is_active = True
            
            # Применяем CDP команды блокировки медиа из профиля (если есть)
            await self._apply_cdp_resource_blocking(driver, profile_name)
            
            # КРИТИЧНО: Инжектим JavaScript для АГРЕССИВНОЙ блокировки изображений
            await self._inject_image_blocking_script(driver)
            
            return driver
            
        except Exception as e:
            logger.error(f"❌ Failed to create FIXED undetected browser: {e}")
            
            try:
                if 'driver' in locals() and driver:
                    driver.quit()
            except Exception as cleanup_error:
                logger.debug(f"⚠️ Cleanup error: {cleanup_error}")
                pass
                
            raise Exception(f"Failed to create FIXED undetected browser: {str(e)}")
    
    async def _cleanup_chrome_processes(self):
        """Очистка зависших Chrome процессов на macOS"""
        import subprocess
        
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'undetected_chromedriver'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                logger.info(f"🧽 Found {len(pids)} hanging Chrome processes, cleaning up...")
                
                for pid in pids:
                    try:
                        subprocess.run(['kill', '-9', pid], timeout=2)
                        logger.debug(f"☠️ Killed Chrome process {pid}")
                    except:
                        pass
                        
                await asyncio.sleep(1)
                
        except subprocess.TimeoutExpired:
            logger.debug("⚠️ Chrome process cleanup timed out")
        except Exception as e:
            logger.debug(f"⚠️ Chrome process cleanup failed: {e}")
    
    async def load_cookies_selenium_optimized_order(self, driver: uc.Chrome, cookies: List[Dict], base_url: str):
        """ОПТИМИЗИРОВАННАЯ загрузка кук ПЕРЕД переходом на целевой URL"""
        logger.info(f"🚀 OPTIMIZED: Loading {len(cookies)} cookies BEFORE navigating to target URL...")
        
        try:
            # Проверяем что окно браузера еще открыто
            try:
                current_url = driver.current_url
                logger.info(f"🔍 Browser status check: {current_url[:50]}...")
            except Exception as check_error:
                logger.error(f"❌ Browser window is already closed: {check_error}")
                raise Exception("Cannot load cookies - browser window closed")
            
            # ШАГИ ОПТИМИЗАЦИИ:
            domain_url = base_url.split('/')[0] + '//' + base_url.split('//')[1].split('/')[0]
            logger.info(f"🎯 Target domain: {domain_url}")
            logger.info(f"🎯 Target base_url: {base_url}")
            
            # ПРОВЕРЯЕМ: нужен ли отдельный переход на домен?
            need_separate_domain_navigation = (domain_url != base_url.rstrip('/'))
            
            if need_separate_domain_navigation:
                logger.info(f"🌐 Step 1: Navigate to domain to enable cookie injection: {domain_url}")
                try:
                    driver.get(domain_url)
                    logger.info(f"✅ Domain navigation successful")
                except Exception as nav_error:
                    logger.error(f"❌ Domain navigation failed: {nav_error}")
                    raise Exception(f"Domain navigation failed: {nav_error}")
                
                await asyncio.sleep(1)  # Короткая пауза для стабилизации
            else:
                logger.info(f"🌐 Step 1: SKIPPED - domain and target URL are the same ({base_url})")
            
            # ШАГ 2: Добавляем ВСЕ cookies (домен уже установлен)
            logger.info(f"🍪 Step 2: Adding ALL {len(cookies)} cookies to the domain...")
            valid_cookies = 0
            skipped_cookies = 0
            
            for cookie in cookies:
                try:
                    # 🔍 ДИАГНОСТИКА: проверяем каждую куку
                    logger.debug(f"🔍 Processing cookie: {cookie.get('name', 'NO_NAME')} = {str(cookie.get('value', 'NO_VALUE'))[:10]}...")
                    
                    # Проверяем обязательные поля
                    if not cookie.get('name') or not cookie.get('value'):
                        logger.warning(f"⚠️ Skipping cookie with missing name/value: name='{cookie.get('name')}', value='{str(cookie.get('value'))[:10]}...'")
                        skipped_cookies += 1
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
                    
                    # Обработка expires
                    expires = cookie.get('expires')
                    if expires and expires != -1 and isinstance(expires, (int, float)) and expires > 0:
                        selenium_cookie['expiry'] = int(expires)
                    
                    # Добавляем куку
                    driver.add_cookie(selenium_cookie)
                    valid_cookies += 1
                    
                    logger.debug(f"✅ Cookie added: {selenium_cookie['name']} ({selenium_cookie.get('domain', 'no-domain')})")
                    
                except Exception as e:
                    logger.warning(f"⚠️ ERROR processing cookie '{cookie.get('name', 'UNKNOWN')}': {e}")
                    logger.debug(f"🔍 Full cookie data: {cookie}")
                    skipped_cookies += 1
                    continue
            
            logger.info(f"✅ Successfully loaded {valid_cookies}/{len(cookies)} cookies (skipped: {skipped_cookies})")
            
            # ШАГ 3: Переход на целевой URL (только если надо)
            if need_separate_domain_navigation:
                logger.info(f"🎯 Step 3: FINAL navigation to {base_url} with pre-loaded cookies...")
                try:
                    driver.get(base_url)
                    logger.info(f"✅ Final navigation successful with cookies applied")
                except Exception as final_nav_error:
                    logger.error(f"❌ Final navigation failed: {final_nav_error}")
                    raise Exception(f"Final navigation failed: {final_nav_error}")
            else:
                # Если URL одинаковые, делаем один переход СРАЗУ на целевой URL
                logger.info(f"🎯 Step 3: SINGLE navigation to {base_url} and add cookies there...")
                try:
                    driver.get(base_url)
                    logger.info(f"✅ Single navigation to target URL successful")
                except Exception as single_nav_error:
                    logger.error(f"❌ Single navigation failed: {single_nav_error}")
                    raise Exception(f"Single navigation failed: {single_nav_error}")
                
                # НОВОЕ: ТЕПЕРЬ ДОБАВЛЯЕМ КУКИ НА УЖЕ ЗАГРУЖЕННОЙ СТРАНИЦЕ!
                logger.info(f"🍪 Step 3.5: Adding cookies AFTER navigation...")
                
                # Добавляем куки НА УЖЕ ЗАГРУЖЕННОЙ странице
                cookies_added_after = 0
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
                        
                        # Обработка expires
                        expires = cookie.get('expires')
                        if expires and expires != -1 and isinstance(expires, (int, float)) and expires > 0:
                            selenium_cookie['expiry'] = int(expires)
                        
                        # Добавляем куку
                        driver.add_cookie(selenium_cookie)
                        cookies_added_after += 1
                        
                        logger.debug(f"✅ Cookie added AFTER navigation: {selenium_cookie['name']}")
                        
                    except Exception as e:
                        logger.debug(f"⚠️ Failed to add cookie AFTER navigation '{cookie.get('name', 'UNKNOWN')}': {e}")
                        continue
                
                logger.info(f"🍪 Successfully added {cookies_added_after}/{len(cookies)} cookies AFTER navigation")
                valid_cookies = cookies_added_after  # Обновляем счетчик
                
                await asyncio.sleep(1)  # Пауза после добавления кук
            # ИСПРАВЛЕНИЕ: Убрали принудительное обновление - оно сбрасывало состояние
            logger.info("⚙️ FIXED: Skipping forced refresh to preserve cookie state...")
            # Пауза для стабилизации кук без обновления
            await asyncio.sleep(3)  # Даём время кукам стабилизироваться
            # ШАГ 4: ДИАГНОСТИКА - проверяем что куки действительно активны
            await asyncio.sleep(3)  # Даем время странице загрузиться
            
            try:
                # Получаем все активные куки из браузера
                current_cookies = driver.get_cookies()
                logger.info(f"🔍 DIAGNOSTIC: Browser has {len(current_cookies)} active cookies after navigation")
                
                # Проверяем ключевые куки авторизации
                auth_cookies = [c for c in current_cookies if any(keyword in c['name'].lower() 
                                for keyword in ['session', 'auth', 'token', 'user', 'login'])]
                               
                if auth_cookies:
                    logger.info(f"✅ DIAGNOSTIC: Found {len(auth_cookies)} authentication cookies:")
                    for cookie in auth_cookies[:3]:  # Показываем первые 3
                        logger.info(f"  🔑 {cookie['name']} = {str(cookie['value'])[:10]}... (domain: {cookie['domain']})")
                else:
                    logger.warning(f"⚠️ DIAGNOSTIC: No authentication cookies found - user may not be logged in")
                
                # Проверяем URL и title страницы
                current_url = driver.current_url
                page_title = driver.title
                logger.info(f"📍 DIAGNOSTIC: Final URL: {current_url}")
                logger.info(f"📄 DIAGNOSTIC: Page title: {page_title}")
                
                # Проверяем признаки авторизации на странице
                try:
                    # Ищем элементы профиля/имени пользователя
                    profile_selectors = [
                        "//div[contains(@class, 'ProfileButton')]//span[not(text()='Войти')]",
                        "//button[contains(@class, 'ProfileButton')]//span[not(text()='Войти')]", 
                        "//*[contains(@class, 'profile') or contains(@class, 'Profile')][not(contains(text(), 'Войти'))]",
                        "//*[contains(text(), 'Профиль')]",
                        "//*[contains(@class, 'user') or contains(@class, 'User')]"
                    ]
                    
                    profile_found = False
                    for selector in profile_selectors:
                        try:
                            from selenium.webdriver.common.by import By
                            elements = driver.find_elements(By.XPATH, selector)
                            if elements and elements[0].is_displayed():
                                element_text = elements[0].text.strip()
                                if element_text and element_text != 'Войти':
                                    logger.info(f"✅ DIAGNOSTIC: Found profile element: '{element_text}' (selector: {selector})")
                                    profile_found = True
                                    break
                        except Exception:
                            continue
                    
                    if not profile_found:
                        # Ищем кнопки "Войти" - если есть, то не авторизован
                        login_selectors = [
                            "//span[text()='Войти']",
                            "//button[contains(text(), 'Войти')]",
                            "//*[contains(text(), 'Войти')]"
                        ]
                        
                        login_found = False
                        for selector in login_selectors:
                            try:
                                elements = driver.find_elements(By.XPATH, selector)
                                if elements and elements[0].is_displayed():
                                    logger.warning(f"❌ DIAGNOSTIC: Found login button - user NOT authenticated (selector: {selector})")
                                    login_found = True
                                    break
                            except Exception:
                                continue
                        
                        if not login_found:
                            logger.info(f"🤔 DIAGNOSTIC: No clear authentication indicators found")
                    
                except Exception as auth_check_error:
                    logger.warning(f"⚠️ DIAGNOSTIC: Could not check authentication status: {auth_check_error}")
                    
            except Exception as diagnostic_error:
                logger.warning(f"⚠️ DIAGNOSTIC: Error during cookie verification: {diagnostic_error}")
            
            await asyncio.sleep(2)  # Финальная пауза
            
            logger.info(f"🎉 OPTIMIZED cookie loading completed: {valid_cookies}/{len(cookies)} cookies loaded, then navigated to target URL")
            return True
            
        except Exception as e:
            logger.error(f"❌ OPTIMIZED cookie loading failed: {e}")
            return False
    
    async def navigate_with_human_behavior(self, driver: uc.Chrome, url: str, timeout: int = 30):
        """Навигация с имитацией человеческого поведения"""
        logger.info(f"🚶 Navigating to {url} with human-like behavior...")
        
        try:
            logger.info(f"📍 Step 1: Starting navigation to {url}")
            driver.get(url)
            
            logger.info("📍 Step 2: Waiting for DOM ready state...")
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            logger.info("✅ DOM loaded successfully")
            
            # ДИАГНОСТИКА
            current_url = driver.current_url
            page_title = driver.title
            logger.info(f"📍 Current URL: {current_url}")
            logger.info(f"📄 Page title: {page_title}")
            
            try:
                body_html = driver.execute_script("return document.body ? document.body.innerHTML.length : 0;")
                logger.info(f"📏 Body HTML length: {body_html} characters")
                
                if body_html < 100:
                    logger.warning("⚠️ Very small body content - possible white screen!")
                    
            except Exception as e:
                logger.warning(f"⚠️ Could not check body content: {e}")
            
            logger.info("📍 Step 3: Critical pause for JavaScript...")
            await asyncio.sleep(5)
            
            try:
                final_body = driver.execute_script("return document.body ? document.body.innerHTML.length : 0;")
                logger.info(f"📏 FINAL body length: {final_body} characters")
                
                if final_body < 200:
                    logger.error("❌ 🎨 WHITE SCREEN DETECTED! Very small content.")
                    return False
                else:
                    logger.info("✅ Page content looks normal - no white screen")
                    
            except Exception as e:
                logger.error(f"❌ Final diagnostic failed: {e}")
                return False
            
            if final_body >= 200:
                logger.info("📍 Step 4: Simulating human behavior...")
                await self._simulate_human_behavior(driver)
            
            logger.info(f"✅ Successfully navigated to {url}")
            return True
            
        except TimeoutException:
            logger.error(f"❌ Navigation timeout to {url}")
            return False
        except Exception as e:
            logger.error(f"❌ Navigation error: {e}")
            return False
    
    async def _simulate_human_behavior(self, driver: uc.Chrome):
        """Симуляция реального человеческого поведения"""
        try:
            actions = ActionChains(driver)
            window_size = driver.get_window_size()
            
            for _ in range(random.randint(2, 5)):
                x = random.randint(100, window_size['width'] - 100)
                y = random.randint(100, window_size['height'] - 100)
                actions.move_by_offset(x - 200, y - 200).pause(random.uniform(0.1, 0.3))
            
            actions.perform()
            
            scroll_distance = random.randint(100, 500)
            driver.execute_script(f"window.scrollBy(0, {scroll_distance})")
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            driver.execute_script("window.scrollTo(0, 0)")
            await asyncio.sleep(random.uniform(0.3, 0.8))
            
            logger.debug("👤 Human behavior simulation completed")
            
        except Exception as e:
            logger.debug(f"⚠️ Human behavior simulation error: {e}")
    
    async def take_screenshot(self, driver: uc.Chrome, filename: str):
        """Создание скриншота"""
        try:
            driver.save_screenshot(filename)
            logger.info(f"📸 Screenshot saved: {filename}")
            return True
        except Exception as e:
            logger.error(f"❌ Screenshot failed: {e}")
            return False
    
    async def check_anti_bot_detection(self, driver: uc.Chrome) -> Dict[str, Any]:
        """Проверка обнаружения антибот-системами"""
        logger.info("🔍 Checking for anti-bot detection...")
        
        detection_result = {
            'detected': False,
            'indicators': [],
            'page_title': '',
            'current_url': '',
            'suspicious_elements': []
        }
        
        try:
            detection_result['page_title'] = driver.title
            detection_result['current_url'] = driver.current_url
            
            suspicious_texts = [
                'access denied', 'blocked', 'bot detected', 'captcha', 
                'verification', 'robot', 'unusual traffic',
                'доступ запрещен', 'заблокирован', 'капча', 'проверка'
            ]
            
            page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            
            for suspicious_text in suspicious_texts:
                if suspicious_text in page_text:
                    detection_result['detected'] = True
                    detection_result['indicators'].append(f"Suspicious text: {suspicious_text}")
            
            blocking_selectors = [
                "div[class*='blocked']",
                "div[class*='error']", 
                "div[class*='access-denied']",
                "#cf-wrapper",
                ".cf-error-overview"
            ]
            
            for selector in blocking_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        detection_result['detected'] = True
                        detection_result['suspicious_elements'].append(selector)
                except:
                    continue
            
            if any(keyword in detection_result['current_url'].lower() 
                   for keyword in ['blocked', 'error', 'denied', 'captcha']):
                detection_result['detected'] = True
                detection_result['indicators'].append(f"Blocking URL: {detection_result['current_url']}")
            
            if detection_result['detected']:
                logger.warning(f"🚨 Anti-bot detection found: {detection_result['indicators']}")
            else:
                logger.info("✅ No anti-bot detection found")
            
            return detection_result
            
        except Exception as e:
            logger.error(f"❌ Error checking anti-bot detection: {e}")
            detection_result['detected'] = True
            detection_result['indicators'].append(f"Detection check failed: {str(e)}")
            return detection_result
    
    async def _inject_image_blocking_script(self, driver: uc.Chrome):
        """Инжектит JavaScript для агрессивной блокировки изображений НА КАЖДОЙ СТРАНИЦЕ"""
        try:
            # JavaScript код для блокировки всех изображений
            blocking_script = """
            (function() {
                // Блокируем загрузку изображений через CSS
                if (!document.getElementById('image-blocker-style')) {
                    var style = document.createElement('style');
                    style.id = 'image-blocker-style';
                    style.innerHTML = `
                        img { display: none !important; visibility: hidden !important; opacity: 0 !important; }
                        picture { display: none !important; }
                        svg { display: none !important; }
                        [style*="background-image"] { background-image: none !important; }
                        video { display: none !important; }
                    `;
                    (document.head || document.documentElement).appendChild(style);
                }
                
                // Переопределяем Image constructor
                if (!window.__imageBlockerInstalled) {
                    var OriginalImage = window.Image;
                    window.Image = function() {
                        var img = new OriginalImage();
                        img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
                        return img;
                    };
                    
                    // Блокируем создание новых img через DOM
                    var originalCreateElement = document.createElement;
                    document.createElement = function(tagName) {
                        if (tagName && tagName.toLowerCase() === 'img') {
                            var img = originalCreateElement.call(document, 'img');
                            img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
                            return img;
                        }
                        return originalCreateElement.apply(document, arguments);
                    };
                    
                    // Блокируем setAttribute для src
                    var originalSetAttribute = Element.prototype.setAttribute;
                    Element.prototype.setAttribute = function(name, value) {
                        if (this.tagName === 'IMG' && name.toLowerCase() === 'src') {
                            value = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
                        }
                        return originalSetAttribute.call(this, name, value);
                    };
                    
                    window.__imageBlockerInstalled = true;
                    console.log('✅ Image blocking script installed');
                }
            })();
            """
            
            # КРИТИЧНО: Инжектим скрипт через CDP чтобы он применялся на КАЖДОЙ новой странице
            try:
                driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    'source': blocking_script
                })
                logger.info("🚫 Image blocking script added to ALL new pages via CDP")
                
                # Также применяем к текущей странице немедленно
                driver.execute_script(blocking_script)
                logger.info("🚫 Image blocking applied to current page")
                
            except Exception as cdp_error:
                # Fallback: только текущая страница
                logger.warning(f"⚠️ CDP injection failed: {cdp_error}, using fallback")
                driver.execute_script(blocking_script)
                logger.info("🚫 Image blocking applied via execute_script (fallback - current page only)")
                
        except Exception as e:
            logger.warning(f"⚠️ Failed to inject image blocking script: {e}")
            # Не критично - продолжаем работу
    
    async def _apply_cdp_resource_blocking(self, driver: uc.Chrome, profile_name: str = None):
        """Применяет CDP команды для блокировки медиа-ресурсов из профиля"""
        try:
            # Импортируем profile_manager
            try:
                from browser_profile_manager import profile_manager
            except ImportError:
                logger.debug("⚠️ Could not import profile_manager for CDP blocking")
                return
            
            if not profile_name:
                logger.debug("⚠️ No profile specified, skipping CDP resource blocking")
                return
            
            # Загружаем профиль
            profile_data = profile_manager.load_profile(profile_name)
            if not profile_data:
                logger.debug(f"⚠️ Profile {profile_name} not found, skipping CDP blocking")
                return
            
            # Проверяем есть ли CDP команды в профиле
            cdp_commands = profile_data.get('cdp_commands', {})
            block_patterns = cdp_commands.get('block_urls_patterns', [])
            
            if not block_patterns:
                logger.debug("⚠️ No CDP block patterns in profile, skipping")
                return
            
            logger.info(f"🚫 Applying CDP resource blocking: {len(block_patterns)} patterns")
            
            # Применяем блокировку через CDP
            try:
                driver.execute_cdp_cmd('Network.setBlockedURLs', {
                    'urls': block_patterns
                })
                logger.info(f"✅ Successfully blocked {len(block_patterns)} resource patterns via CDP")
                logger.debug(f"🚫 Blocked patterns: {', '.join(block_patterns[:5])}...")
            except Exception as cdp_error:
                logger.warning(f"⚠️ CDP blocking failed (might be OK for some sites): {cdp_error}")
                # Не критично - продолжаем работу
            
        except Exception as e:
            logger.warning(f"⚠️ Error applying CDP resource blocking: {e}")
            # Не критично - продолжаем работу
    
    async def close_browser(self):
        """Закрытие браузера"""
        if self.driver:
            try:
                logger.info("🚪 Closing FIXED undetected Chrome browser...")
                self.driver.quit()
                self.is_active = False
                logger.info("✅ FIXED Browser closed successfully")
            except Exception as e:
                logger.error(f"❌ Error closing FIXED browser: {e}")
            finally:
                self.driver = None
    
    def __del__(self):
        """Деструктор для автоматической очистки"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
