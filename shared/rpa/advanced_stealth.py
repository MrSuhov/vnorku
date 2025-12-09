#!/usr/bin/env python3
"""
Продвинутая маскировка браузера для обхода сложных анти-бот систем (Ozon, Wildberries и т.д.)
"""

import asyncio
import random
import string
from typing import Dict, List, Any
from playwright.async_api import Page, BrowserContext

class AdvancedStealth:
    """Класс для продвинутой маскировки браузера"""
    
    @staticmethod
    def get_stealth_browser_args() -> List[str]:
        """Получить аргументы браузера для максимальной маскировки"""
        return [
            # Базовые аргументы безопасности
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-setuid-sandbox',
            
            # Отключение автоматизации
            '--disable-blink-features=AutomationControlled',
            '--exclude-switches=enable-automation',
            '--disable-component-extensions-with-background-pages',
            '--disable-default-apps',
            '--disable-extensions',
            
            # Отключение телеметрии и метрик
            '--disable-background-networking',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-features=TranslateUI',
            '--disable-ipc-flooding-protection',
            '--no-first-run',
            '--no-service-autorun',
            '--password-store=basic',
            '--use-mock-keychain',
            
            # Отключение различных служб
            '--disable-background-mode',
            '--disable-component-update',
            '--disable-domain-reliability',
            '--disable-features=VizDisplayCompositor',
            '--disable-hang-monitor',
            '--disable-prompt-on-repost',
            '--disable-sync',
            '--disable-web-security',
            '--metrics-recording-only',
            '--no-default-browser-check',
            '--no-pings',
            '--safebrowsing-disable-auto-update',
            '--use-fake-device-for-media-stream',
            '--use-fake-ui-for-media-stream',
            
            # Размер окна (популярное разрешение)
            '--window-size=1920,1080',
            
            # Дополнительные флаги для обхода детекции
            '--disable-features=VizDisplayCompositor,VizHitTestSurfaceLayer',
            '--disable-features=site-per-process',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--disable-accelerated-jpeg-decoding',
            '--disable-accelerated-mjpeg-decode',
            '--disable-accelerated-video-decode',
            '--disable-gpu',
            '--disable-gpu-sandbox',
            '--disable-software-rasterizer',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-field-trial-config',
            '--disable-back-forward-cache',
            '--disable-breakpad',
            '--disable-client-side-phishing-detection',
            '--disable-component-update',
            '--disable-default-apps',
            '--disable-domain-reliability',
            '--disable-extensions',
            '--disable-features=AudioServiceOutOfProcess',
            '--disable-features=VizDisplayCompositor',
            '--disable-hang-monitor',
            '--disable-ipc-flooding-protection',
            '--disable-popup-blocking',
            '--disable-prompt-on-repost',
            '--disable-sync',
            '--force-color-profile=srgb',
            '--metrics-recording-only',
            '--no-first-run',
            '--no-default-browser-check',
            '--no-pings',
            '--password-store=basic',
            '--use-mock-keychain',
            '--disable-extensions-except',
            '--disable-plugins-discovery',
            '--allow-running-insecure-content'
        ]
    
    @staticmethod
    def get_stealth_context_options() -> Dict[str, Any]:
        """Получить опции контекста для маскировки"""
        return {
            # Реалистичный User-Agent (последний Chrome на Windows)
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            
            # Разрешение экрана
            'viewport': {'width': 1920, 'height': 1080},
            'screen': {'width': 1920, 'height': 1080},
            'device_scale_factor': 1.0,
            
            # Локализация
            'locale': 'ru-RU',
            'timezone_id': 'Europe/Moscow',
            
            # Разрешения
            'permissions': ['geolocation'],
            
            # HTTP заголовки как у реального Chrome
            'extra_http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Cache-Control': 'max-age=0',
                'DNT': '1',
                'Upgrade-Insecure-Requests': '1',
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1'
            },
            
            # Дополнительные опции
            'java_script_enabled': True,
            'ignore_https_errors': True,
            'bypass_csp': True
        }
    
    @staticmethod
    async def apply_stealth_scripts(page: Page) -> None:
        """Применить JavaScript маскировку к странице"""
        
        # Основная маскировка
        await page.add_init_script("""
            // Переопределяем navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true
            });
            
            // Удаляем chrome runtime
            if (window.chrome) {
                delete window.chrome.runtime;
                delete window.chrome.loadTimes;
                delete window.chrome.csi;
                delete window.chrome.app;
            }
            
            // Маскируем navigator properties
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    return [
                        {
                            0: {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: null},
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "PDF Viewer"
                        },
                        {
                            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: null},
                            description: "Portable Document Format", 
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Plugin"
                        },
                        {
                            0: {type: "application/x-nacl", suffixes: "", description: "Native Client Executable", enabledPlugin: null},
                            1: {type: "application/x-pnacl", suffixes: "", description: "Portable Native Client Executable", enabledPlugin: null},
                            description: "Native Client",
                            filename: "internal-nacl-plugin",
                            length: 2,
                            name: "Native Client"
                        }
                    ];
                },
                configurable: true
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ru-RU', 'ru', 'en-US', 'en'],
                configurable: true
            });
            
            Object.defineProperty(navigator, 'vendor', {
                get: () => 'Google Inc.',
                configurable: true
            });
            
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32',
                configurable: true
            });
            
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8,
                configurable: true
            });
            
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8,
                configurable: true
            });
            
            Object.defineProperty(navigator, 'maxTouchPoints', {
                get: () => 0,
                configurable: true
            });
            
            // Маскируем WebGL
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel(R) UHD Graphics 630';
                }
                return getParameter.call(this, parameter);
            };
            
            // Маскируем canvas fingerprinting
            const toDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {
                const shift = Math.floor(Math.random() * 10) - 5;
                const canvas = this;
                const ctx = canvas.getContext('2d');
                if (ctx) {
                    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                    for (let i = 0; i < imageData.data.length; i += 4) {
                        imageData.data[i] = Math.min(255, Math.max(0, imageData.data[i] + shift));
                    }
                    ctx.putImageData(imageData, 0, 0);
                }
                return toDataURL.apply(this, arguments);
            };
            
            // Удаляем следы автоматизации
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
            
            // Удаляем window.cdc_ переменные
            Object.keys(window).forEach(key => {
                if (key.includes('cdc_') || key.includes('webdriver')) {
                    delete window[key];
                }
            });
            
            // Маскируем Error стеки
            const originalError = window.Error;
            window.Error = function(...args) {
                const error = new originalError(...args);
                if (error.stack) {
                    error.stack = error.stack.replace(/.*playwright.*\\n?/gi, '');
                    error.stack = error.stack.replace(/.*puppeteer.*\\n?/gi, '');
                    error.stack = error.stack.replace(/.*automation.*\\n?/gi, '');
                }
                return error;
            };
            
            console.log('🎭 Advanced stealth mode activated');
        """)
        
        # Маскировка временных зон
        await page.add_init_script("""
            Date.prototype.getTimezoneOffset = function() {
                return -180; // Moscow timezone
            };
        """)
        
        # Добавляем случайные задержки в действия мыши
        await page.add_init_script("""
            const originalAddEventListener = EventTarget.prototype.addEventListener;
            EventTarget.prototype.addEventListener = function(type, listener, options) {
                if (type === 'mousedown' || type === 'mouseup' || type === 'click') {
                    const wrappedListener = function(event) {
                        // Добавляем микро-задержки для имитации человека
                        setTimeout(() => listener.call(this, event), Math.random() * 2);
                    };
                    return originalAddEventListener.call(this, type, wrappedListener, options);
                }
                return originalAddEventListener.call(this, type, listener, options);
            };
        """)

    @staticmethod  
    async def add_human_behavior(page: Page) -> None:
        """Добавляет человекоподобное поведение"""
        
        # Случайные движения мыши
        await page.mouse.move(
            random.randint(100, 300), 
            random.randint(100, 300),
            steps=random.randint(3, 7)
        )
        
        # Случайная пауза
        await asyncio.sleep(random.uniform(0.5, 2.0))
        
        # Эмуляция скролла
        await page.mouse.wheel(0, random.randint(-100, 100))
        
        # Еще одна пауза
        await asyncio.sleep(random.uniform(0.3, 1.0))

    @staticmethod
    async def setup_stealth_page(page: Page) -> None:
        """Полная настройка страницы для маскировки"""
        
        # Применяем все скрипты маскировки
        await AdvancedStealth.apply_stealth_scripts(page)
        
        # Устанавливаем дополнительные заголовки
        await page.set_extra_http_headers({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'max-age=0',
            'Upgrade-Insecure-Requests': '1',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        })
        
        # НЕ блокируем картинки - только рекламу и трекеры
        # await page.route('**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2}', lambda route: route.abort())
        
        # Блокируем только рекламу и аналитику
        await page.route('**/*ads*', lambda route: route.abort())
        await page.route('**/*analytics*', lambda route: route.abort())
        await page.route('**/*tracking*', lambda route: route.abort())
        
        # Добавляем обработчики для имитации человека
        await page.evaluate("""
            // Добавляем случайные движения курсора
            document.addEventListener('mousemove', (e) => {
                // Сохраняем координаты для анализа паттернов движения
                window.mouseMovements = window.mouseMovements || [];
                window.mouseMovements.push({x: e.clientX, y: e.clientY, time: Date.now()});
                if (window.mouseMovements.length > 100) {
                    window.mouseMovements.shift();
                }
            });
        """)

    @staticmethod
    def create_realistic_user_agent() -> str:
        """Создает реалистичный User-Agent"""
        chrome_versions = ['120.0.0.0', '119.0.0.0', '118.0.0.0']
        version = random.choice(chrome_versions)
        
        return f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36'

    @staticmethod
    async def bypass_cloudflare(page: Page) -> bool:
        """Попытка обойти Cloudflare защиту"""
        try:
            # Ждем загрузки страницы
            await page.wait_for_load_state('networkidle', timeout=10000)
            
            # Проверяем наличие Cloudflare challenge
            cloudflare_selectors = [
                '[data-ray]',
                '.cf-error-title', 
                '#cf-error-details',
                '.cf-browser-verification',
                'input[name="cf_captcha_kind"]'
            ]
            
            for selector in cloudflare_selectors:
                element = await page.query_selector(selector)
                if element:
                    print("🛡️  Обнаружена защита Cloudflare, ожидаем...")
                    # Ждем до 30 секунд для прохождения проверки
                    await page.wait_for_timeout(random.randint(5000, 10000))
                    
                    # Попробуем кликнуть на checkbox если есть
                    checkbox = await page.query_selector('input[type="checkbox"]')
                    if checkbox:
                        await checkbox.click()
                        await page.wait_for_timeout(3000)
                    
                    return True
            
            return False
            
        except Exception as e:
            print(f"Ошибка при обходе Cloudflare: {e}")
            return False

    @staticmethod
    async def wait_for_stable_page(page: Page, timeout: int = 30000) -> None:
        """Ждет стабилизации страницы (полной загрузки)"""
        try:
            # Ждем загрузки DOM
            await page.wait_for_load_state('domcontentloaded', timeout=timeout)
            
            # Ждем загрузки всех ресурсов
            await page.wait_for_load_state('networkidle', timeout=timeout)
            
            # Дополнительная пауза для JS инициализации
            await page.wait_for_timeout(2000)
            
        except Exception as e:
            print(f"Предупреждение: страница может быть не полностью загружена: {e}")
