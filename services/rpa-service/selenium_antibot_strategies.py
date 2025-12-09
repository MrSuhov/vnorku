#!/usr/bin/env python3
"""
Selenium антибот стратегии для обхода защиты сайтов
Замена старого Playwright antibot_strategies.py
"""

import logging
from selenium import webdriver

logger = logging.getLogger(__name__)

class SeleniumAntibotStrategies:
    """Антибот стратегии для Selenium WebDriver"""

    @staticmethod
    def apply_stealth_settings(driver: webdriver.Chrome):
        """Применение базовых stealth настроек через JavaScript"""
        logger.info("🎭 Applying basic stealth JavaScript patches...")

        try:
            # Скрываем webdriver флаг
            driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            # Переопределяем permissions
            driver.execute_script("""
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)

            # Переопределяем chrome объект
            driver.execute_script("""
                window.chrome = {
                    runtime: {}
                };
            """)

            # Переопределяем plugins
            driver.execute_script("""
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
            """)

            # Переопределяем languages
            driver.execute_script("""
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ru-RU', 'ru', 'en-US', 'en']
                });
            """)

            logger.info("✅ Basic stealth patches applied successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to apply stealth patches: {e}")
            return False

    @staticmethod
    def apply_advanced_stealth(driver: webdriver.Chrome):
        """Применение продвинутых stealth настроек для обхода жесткой антибот защиты"""
        logger.info("🛡️ Applying ADVANCED stealth techniques...")

        try:
            # БЛОК 1: Базовые маскировки + улучшенные
            driver.execute_script("""
                // Переопределяем navigator.webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                    configurable: true
                });

                // Удаляем только runtime, оставляем loadTimes (как в реальном Chrome)
                if (window.chrome) {
                    delete window.chrome.runtime;
                    delete window.chrome.csi;
                    delete window.chrome.app;
                    // НЕ удаляем loadTimes - он есть в реальном Chrome!
                }

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
                    get: () => 0,
                    configurable: true
                });

                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ru-RU', 'ru', 'en-US', 'en'],
                    configurable: true
                });

                console.log('🎭 Advanced stealth: Basic properties masked');
            """)

            # БЛОК 2: Реалистичные plugins (5 plugins как в реальном Chrome)
            driver.execute_script("""
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
                                description: "Native Client",
                                filename: "internal-nacl-plugin",
                                length: 1,
                                name: "Native Client"
                            },
                            {
                                0: {type: "application/x-pnacl", suffixes: "", description: "Portable Native Client Executable", enabledPlugin: null},
                                description: "Portable Native Client",
                                filename: "internal-nacl-plugin",
                                length: 1,
                                name: "Portable Native Client"
                            },
                            {
                                0: {type: "application/x-ppapi-widevine-cdm", suffixes: "", description: "Widevine Content Decryption Module", enabledPlugin: null},
                                description: "Widevine Content Decryption Module",
                                filename: "widevinecdmadapter.plugin",
                                length: 1,
                                name: "Widevine Content Decryption Module"
                            }
                        ];
                    },
                    configurable: true
                });

                console.log('🎭 Advanced stealth: Realistic plugins set (5 items)');
            """)

            # БЛОК 3: WebGL - НЕ переопределяем, используем реальные значения системы
            # Реальный Chrome M1 показывает: ANGLE (Apple, ANGLE Metal Renderer: Apple M1...)
            # Подделка на Intel делает fingerprint подозрительным!

            # БЛОК 4: Canvas fingerprinting защита
            driver.execute_script("""
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

                console.log('🎭 Advanced stealth: Canvas fingerprinting protected');
            """)

            # БЛОК 5: Удаляем следы автоматизации (cdc_, webdriver, etc)
            driver.execute_script("""
                Object.keys(window).forEach(key => {
                    if (key.includes('cdc_') || key.includes('webdriver') || key.includes('$chrome_asyncScriptInfo')) {
                        delete window[key];
                    }
                });

                console.log('🎭 Advanced stealth: Automation traces removed');
            """)

            # БЛОК 6: Маскируем Error стеки
            driver.execute_script("""
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

                console.log('🎭 Advanced stealth: Error stacks cleaned');
            """)

            # БЛОК 7: Timezone маскировка (Moscow)
            driver.execute_script("""
                Date.prototype.getTimezoneOffset = function() {
                    return -180; // Moscow timezone (+3)
                };

                console.log('🎭 Advanced stealth: Timezone masked (Moscow)');
            """)

            # БЛОК 8: Permissions API
            driver.execute_script("""
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
                );

                console.log('🎭 Advanced stealth: Permissions API masked');
            """)

            logger.info("✅ ADVANCED stealth techniques applied successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to apply advanced stealth techniques: {e}")
            return False
    

    
    @staticmethod
    def apply_comprehensive_antibot(driver: webdriver.Chrome, lsd_name: str = None):
        """Комплексное применение всех антибот стратегий"""
        logger.info(f"🛡️ Applying comprehensive antibot strategies for {lsd_name or 'unknown LSD'}...")
        
        try:
            # Только stealth патчи - если сайт открылся, больше ничего не нужно
            SeleniumAntibotStrategies.apply_stealth_settings(driver)
            
            logger.info(f"✅ Antibot strategies applied successfully for {lsd_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to apply antibot strategies: {e}")
            return False


class AuchanAntibotStrategy:
    """Специальные стратегии для обхода защиты Auchan"""
    
    @staticmethod
    def apply_auchan_specific_bypass(driver: webdriver.Chrome):
        """Специфичные для Auchan обходы"""
        logger.info("🏪 Applying Auchan-specific antibot bypass...")
        
        try:
            # 1. Базовые stealth настройки
            SeleniumAntibotStrategies.apply_stealth_settings(driver)
            
            # 2. Дополнительные патчи для Auchan
            driver.execute_script("""
                // Переопределяем Date.now для избежания timing attacks
                const originalNow = Date.now;
                const startTime = originalNow();
                Date.now = () => {
                    const elapsed = originalNow() - startTime;
                    return startTime + elapsed + Math.floor(Math.random() * 10);
                };
                
                // Переопределяем performance.now
                if (window.performance && window.performance.now) {
                    const originalPerfNow = window.performance.now;
                    window.performance.now = () => {
                        return originalPerfNow.call(window.performance) + Math.random() * 0.1;
                    };
                }
                
                // Скрываем automation flags
                Object.defineProperty(window, 'outerHeight', {
                    get: () => window.innerHeight,
                    configurable: true
                });
                
                Object.defineProperty(window, 'outerWidth', {
                    get: () => window.innerWidth,
                    configurable: true
                });
                
                console.log('🏪 Auchan antibot patches applied');
            """)
            
            logger.info("✅ Auchan antibot bypass applied successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Auchan antibot bypass failed: {e}")
            return False


def apply_antibot_for_lsd(driver: webdriver.Chrome, lsd_name: str, rpa_config: dict = None):
    """Применение антибот стратегий в зависимости от ЛСД и конфигурации

    Args:
        driver: WebDriver instance
        lsd_name: Название ЛСД
        rpa_config: RPA конфигурация из lsd_configs.rpa_config (опционально)

    Returns:
        True если успешно применены стратегии
    """

    # Проверяем флаг stealth_mode в rpa_config
    use_advanced_stealth = False
    if rpa_config and isinstance(rpa_config, dict):
        antibot_strategies = rpa_config.get('antibot_strategies', {})
        use_advanced_stealth = antibot_strategies.get('stealth_mode', False)

    # Логика применения стратегий
    if lsd_name and lsd_name.lower() in ['auchan', 'ашан']:
        # Auchan имеет специфичную стратегию
        logger.info(f"🏪 Using Auchan-specific antibot strategy")
        return AuchanAntibotStrategy.apply_auchan_specific_bypass(driver)
    elif use_advanced_stealth:
        # Применяем продвинутые техники если stealth_mode=true
        logger.info(f"🛡️ Using ADVANCED stealth mode for {lsd_name} (stealth_mode=true)")
        return SeleniumAntibotStrategies.apply_advanced_stealth(driver)
    else:
        # Применяем базовые техники
        logger.info(f"🎭 Using basic antibot strategy for {lsd_name}")
        return SeleniumAntibotStrategies.apply_comprehensive_antibot(driver, lsd_name)
