"""
CDP Cookie Manager - Модуль для управления куки через Chrome DevTools Protocol
"""

import logging
from typing import List, Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

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

class CDPCookieManager:
    """Менеджер кук через Chrome DevTools Protocol для предварительной загрузки"""
    
    def __init__(self, page_load_strategy: str = 'none'):
        self.driver: Optional[webdriver.Chrome] = None
        self.injected_cookies_count = 0
        self.page_load_strategy = page_load_strategy
        logger.info(f"🔧 CDPCookieManager initialized with page_load_strategy='{page_load_strategy}'")
    
    def setup_browser_with_cdp(self, window_size: str = "2560,1600", headless: bool = None, block_media: bool = False) -> webdriver.Chrome:
        """
        Настраивает браузер с включенным CDP
        
        Args:
            window_size: Размер окна браузера
            headless: Запуск в headless режиме (если None - используем глобальную настройку RPA_HEADLESS)
            block_media: Блокировать загрузку медиа (изображения, шрифты, видео) для performance.
                         ВАЖНО: Оставьте False для флоу авторизации (нужны QR-коды).
                         Используйте True только для поиска товаров, где медиа не критично.
            
        Returns:
            Настроенный WebDriver с CDP
        """
        # Используем глобальную настройку если headless не передан
        if headless is None:
            headless = settings.rpa_headless if settings else False
            
        logger.info(f"🔧 Setting up browser with CDP enabled (headless: {headless})...")
        
        # Находим свободный порт для CDP
        import socket
        def get_free_port():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', 0))
                s.listen(1)
                port = s.getsockname()[1]
            return port
        
        cdp_port = get_free_port()
        logger.info(f"🔌 Using CDP port: {cdp_port}")
        
        options = Options()
        
        # КРИТИЧНО: используем page_load_strategy из конфига для управляемой загрузки
        options.page_load_strategy = self.page_load_strategy
        logger.info(f"🔄 Using '{self.page_load_strategy}' page load strategy")
        
        if headless:
            options.add_argument('--headless')
            logger.info("🌐 Running in HEADLESS mode (from RPA_HEADLESS=true)")
        else:
            # Для не-headless режима добавляем дополнительные параметры для видимости
            options.add_argument('--start-maximized')
            options.add_argument('--force-device-scale-factor=1')
            logger.info("🌐 Running in VISIBLE mode (from RPA_HEADLESS=false)")
            
        options.add_argument(f'--window-size={window_size}')
        options.add_argument('--disable-blink-features=AutomationControlled')
        # ИСПРАВЛЕНО: убрали --enable-automation, он включает флаг автоматизации
        options.add_argument(f'--remote-debugging-port={cdp_port}')  # Используем динамический порт
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        # Современный User-Agent Chrome 140 - точная версия как в Ашан
        options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.7339.213 Safari/537.36')
        
        # Дополнительные флаги для маскировки автоматизации (как в Ашан)
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--lang=ru-RU')
        
        # Отключаем уведомления, всплывающие окна, геолокацию и другие разрешения (как в Ашан)
        prefs = {
            "profile.default_content_setting_values": {
                "notifications": 2,  # Блокируем уведомления
                "geolocation": 2,  # Блокируем геолокацию (2 = block)
                "media_stream_mic": 2,  # Блокировать микрофон
                "media_stream_camera": 2,  # Блокировать камеру
                "popups": 0,  # Разрешаем всплывающие окна (нужны для модалок)
            },
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False
        }
        
        # КОНТЕКСТНАЯ БЛОКИРОВКА ИЗОБРАЖЕНИЙ: только если block_media=True
        if block_media:
            prefs["profile.default_content_setting_values"]["images"] = 2
            prefs["profile.managed_default_content_settings.images"] = 2
            prefs["profile.content_settings.exceptions.images"] = {}
            prefs["profile.default_content_settings.images"] = 2
            logger.info("🚫 PERFORMANCE MODE: Image blocking ENABLED in prefs")
        else:
            logger.info("🖼️ NORMAL MODE: Images ALLOWED in prefs (needed for QR codes)")
        options.add_experimental_option("prefs", prefs)
        logger.info("🚫 Permissions blocked: geolocation, notifications, camera, microphone")
        
        # Убираем признаки автоматизации (как в Ашан)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        try:
            self.driver = webdriver.Chrome(service=Service(), options=options)
            
            # КРИТИЧНО: устанавливаем page load timeout для защиты от зависаний
            self.driver.set_page_load_timeout(30)  # 30 секунд максимум на загрузку страницы
            logger.info("⏱️ Page load timeout set to 30 seconds")
            
            # Убираем webdriver property и добавляем плагины
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                
                // Добавляем плагины
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {name: 'PDF Viewer', description: 'Portable Document Format', filename: 'internal-pdf-viewer'},
                        {name: 'Chrome PDF Viewer', description: 'Portable Document Format', filename: 'internal-pdf-viewer'},
                        {name: 'Chromium PDF Viewer', description: 'Portable Document Format', filename: 'internal-pdf-viewer'},
                        {name: 'Microsoft Edge PDF Viewer', description: 'Portable Document Format', filename: 'internal-pdf-viewer'},
                        {name: 'WebKit built-in PDF', description: 'Portable Document Format', filename: 'internal-pdf-viewer'}
                    ]
                });
                
                // Улучшаем languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ru-RU', 'ru', 'en-US', 'en']
                });
                
                // КРИТИЧНО: Добавляем userAgentData для Client Hints (обход Qrator)
                Object.defineProperty(navigator, 'userAgentData', {
                    get: () => ({
                        brands: [
                            {brand: 'Chromium', version: '140'},
                            {brand: 'Not=A?Brand', version: '24'},
                            {brand: 'Google Chrome', version: '140'}
                        ],
                        mobile: false,
                        platform: 'macOS'
                    })
                });
            """)
            
            # КРИТИЧНО: Устанавливаем правильные заголовки через CDP (обход Qrator)
            self.driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {
                'headers': {
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'accept-encoding': 'gzip, deflate, br, zstd',
                    'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                    'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"macOS"',
                    'sec-fetch-dest': 'document',
                    'sec-fetch-mode': 'navigate',
                    'sec-fetch-site': 'none',
                    'sec-fetch-user': '?1',
                    'upgrade-insecure-requests': '1'
                }
            })
            logger.info("🔑 Extra HTTP headers set via CDP (Qrator bypass)")
            
            # КОНТЕКСТНАЯ БЛОКИРОВКА: инжектим JavaScript только если block_media=True
            if block_media:
                self._inject_image_blocking_script()
                logger.info("🚫 PERFORMANCE MODE: JavaScript image blocking ENABLED")
            else:
                logger.info("🖼️ NORMAL MODE: JavaScript image blocking DISABLED (QR codes will work)")
            
            logger.info(f"✅ Browser with CDP started successfully on port {cdp_port} (headless: {headless})")
            return self.driver
            
        except Exception as e:
            logger.error(f"❌ Failed to start browser with CDP (headless: {headless}): {e}")
            raise
    
    def inject_cookies_before_navigation(self, cookies: List[Dict[str, Any]], target_domain: str = "samokat.ru") -> int:
        """
        Инъектирует куки через CDP ДО навигации на сайт
        
        Args:
            cookies: Список кук для инъекции
            target_domain: Целевой домен
            
        Returns:
            Количество успешно инъектированных кук
        """
        if not self.driver:
            raise RuntimeError("Browser not initialized. Call setup_browser_with_cdp() first.")
        
        logger.info(f"🍪 Injecting {len(cookies)} cookies via CDP...")
        
        # Открываем пустую страницу для активации CDP
        self.driver.get("data:,")
        
        injected_count = 0
        failed_count = 0
        failed_details = []
        
        for cookie in cookies:
            try:
                # Подготавливаем куку для CDP
                cdp_cookie = self._prepare_cookie_for_cdp(cookie, target_domain)
                
                # Инъектируем через CDP
                self.driver.execute_cdp_cmd('Network.setCookie', cdp_cookie)
                injected_count += 1
                
                # Показываем прогресс каждые 10 кук
                if injected_count % 10 == 0:
                    logger.debug(f"   Injected {injected_count}/{len(cookies)} cookies...")
                
            except Exception as e:
                failed_count += 1
                failed_details.append({
                    'name': cookie.get('name', 'unknown'),
                    'error': str(e)[:100]
                })
                
                logger.debug(f"⚠️ Failed to inject cookie {cookie.get('name', 'unknown')}: {str(e)[:50]}")
        
        self.injected_cookies_count = injected_count
        
        logger.info(f"✅ CDP injection complete: {injected_count}/{len(cookies)} cookies injected")
        
        if failed_count > 0:
            logger.warning(f"❌ Failed to inject {failed_count} cookies")
            for fail in failed_details[:3]:  # Логируем первые 3 ошибки
                logger.debug(f"   - {fail['name']}: {fail['error']}")
        
        return injected_count
    
    def _prepare_cookie_for_cdp(self, cookie: Dict[str, Any], default_domain: str) -> Dict[str, Any]:
        """
        Подготавливает куку для CDP формата
        
        Args:
            cookie: Исходная кука
            default_domain: Домен по умолчанию
            
        Returns:
            Кука в формате CDP
        """
        cdp_cookie = {
            'name': cookie.get('name'),
            'value': cookie.get('value', ''),
        }
        
        # Обрабатываем домен
        domain = cookie.get('domain')
        if domain:
            # Убираем точку в начале домена если есть, но оставляем для субдоменов
            if domain.startswith('.') and default_domain in domain:
                cdp_cookie['domain'] = domain
            elif not domain.startswith('.') and default_domain in domain:
                cdp_cookie['domain'] = domain
            else:
                cdp_cookie['domain'] = default_domain
        else:
            cdp_cookie['domain'] = default_domain
        
        # Добавляем опциональные параметры
        if cookie.get('path'):
            cdp_cookie['path'] = cookie['path']
        else:
            cdp_cookie['path'] = '/'
            
        if 'secure' in cookie:
            cdp_cookie['secure'] = bool(cookie['secure'])
            
        if 'httpOnly' in cookie:
            cdp_cookie['httpOnly'] = bool(cookie['httpOnly'])
            
        # ИСПРАВЛЕНО: поддержка обоих форматов expires
        if 'expirationDate' in cookie:
            cdp_cookie['expires'] = float(cookie['expirationDate'])
        elif 'expiry' in cookie:
            cdp_cookie['expires'] = float(cookie['expiry'])
        
        # Дополнительные параметры для совместимости
        if 'sameSite' in cookie:
            same_site = cookie['sameSite']
            if same_site in ['Strict', 'Lax', 'None']:
                cdp_cookie['sameSite'] = same_site
        
        return cdp_cookie
    
    def _verify_page_loaded(self, expected_url: str) -> bool:
        """
        Проверяет что страница действительно загружена
        
        Args:
            expected_url: Ожидаемый URL или домен
            
        Returns:
            True если страница загружена
        """
        try:
            from selenium.webdriver.common.by import By
            from urllib.parse import urlparse
            
            # 1. Проверка что URL содержит ожидаемый домен
            current = self.driver.current_url
            expected_domain = urlparse(expected_url).netloc or expected_url
            
            if expected_domain not in current:
                logger.debug(f"❌ URL mismatch: expected '{expected_domain}' in '{current}'")
                return False
            
            # 2. Проверка что есть body элемент
            body = self.driver.find_element(By.TAG_NAME, 'body')
            if not body:
                logger.debug("❌ Body element not found")
                return False
            
            logger.debug(f"✅ Page loaded: {current}")
            return True
            
        except Exception as e:
            logger.debug(f"❌ Page load check failed: {e}")
            return False
    
    def navigate_to_site(self, url: str, wait_time: int = 1) -> bool:
        """
        Переходит на сайт после инъекции кук с проверкой загрузки
        
        Args:
            url: URL для перехода
            wait_time: Время ожидания загрузки
            
        Returns:
            True если переход успешен
        """
        if not self.driver:
            raise RuntimeError("Browser not initialized")
        
        import time
        
        try:
            logger.info(f"🌍 Navigating to {url} with pre-injected cookies...")
            
            # Цикл проверки загрузки страницы (максимум 3 попытки)
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                logger.info(f"🔄 Attempt {attempt}/{max_attempts} to load page...")
                
                # Переход на страницу
                self.driver.get(url)
                time.sleep(min(wait_time, 1))  # Минимальная пауза
                
                # Проверка что страница загрузилась
                if self._verify_page_loaded(url):
                    logger.info(f"✅ Page loaded successfully on attempt {attempt}")
                    logger.info(f"   Current URL: {self.driver.current_url}")
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
            logger.error(f"❌ Navigation failed: {e}")
            return False
    
    def check_cookie_authentication(self) -> Dict[str, Any]:
        """
        Проверяет авторизацию НА ОСНОВЕ КУК (не визуальных элементов)
        Поддерживает разные ЛСД с разными схемами авторизации
        
        Returns:
            {
                'is_authenticated': bool,
                'has_guest_marker': bool,
                'user_id': str или None,
                'issues': List[str]  # список проблем
            }
        """
        if not self.driver:
            raise RuntimeError("Browser not initialized")
        
        results = {
            'is_authenticated': False,
            'has_guest_marker': False,
            'user_id': None,
            'issues': [],
            'auth_markers': []  # найденные маркеры авторизации
        }
        
        try:
            browser_cookies = self.driver.get_cookies()
            
            for cookie in browser_cookies:
                name = cookie.get('name', '')
                value = str(cookie.get('value', ''))
                
                # === УНИВЕРСАЛЬНЫЕ ГОСТЕВЫЕ МАРКЕРЫ ===
                
                # Озон: guest=true
                if name == 'guest' and value == 'true':
                    results['has_guest_marker'] = True
                    results['issues'].append('guest=true cookie found')
                
                # Метро: isUnauthorizedWithDraftNull=1 (гостевой)
                if name == 'isUnauthorizedWithDraftNull' and value == '1':
                    results['has_guest_marker'] = True
                    results['issues'].append('isUnauthorizedWithDraftNull=1 (guest)')
                
                # === МАРКЕРЫ АВТОРИЗАЦИИ ===
                
                # Озон: __Secure-user-id
                if name == '__Secure-user-id':
                    results['user_id'] = value
                    # КРИТИЧНО: Проверяем "0" ДО проверки на непустоту ("0" = True в Python!)
                    if value == '0':
                        results['issues'].append('__Secure-user-id=0 (guest)')
                    elif value:  # Любое непустое значение != "0"
                        results['auth_markers'].append(f'ozon_user_id={value}')
                
                # Метро: isUnauthorizedWithDraftNull=0 (авторизован)
                if name == 'isUnauthorizedWithDraftNull' and value == '0':
                    results['auth_markers'].append('metro_authorized')
                
                # Универсальные токены авторизации
                if name in ['exp_auth', '_userGUID', 'auth_token', 'access_token']:
                    if value and len(value) > 10:  # не пустой токен
                        results['auth_markers'].append(f'{name}=present')
            
            # === ИТОГОВАЯ ОЦЕНКА АВТОРИЗАЦИИ ===
            
            # Если есть хотя бы один маркер авторизации и нет гостевых маркеров
            if results['auth_markers'] and not results['has_guest_marker']:
                results['is_authenticated'] = True
            
            # Логирование
            logger.info(f"🔍 Cookie auth check: authenticated={results['is_authenticated']}, markers={len(results['auth_markers'])}, issues={len(results['issues'])}")
            if results['auth_markers']:
                logger.info(f"   ✅ Auth markers: {', '.join(results['auth_markers'][:3])}")
            if results['issues']:
                for issue in results['issues']:
                    logger.warning(f"   ⚠️ {issue}")
            
        except Exception as e:
            logger.error(f"❌ Cookie authentication check failed: {e}")
            results['issues'].append(f'Exception: {str(e)}')
        
        return results
    
    def verify_authentication(self, lsd_name: str = None) -> Dict[str, Any]:
        """
        Проверяет статус авторизации после загрузки
        
        Args:
            lsd_name: Название ЛСД для логирования (опционально)
        
        Returns:
            Словарь с результатами проверки
        """
        if not self.driver:
            raise RuntimeError("Browser not initialized")
        
        from selenium.webdriver.common.by import By
        
        logger.info("🔍 Verifying authentication status...")
        
        results = {
            'is_authenticated': False,
            'login_buttons_visible': 0,
            'profile_elements_visible': 0,
            'auth_cookies_in_browser': 0,
            'total_cookies_in_browser': 0,
            'cookie_auth_status': {}
        }
        
        try:
            # СНАЧАЛА проверяем куки (более надежно)
            cookie_status = self.check_cookie_authentication()
            results['cookie_auth_status'] = cookie_status
            
            # Проверяем куки в браузере
            browser_cookies = self.driver.get_cookies()
            results['total_cookies_in_browser'] = len(browser_cookies)
            
            # Ищем авторизационные куки
            auth_cookies = []
            for cookie in browser_cookies:
                name = cookie.get('name', '').lower()
                if any(kw in name for kw in ['session', 'auth', 'user', 'token', 'csrf']):
                    auth_cookies.append(cookie.get('name'))
            
            results['auth_cookies_in_browser'] = len(auth_cookies)
            
            # Ищем кнопки входа
            login_selectors = [
                "//span[text()='Войти']",
                "//button[contains(text(), 'Войти')]",
                "//a[contains(text(), 'Войти')]"
            ]
            
            login_count = 0
            for selector in login_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    visible_elements = [e for e in elements if e.is_displayed()]
                    login_count += len(visible_elements)
                except:
                    pass
            
            results['login_buttons_visible'] = login_count
            
            # Ищем элементы профиля
            profile_selectors = [
                "//span[contains(text(), 'Профиль')]",
                "//button[contains(text(), 'Профиль')]",
                "//div[contains(text(), 'Профиль')]",
                "//span[contains(text(), 'Мой профиль')]"
            ]
            
            profile_count = 0
            for selector in profile_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    visible_elements = [e for e in elements if e.is_displayed()]
                    profile_count += len(visible_elements)
                except:
                    pass
            
            results['profile_elements_visible'] = profile_count
            
            # ПРИОРИТЕТ: проверка кук важнее визуальных элементов
            if cookie_status['is_authenticated']:
                results['is_authenticated'] = True
            elif profile_count > 0:
                results['is_authenticated'] = True
            elif login_count == 0 and len(auth_cookies) > 0:
                results['is_authenticated'] = True
            
            # Логируем результаты
            lsd_info = f" in {lsd_name}" if lsd_name else ""
            if results['is_authenticated']:
                logger.info(f"✅ User appears to be authenticated{lsd_info}!")
                logger.info(f"   Cookie user_id: {cookie_status.get('user_id', 'N/A')}")
                logger.info(f"   Profile elements: {profile_count}")
                logger.info(f"   Auth cookies: {len(auth_cookies)}")
            else:
                logger.warning(f"❌ User does not appear to be authenticated{lsd_info}")
                logger.warning(f"   Login buttons visible: {login_count}")
                logger.warning(f"   Profile elements: {profile_count}")
                if cookie_status['issues']:
                    logger.warning(f"   Cookie issues: {', '.join(cookie_status['issues'])}")
            
        except Exception as e:
            logger.error(f"❌ Authentication verification failed: {e}")
        
        return results
    
    def extract_local_storage(self) -> Dict[str, str]:
        """
        Извлекает все данные из localStorage
        
        Returns:
            Словарь {key: value}
        """
        if not self.driver:
            raise RuntimeError("Browser not initialized")
        
        try:
            script = """
            let storage = {};
            for (let i = 0; i < localStorage.length; i++) {
                let key = localStorage.key(i);
                storage[key] = localStorage.getItem(key);
            }
            return storage;
            """
            local_storage = self.driver.execute_script(script)
            
            logger.info(f"📦 Extracted {len(local_storage)} localStorage items")
            
            # Логируем первые несколько ключей
            for i, key in enumerate(list(local_storage.keys())[:3]):
                value_preview = str(local_storage[key])[:50]
                logger.debug(f"   [{i+1}] {key} = {value_preview}...")
            
            if len(local_storage) > 3:
                logger.debug(f"   ... and {len(local_storage)-3} more items")
            
            return local_storage
            
        except Exception as e:
            logger.error(f"❌ Failed to extract localStorage: {e}")
            return {}
    
    def extract_session_storage(self) -> Dict[str, str]:
        """
        Извлекает все данные из sessionStorage
        
        Returns:
            Словарь {key: value}
        """
        if not self.driver:
            raise RuntimeError("Browser not initialized")
        
        try:
            script = """
            let storage = {};
            for (let i = 0; i < sessionStorage.length; i++) {
                let key = sessionStorage.key(i);
                storage[key] = sessionStorage.getItem(key);
            }
            return storage;
            """
            session_storage = self.driver.execute_script(script)
            
            logger.info(f"📦 Extracted {len(session_storage)} sessionStorage items")
            
            # Логируем первые несколько ключей
            for i, key in enumerate(list(session_storage.keys())[:3]):
                value_preview = str(session_storage[key])[:50]
                logger.debug(f"   [{i+1}] {key} = {value_preview}...")
            
            if len(session_storage) > 3:
                logger.debug(f"   ... and {len(session_storage)-3} more items")
            
            return session_storage
            
        except Exception as e:
            logger.error(f"❌ Failed to extract sessionStorage: {e}")
            return {}
    
    def inject_local_storage(self, storage_data: Dict[str, str]) -> int:
        """
        Инжектирует данные в localStorage
        
        Args:
            storage_data: Словарь {key: value}
        
        Returns:
            Количество успешно инжектированных элементов
        """
        if not self.driver:
            raise RuntimeError("Browser not initialized")
        
        if not storage_data:
            logger.debug("No localStorage data to inject")
            return 0
        
        try:
            import json
            injected_count = 0
            
            for key, value in storage_data.items():
                try:
                    script = f"""
                    localStorage.setItem({json.dumps(key)}, {json.dumps(value)});
                    """
                    self.driver.execute_script(script)
                    injected_count += 1
                except Exception as e:
                    logger.debug(f"⚠️ Failed to inject localStorage item '{key}': {e}")
            
            logger.info(f"📦 Injected {injected_count}/{len(storage_data)} localStorage items")
            return injected_count
            
        except Exception as e:
            logger.error(f"❌ Failed to inject localStorage: {e}")
            return 0
    
    def inject_session_storage(self, storage_data: Dict[str, str]) -> int:
        """
        Инжектирует данные в sessionStorage
        
        Args:
            storage_data: Словарь {key: value}
        
        Returns:
            Количество успешно инжектированных элементов
        """
        if not self.driver:
            raise RuntimeError("Browser not initialized")
        
        if not storage_data:
            logger.debug("No sessionStorage data to inject")
            return 0
        
        try:
            import json
            injected_count = 0
            
            for key, value in storage_data.items():
                try:
                    script = f"""
                    sessionStorage.setItem({json.dumps(key)}, {json.dumps(value)});
                    """
                    self.driver.execute_script(script)
                    injected_count += 1
                except Exception as e:
                    logger.debug(f"⚠️ Failed to inject sessionStorage item '{key}': {e}")
            
            logger.info(f"📦 Injected {injected_count}/{len(storage_data)} sessionStorage items")
            return injected_count
            
        except Exception as e:
            logger.error(f"❌ Failed to inject sessionStorage: {e}")
            return 0
    
    def extract_cookies(self) -> List[Dict[str, Any]]:
        """
        Извлекает ВСЕ куки из текущей сессии браузера через CDP
        Включая HTTP-only и __Secure- куки

        Returns:
            Список кук в стандартном формате
        """
        if not self.driver:
            raise RuntimeError("Browser not initialized")

        try:
            # КРИТИЧНО: Используем CDP для получения ВСЕХ кук (включая HTTP-only)
            try:
                cdp_cookies = self.driver.execute_cdp_cmd('Network.getAllCookies', {})
                cookies_list = cdp_cookies.get('cookies', [])

                logger.info(f"🍪 Extracted {len(cookies_list)} cookies via CDP (including HTTP-only)")

                # Конвертируем CDP формат в Selenium формат для совместимости
                selenium_cookies = []
                for cdp_cookie in cookies_list:
                    selenium_cookie = {
                        'name': cdp_cookie.get('name'),
                        'value': cdp_cookie.get('value'),
                        'domain': cdp_cookie.get('domain'),
                        'path': cdp_cookie.get('path', '/'),
                    }

                    # Опциональные поля
                    if 'secure' in cdp_cookie:
                        selenium_cookie['secure'] = cdp_cookie['secure']
                    if 'httpOnly' in cdp_cookie:
                        selenium_cookie['httpOnly'] = cdp_cookie['httpOnly']
                    if 'expires' in cdp_cookie and cdp_cookie['expires'] > 0:
                        selenium_cookie['expiry'] = int(cdp_cookie['expires'])
                    if 'sameSite' in cdp_cookie:
                        selenium_cookie['sameSite'] = cdp_cookie['sameSite']

                    selenium_cookies.append(selenium_cookie)

                # Логируем secure-куки для отладки
                secure_cookies = [c for c in selenium_cookies if c['name'].startswith('__Secure-')]
                if secure_cookies:
                    logger.info(f"   ✅ Found {len(secure_cookies)} __Secure- cookies:")
                    for c in secure_cookies[:5]:
                        logger.debug(f"      {c['name']} (httpOnly={c.get('httpOnly', False)})")

                # Логируем первые несколько кук для отладки
                for i, cookie in enumerate(selenium_cookies[:3]):
                    logger.debug(f"   Cookie {i+1}: {cookie.get('name', 'unknown')} = {str(cookie.get('value', ''))[:20]}...")

                if len(selenium_cookies) > 3:
                    logger.debug(f"   ... and {len(selenium_cookies)-3} more cookies")

                return selenium_cookies

            except Exception as cdp_error:
                # Fallback: Selenium API (не получит HTTP-only куки)
                logger.warning(f"⚠️ CDP cookie extraction failed: {cdp_error}, using Selenium fallback")
                cookies = self.driver.get_cookies()
                logger.warning(f"⚠️ Fallback extracted only {len(cookies)} cookies (missing HTTP-only)")
                return cookies

        except Exception as e:
            logger.error(f"❌ Failed to extract cookies: {e}")
            return []
    
    def extract_cookies_and_storage(self) -> Dict[str, Any]:
        """
        Извлекает cookies + localStorage + sessionStorage
        
        Returns:
            {
                'cookies': List[Dict],
                'localStorage': Dict[str, str],
                'sessionStorage': Dict[str, str]
            }
        """
        return {
            'cookies': self.extract_cookies(),
            'localStorage': self.extract_local_storage(),
            'sessionStorage': self.extract_session_storage()
        }
    
    def take_screenshot(self, filename: Optional[str] = None) -> str:
        """
        Создает скриншот текущего состояния
        
        Args:
            filename: Имя файла (если не указано, генерируется автоматически)
            
        Returns:
            Путь к созданному скриншоту
        """
        if not self.driver:
            raise RuntimeError("Browser not initialized")
        
        if not filename:
            import time
            filename = f"cdp_screenshot_{int(time.time())}.png"
        
        try:
            screenshot_path = f"./{filename}"
            self.driver.save_screenshot(screenshot_path)
            logger.info(f"📸 Screenshot saved: {screenshot_path}")
            return screenshot_path
        except Exception as e:
            logger.error(f"❌ Failed to take screenshot: {e}")
            raise
    
    def _inject_image_blocking_script(self):
        """Инжектит JavaScript для агрессивной блокировки изображений НА КАЖДОЙ СТРАНИЦЕ"""
        if not self.driver:
            return
        
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
                self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    'source': blocking_script
                })
                logger.info("🚫 Image blocking script added to ALL new pages via CDP")
                
                # Также применяем к текущей странице немедленно
                self.driver.execute_script(blocking_script)
                logger.info("🚫 Image blocking applied to current page")
                
            except Exception as cdp_error:
                # Fallback: только текущая страница
                logger.warning(f"⚠️ CDP injection failed: {cdp_error}, using fallback")
                self.driver.execute_script(blocking_script)
                logger.info("🚫 Image blocking applied via execute_script (fallback - current page only)")
                
        except Exception as e:
            logger.warning(f"⚠️ Failed to inject image blocking script: {e}")
            # Не критично - продолжаем работу
    
    def remove_guest_cookies(self) -> int:
        """
        Удаляет гостевые куки из текущей сессии браузера
        
        Returns:
            Количество удаленных кук
        """
        if not self.driver:
            raise RuntimeError("Browser not initialized")
        
        removed_count = 0
        removed_names = []
        
        try:
            browser_cookies = self.driver.get_cookies()
            
            for cookie in browser_cookies:
                name = cookie.get('name', '')
                value = str(cookie.get('value', ''))
                domain = cookie.get('domain', '')
                
                should_remove = False
                reason = ""
                
                # Удаляем guest=true
                if name == 'guest' and value == 'true':
                    should_remove = True
                    reason = "guest=true"
                
                # Удаляем __Secure-user-id=0
                elif name == '__Secure-user-id' and value == '0':
                    should_remove = True
                    reason = f"user-id=0 on {domain}"
                
                # Удаляем конфликтующие токены на широком домене
                elif domain.startswith('.') and name in {'__Secure-access-token', '__Secure-refresh-token'}:
                    # Проверяем есть ли такая же кука на специфичном домене
                    specific_domain_has_token = any(
                        c.get('name') == name and not c.get('domain', '').startswith('.')
                        for c in browser_cookies
                    )
                    if specific_domain_has_token:
                        should_remove = True
                        reason = f"{name} on {domain} (conflict)"
                
                if should_remove:
                    try:
                        self.driver.delete_cookie(name)
                        removed_count += 1
                        removed_names.append(f"{name} ({reason})")
                    except Exception as e:
                        logger.debug(f"⚠️ Failed to delete cookie {name}: {e}")
            
            if removed_count > 0:
                logger.info(f"🧹 Removed {removed_count} guest/conflicting cookies:")
                for i, name_reason in enumerate(removed_names[:5], 1):
                    logger.info(f"   {i}. {name_reason}")
                if len(removed_names) > 5:
                    logger.info(f"   ... and {len(removed_names) - 5} more")
            else:
                logger.info("✅ No guest cookies found to remove")
            
        except Exception as e:
            logger.error(f"❌ Failed to remove guest cookies: {e}")
        
        return removed_count
    
    def cleanup(self):
        """Закрывает браузер и освобождает ресурсы"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("✅ Browser closed and cleaned up")
            except Exception as e:
                logger.warning(f"⚠️ Error during cleanup: {e}")
            finally:
                self.driver = None
    
    def __enter__(self):
        """Поддержка context manager"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Автоматическая очистка при выходе из context"""
        self.cleanup()
