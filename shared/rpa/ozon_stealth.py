#!/usr/bin/env python3
"""
Специальная маскировка для Ozon - максимальный обход детекции ботов
"""

import asyncio
import random
import string
from typing import Dict, List, Any
from playwright.async_api import Page, BrowserContext

class OzonStealth:
    """Специальная маскировка для обхода защиты Ozon"""
    
    @staticmethod
    def get_ozon_browser_args() -> List[str]:
        """Получить специальные аргументы браузера для Ozon"""
        return [
            # Основные аргументы маскировки
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-setuid-sandbox',
            
            # КРИТИЧНО: Отключение автоматизации
            '--disable-blink-features=AutomationControlled',
            '--exclude-switches=enable-automation',
            '--disable-component-extensions-with-background-pages',
            '--disable-default-apps',
            '--disable-extensions',
            '--no-first-run',
            '--no-default-browser-check',
            
            # Отключение телеметрии (важно для Ozon)
            '--disable-background-networking',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-features=TranslateUI',
            '--disable-ipc-flooding-protection',
            '--no-service-autorun',
            '--password-store=basic',
            '--use-mock-keychain',
            
            # Размер окна (популярное разрешение)
            '--window-size=1920,1080',
            
            # Дополнительные флаги против детекции
            '--disable-features=VizDisplayCompositor',
            '--disable-features=site-per-process',
            '--disable-web-security',
            '--allow-running-insecure-content',
            '--disable-client-side-phishing-detection',
            '--disable-component-update',
            '--disable-domain-reliability',
            '--disable-hang-monitor',
            '--disable-popup-blocking',
            '--disable-prompt-on-repost',
            '--disable-sync',
            '--metrics-recording-only',
            '--no-pings',
            '--force-color-profile=srgb',
            '--use-fake-device-for-media-stream',
            '--use-fake-ui-for-media-stream',
            
            # GPU отключение (может помочь с детекцией)
            '--disable-gpu',
            '--disable-gpu-sandbox',
            '--disable-accelerated-2d-canvas',
            '--disable-accelerated-jpeg-decoding',
            '--disable-accelerated-mjpeg-decode',
            '--disable-accelerated-video-decode',
            '--disable-software-rasterizer',
            
            # Дополнительные флаги
            '--disable-field-trial-config',
            '--disable-back-forward-cache',
            '--disable-breakpad',
            '--disable-extensions-except',
            '--disable-plugins-discovery'
        ]
    
    @staticmethod
    def get_ozon_context_options() -> Dict[str, Any]:
        """Получить специальные опции контекста для Ozon"""
        return {
            # Реалистичный User-Agent (последний Chrome на Mac - как у вас)
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            
            # Разрешение экрана (популярное для Mac)
            'viewport': {'width': 1920, 'height': 1080},
            'screen': {'width': 1920, 'height': 1080},
            'device_scale_factor': 2.0,  # Retina display
            
            # Локализация (Russian)
            'locale': 'ru-RU',
            'timezone_id': 'Europe/Moscow',
            
            # Разрешения
            'permissions': ['geolocation', 'notifications'],
            'geolocation': {'latitude': 55.7558, 'longitude': 37.6176},  # Moscow
            
            # HTTP заголовки как у реального Safari на Mac
            'extra_http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Cache-Control': 'max-age=0',
                'DNT': '1',
                'Upgrade-Insecure-Requests': '1',
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
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
    async def apply_ozon_stealth_scripts(page: Page) -> None:
        """Применить максимальную JavaScript маскировку для Ozon"""
        
        # Основная маскировка
        await page.add_init_script("""
            // Удаляем все следы автоматизации
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true
            });
            
            // Удаляем chrome runtime полностью
            if (window.chrome && window.chrome.runtime) {
                delete window.chrome.runtime;
            }
            if (window.chrome && window.chrome.loadTimes) {
                delete window.chrome.loadTimes;
            }
            if (window.chrome && window.chrome.csi) {
                delete window.chrome.csi;
            }
            if (window.chrome && window.chrome.app) {
                delete window.chrome.app;
            }
            
            // Переопределяем permissions API
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
            
            // Маскируем navigator properties (Mac версия)
            Object.defineProperty(navigator, 'platform', {
                get: () => 'MacIntel',
                configurable: true
            });
            
            Object.defineProperty(navigator, 'vendor', {
                get: () => 'Google Inc.',
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
                get: () => 0,  // Desktop Mac
                configurable: true
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ru-RU', 'ru', 'en-US', 'en'],
                configurable: true
            });
            
            // Маскируем plugins (реалистичный набор для Mac Chrome)
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
                        }
                    ];
                },
                configurable: true
            });
            
            // Маскируем WebGL для Mac
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel(R) Iris(TM) Pro Graphics 6200';
                }
                return getParameter.call(this, parameter);
            };
            
            // Удаляем все cdc_ переменные (след ChromeDriver)
            Object.keys(window).forEach(key => {
                if (key.includes('cdc_') || key.includes('webdriver') || key.includes('$chrome_asyncScriptInfo')) {
                    delete window[key];
                }
            });
            
            // Маскируем canvas fingerprinting с учетом Mac
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
            
            // Маскируем Error стеки
            const originalError = window.Error;
            window.Error = function(...args) {
                const error = new originalError(...args);
                if (error.stack) {
                    error.stack = error.stack.replace(/.*playwright.*\\n?/gi, '');
                    error.stack = error.stack.replace(/.*puppeteer.*\\n?/gi, '');
                    error.stack = error.stack.replace(/.*automation.*\\n?/gi, '');
                    error.stack = error.stack.replace(/.*chromedriver.*\\n?/gi, '');
                }
                return error;
            };
            
            // Добавляем реалистичные свойства экрана для Mac
            Object.defineProperty(screen, 'colorDepth', {
                get: () => 24,
                configurable: true
            });
            
            Object.defineProperty(screen, 'pixelDepth', {
                get: () => 24,
                configurable: true
            });
            
            // Маскируем Date для Moscow timezone
            Date.prototype.getTimezoneOffset = function() {
                return -180; // Moscow timezone (+3)
            };
            
            console.log('🎭 Ozon stealth mode activated');
        """)
        
        # Дополнительная маскировка специально для Ozon
        await page.add_init_script("""
            // Переопределяем функции детекции автоматизации
            if (window.navigator.webdriver) {
                delete window.navigator.webdriver;
            }
            
            // Эмулируем человеческое поведение мыши
            let mouseEventCount = 0;
            const originalAddEventListener = EventTarget.prototype.addEventListener;
            EventTarget.prototype.addEventListener = function(type, listener, options) {
                if (type === 'mousedown' || type === 'mouseup' || type === 'click') {
                    const wrappedListener = function(event) {
                        mouseEventCount++;
                        // Добавляем микро-задержки и вариативность
                        const delay = Math.random() * 3 + 1;
                        setTimeout(() => listener.call(this, event), delay);
                    };
                    return originalAddEventListener.call(this, type, wrappedListener, options);
                }
                return originalAddEventListener.call(this, type, listener, options);
            };
            
            // Эмулируем активность пользователя
            setInterval(() => {
                // Имитируем движения мыши
                const event = new MouseEvent('mousemove', {
                    bubbles: true,
                    cancelable: true,
                    clientX: Math.random() * window.innerWidth,
                    clientY: Math.random() * window.innerHeight
                });
                document.dispatchEvent(event);
            }, 1000 + Math.random() * 2000);
        """)

    @staticmethod  
    async def add_ozon_human_behavior(page: Page) -> None:
        """Добавляет специальное человекоподобное поведение для Ozon"""
        
        # Более долгие и реалистичные движения мыши
        for _ in range(random.randint(2, 4)):
            x = random.randint(200, 1720)
            y = random.randint(200, 880)
            await page.mouse.move(x, y, steps=random.randint(5, 12))
            await asyncio.sleep(random.uniform(0.3, 0.8))
        
        # Случайные скроллы (имитация чтения)
        for _ in range(random.randint(1, 3)):
            scroll_delta = random.randint(-300, 300)
            await page.mouse.wheel(0, scroll_delta)
            await asyncio.sleep(random.uniform(0.5, 1.5))
        
        # Более долгая пауза (имитация чтения страницы)
        await asyncio.sleep(random.uniform(2.0, 4.0))

    @staticmethod
    async def setup_ozon_page(page: Page) -> None:
        """Полная настройка страницы специально для Ozon"""
        
        # Применяем все скрипты маскировки
        await OzonStealth.apply_ozon_stealth_scripts(page)
        
        # Устанавливаем специальные заголовки для Mac Safari
        await page.set_extra_http_headers({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'max-age=0',
            'Upgrade-Insecure-Requests': '1',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"'
        })
        
        # НЕ блокируем картинки для Ozon - они могут это детектить
        # Только блокируем рекламу и трекеры
        await page.route('**/*ads*', lambda route: route.abort())
        await page.route('**/*analytics*', lambda route: route.abort())
        await page.route('**/*tracking*', lambda route: route.abort())
        
        # Добавляем обработчики для имитации реального пользователя
        await page.evaluate("""
            // Более сложная имитация движений мыши
            let mouseTrail = [];
            document.addEventListener('mousemove', (e) => {
                mouseTrail.push({
                    x: e.clientX, 
                    y: e.clientY, 
                    time: Date.now(),
                    pressure: Math.random() * 0.5 + 0.5
                });
                if (mouseTrail.length > 50) {
                    mouseTrail.shift();
                }
            });
            
            // Имитация печатания
            let keystrokes = [];
            document.addEventListener('keydown', (e) => {
                keystrokes.push({
                    key: e.key,
                    time: Date.now(),
                    duration: Math.random() * 200 + 50
                });
                if (keystrokes.length > 20) {
                    keystrokes.shift();
                }
            });
            
            // Добавляем случайные интеракции
            setInterval(() => {
                if (Math.random() < 0.1) {
                    const scrollEvent = new WheelEvent('wheel', {
                        deltaY: (Math.random() - 0.5) * 100,
                        bubbles: true
                    });
                    document.dispatchEvent(scrollEvent);
                }
            }, 3000);
        """)

    @staticmethod
    async def navigate_to_ozon_safely(page: Page, url: str) -> bool:
        """Безопасная навигация на Ozon с проверками"""
        try:
            print("🌍 Безопасная навигация на Ozon...")
            
            # Добавляем человеческое поведение перед навигацией
            await OzonStealth.add_ozon_human_behavior(page)
            
            # Идем на страницу
            await page.goto(url, timeout=30000, wait_until='networkidle')
            
            # Проверяем заголовок
            title = await page.title()
            print(f"📄 Заголовок: {title}")
            
            # Проверяем, не заблокировал ли нас Ozon
            content = await page.content()
            
            if any(keyword in content.lower() for keyword in ['access denied', 'blocked', 'captcha', 'verification']):
                print("🚨 Ozon заблокировал доступ")
                return False
            
            if 'ozon' not in content.lower():
                print("⚠️ Не похоже на страницу Ozon")
                return False
            
            print("✅ Успешно попали на Ozon")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка навигации: {e}")
            return False
