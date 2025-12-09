#!/usr/bin/env python3
"""
Safari-подобная конфигурация браузера для максимального сходства с реальным Safari
"""

import asyncio
from typing import Dict, List, Any
from playwright.async_api import Page, BrowserContext

class SafariLikeBrowser:
    """Конфигурация браузера максимально близкая к Safari"""
    
    @staticmethod
    def get_safari_browser_args() -> List[str]:
        """Минимальные аргументы браузера для Safari-подобного поведения"""
        return [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            # Маскировка автоматизации
            '--disable-blink-features=AutomationControlled',
            '--exclude-switches=enable-automation',
            '--disable-component-extensions-with-background-pages',
            '--disable-default-apps',
            '--disable-extensions',
            # Отключаем телеметрию
            '--disable-background-networking',
            '--disable-background-timer-throttling',
            '--disable-renderer-backgrounding',
            '--disable-features=TranslateUI',
            '--no-first-run',
            '--no-default-browser-check',
            # Отключаем синхронизацию и метрики
            '--disable-sync',
            '--disable-component-update',
            '--disable-domain-reliability',
            '--metrics-recording-only',
            '--no-pings',
        ]
    
    @staticmethod
    def get_safari_context_options() -> Dict[str, Any]:
        """Safari-подобные опции контекста с реальными настройками пользователя"""
        return {
            # Точный User-Agent из Safari пользователя
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15',
            
            # Реальные размеры экрана и viewport (обновленные)
            'viewport': {'width': 1400, 'height': 850},
            'screen': {'width': 1400, 'height': 900},
            'device_scale_factor': 2.0,  # Retina display
            
            # Реальная локализация пользователя
            'locale': 'ru-RU',  # Обновленная локаль пользователя
            'timezone_id': 'Europe/Moscow',  # Реальный часовой пояс пользователя
            
            # Десктопные настройки
            'is_mobile': False,
            'has_touch': False,
            
            # Safari-подобные заголовки с русским языком для ЛСД
            'extra_http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',  # Русский приоритет для ЛСД
                'Accept-Encoding': 'gzip, deflate, br',
                'Cache-Control': 'max-age=0',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none'
            },
            
            # Safari настройки
            'java_script_enabled': True,
            'ignore_https_errors': False,  # Safari строже с SSL
        }
    
    @staticmethod
    async def apply_safari_scripts(page: Page) -> None:
        """Минимальные скрипты для удаления следов автоматизации"""
        
        # Максимальная маскировка для Safari-подобного поведения
        await page.add_init_script("""
            // ========== 1. Агрессивная JavaScript маскировка ==========
            
            // Убираем основной признак автоматизации
            if (navigator.webdriver) {
                delete navigator.webdriver;
            }
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true
            });
            
            // Скрываем все Selenium/WebDriver артефакты
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_JSON;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Object;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Proxy;
            
            // Удаляем все переменные с cdc_ префиксом
            Object.keys(window).forEach(key => {
                if (key.includes('cdc_') || key.includes('webdriver') || key.includes('selenium') || key.includes('playwright')) {
                    try {
                        delete window[key];
                    } catch (e) {}
                }
            });
            
            // Удаляем Playwright специфичные объекты
            delete window.playwright;
            delete window.__playwright;
            delete document.__playwright;
            delete window.domAutomation;
            delete window.domAutomationController;
            
            // ========== 2. Реалистичные plugins и permissions ==========
            
            // Добавляем реалистичные плагины как в настоящем Safari
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    return [
                        {
                            0: {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: null},
                            description: "PDF Viewer",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "PDF Viewer"
                        },
                        {
                            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: null},
                            description: "Chrome PDF Plugin", 
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Plugin"
                        },
                        {
                            0: {type: "application/x-webkit-test-netscape", suffixes: "", description: "test netscape content", enabledPlugin: null},
                            description: "WebKit built-in PDF",
                            filename: "WebKit built-in PDF",
                            length: 1,
                            name: "WebKit built-in PDF"
                        }
                    ];
                },
                configurable: true
            });
            
            // Маскируем permissions API
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => {
                if (parameters.name === 'notifications') {
                    return Promise.resolve({ state: 'default', onchange: null });
                }
                if (parameters.name === 'geolocation') {
                    return Promise.resolve({ state: 'prompt', onchange: null });
                }
                return originalQuery(parameters);
            };
            
            // ========== 3. Правильный WebGL fingerprint ==========
            
            // Маскируем WebGL как реальный Mac
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                // UNMASKED_VENDOR_WEBGL
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                // UNMASKED_RENDERER_WEBGL  
                if (parameter === 37446) {
                    return 'Intel(R) Iris(TM) Pro Graphics 6200';
                }
                // VERSION
                if (parameter === 7938) {
                    return 'WebGL 1.0 (OpenGL ES 2.0 Chromium)';
                }
                // SHADING_LANGUAGE_VERSION
                if (parameter === 35724) {
                    return 'WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)';
                }
                return getParameter.call(this, parameter);
            };
            
            // Аналогично для WebGL2
            if (typeof WebGL2RenderingContext !== 'undefined') {
                const getParameter2 = WebGL2RenderingContext.prototype.getParameter;
                WebGL2RenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) return 'Intel Inc.';
                    if (parameter === 37446) return 'Intel(R) Iris(TM) Pro Graphics 6200';
                    return getParameter2.call(this, parameter);
                };
            }
            
            // ========== 4. Дополнительные улучшения ==========
            
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
            
            // Маскируем chrome объект
            if (window.chrome) {
                // Оставляем только runtime для реалистичности
                Object.defineProperty(window.chrome, 'runtime', {
                    get: () => ({
                        onConnect: null,
                        onMessage: null,
                        PlatformOs: {
                            MAC: "mac",
                            WIN: "win",
                            ANDROID: "android",
                            CROS: "cros",
                            LINUX: "linux",
                            OPENBSD: "openbsd"
                        },
                        PlatformArch: {
                            ARM: "arm",
                            X86_32: "x86-32",
                            X86_64: "x86-64"
                        }
                    }),
                    configurable: true
                });
            }
            
            console.log('🍎 Enhanced Safari-like mode activated');
        """)    
    
    @staticmethod
    async def setup_safari_page(page: Page) -> None:
        """Настройка страницы в Safari-подобном стиле"""
        
        # Применяем минимальные скрипты
        await SafariLikeBrowser.apply_safari_scripts(page)
        
        # Устанавливаем Safari-подобные заголовки с русским языком
        await page.set_extra_http_headers({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'max-age=0',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # НЕ блокируем НИКАКИЕ ресурсы - работаем как обычный браузер
        # Safari загружает все ресурсы включая картинки
        
    @staticmethod
    async def navigate_safari_like(page: Page, url: str) -> bool:
        """Safari-подобная навигация"""
        try:
            # Простая навигация как в Safari
            await page.goto(url, timeout=30000, wait_until='networkidle')
            return True
        except Exception as e:
            print(f"❌ Navigation failed: {e}")
            return False
