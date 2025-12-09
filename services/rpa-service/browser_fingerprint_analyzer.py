#!/usr/bin/env python3
"""
Полный анализ отпечатка браузера для сравнения обычного и автоматизированного
Собирает ВСЕ данные: HTTP заголовки, JavaScript API, WebGL, Canvas, Audio, и т.д.
"""

import json
import logging
import time
from typing import Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import undetected_chromedriver as uc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BrowserFingerprintAnalyzer:
    """Анализатор отпечатков браузера"""
    
    # JavaScript для сбора ВСЕХ возможных данных о браузере
    FINGERPRINT_SCRIPT = """
    async function collectFullFingerprint() {
        const fp = {
            timestamp: new Date().toISOString(),
            
            // ========== NAVIGATOR ==========
            navigator: {
                userAgent: navigator.userAgent,
                appVersion: navigator.appVersion,
                platform: navigator.platform,
                vendor: navigator.vendor,
                language: navigator.language,
                languages: navigator.languages,
                cookieEnabled: navigator.cookieEnabled,
                doNotTrack: navigator.doNotTrack,
                hardwareConcurrency: navigator.hardwareConcurrency,
                maxTouchPoints: navigator.maxTouchPoints,
                productSub: navigator.productSub,
                vendorSub: navigator.vendorSub,
                
                // КРИТИЧНО: webdriver флаг
                webdriver: navigator.webdriver,
                
                // Permissions API
                permissions: await (async () => {
                    try {
                        const perms = {};
                        const permNames = ['geolocation', 'notifications', 'camera', 'microphone'];
                        for (const name of permNames) {
                            try {
                                const result = await navigator.permissions.query({name});
                                perms[name] = result.state;
                            } catch (e) {
                                perms[name] = 'error: ' + e.message;
                            }
                        }
                        return perms;
                    } catch (e) {
                        return {error: e.message};
                    }
                })(),
                
                // User Agent Data (Client Hints)
                userAgentData: navigator.userAgentData ? {
                    brands: navigator.userAgentData.brands,
                    mobile: navigator.userAgentData.mobile,
                    platform: navigator.userAgentData.platform,
                } : null,
                
                // Connection info
                connection: navigator.connection ? {
                    effectiveType: navigator.connection.effectiveType,
                    downlink: navigator.connection.downlink,
                    rtt: navigator.connection.rtt,
                    saveData: navigator.connection.saveData
                } : null,
                
                // Device Memory
                deviceMemory: navigator.deviceMemory,
                
                // Plugins (критично для детекта)
                plugins: Array.from(navigator.plugins || []).map(p => ({
                    name: p.name,
                    description: p.description,
                    filename: p.filename,
                    length: p.length
                })),
                
                // MIME Types
                mimeTypes: Array.from(navigator.mimeTypes || []).map(m => ({
                    type: m.type,
                    description: m.description,
                    suffixes: m.suffixes
                }))
            },
            
            // ========== WINDOW ==========
            window: {
                innerWidth: window.innerWidth,
                innerHeight: window.innerHeight,
                outerWidth: window.outerWidth,
                outerHeight: window.outerHeight,
                screenX: window.screenX,
                screenY: window.screenY,
                pageXOffset: window.pageXOffset,
                pageYOffset: window.pageYOffset,
                devicePixelRatio: window.devicePixelRatio,
                
                // Chrome объект (есть только в настоящем Chrome)
                hasChrome: typeof window.chrome !== 'undefined',
                chromeKeys: typeof window.chrome !== 'undefined' ? Object.keys(window.chrome) : [],
                
                // WebDriver флаги
                hasWebDriver: 'webdriver' in window,
                hasCallPhantom: '_phantom' in window || 'callPhantom' in window,
                hasPhantom: 'phantom' in window,
                
                // Размеры различаются у автоматизированных браузеров
                sizeMismatch: (window.outerWidth - window.innerWidth) < 50 || 
                              (window.outerHeight - window.innerHeight) < 50
            },
            
            // ========== SCREEN ==========
            screen: {
                width: screen.width,
                height: screen.height,
                availWidth: screen.availWidth,
                availHeight: screen.availHeight,
                colorDepth: screen.colorDepth,
                pixelDepth: screen.pixelDepth,
                orientation: screen.orientation ? {
                    type: screen.orientation.type,
                    angle: screen.orientation.angle
                } : null
            },
            
            // ========== DOCUMENT ==========
            document: {
                title: document.title,
                referrer: document.referrer,
                characterSet: document.characterSet,
                documentElement: {
                    clientWidth: document.documentElement.clientWidth,
                    clientHeight: document.documentElement.clientHeight,
                    scrollWidth: document.documentElement.scrollWidth,
                    scrollHeight: document.documentElement.scrollHeight
                },
                hidden: document.hidden,
                visibilityState: document.visibilityState,
                
                // Проверка на $cdc_ переменные (признак ChromeDriver)
                hasCdcProps: (() => {
                    const props = [];
                    for (let prop in document) {
                        if (prop.match(/\\$[a-z]dc_/) && document[prop]) {
                            props.push(prop);
                        }
                    }
                    return props;
                })()
            },
            
            // ========== WEBGL ==========
            webgl: (() => {
                try {
                    const canvas = document.createElement('canvas');
                    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                    if (!gl) return {error: 'WebGL not supported'};
                    
                    const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
                    return {
                        vendor: gl.getParameter(gl.VENDOR),
                        renderer: gl.getParameter(gl.RENDERER),
                        version: gl.getParameter(gl.VERSION),
                        shadingLanguageVersion: gl.getParameter(gl.SHADING_LANGUAGE_VERSION),
                        unmaskedVendor: debugInfo ? gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) : null,
                        unmaskedRenderer: debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : null,
                        supportedExtensions: gl.getSupportedExtensions()
                    };
                } catch (e) {
                    return {error: e.message};
                }
            })(),
            
            // ========== CANVAS ==========
            canvas: (() => {
                try {
                    const canvas = document.createElement('canvas');
                    const ctx = canvas.getContext('2d');
                    canvas.width = 200;
                    canvas.height = 50;
                    
                    ctx.textBaseline = 'top';
                    ctx.font = '14px Arial';
                    ctx.fillStyle = '#f60';
                    ctx.fillRect(0, 0, 100, 50);
                    ctx.fillStyle = '#069';
                    ctx.fillText('Canvas 🎨 Test', 2, 15);
                    
                    return {
                        dataURL: canvas.toDataURL(),
                        hash: canvas.toDataURL().slice(-50) // последние 50 символов для компактности
                    };
                } catch (e) {
                    return {error: e.message};
                }
            })(),
            
            // ========== AUDIO ==========
            audio: (() => {
                try {
                    const AudioContext = window.AudioContext || window.webkitAudioContext;
                    if (!AudioContext) return {error: 'AudioContext not supported'};
                    
                    const context = new AudioContext();
                    const oscillator = context.createOscillator();
                    const analyser = context.createAnalyser();
                    const gainNode = context.createGain();
                    const scriptProcessor = context.createScriptProcessor(4096, 1, 1);
                    
                    gainNode.gain.value = 0;
                    oscillator.connect(analyser);
                    analyser.connect(scriptProcessor);
                    scriptProcessor.connect(gainNode);
                    gainNode.connect(context.destination);
                    oscillator.start(0);
                    
                    return {
                        sampleRate: context.sampleRate,
                        channelCount: context.destination.maxChannelCount,
                        channelCountMode: context.destination.channelCountMode,
                        channelInterpretation: context.destination.channelInterpretation,
                        state: context.state,
                        baseLatency: context.baseLatency,
                        outputLatency: context.outputLatency
                    };
                } catch (e) {
                    return {error: e.message};
                }
            })(),
            
            // ========== FONTS ==========
            fonts: (() => {
                const baseFonts = ['monospace', 'sans-serif', 'serif'];
                const testFonts = [
                    'Arial', 'Verdana', 'Times New Roman', 'Courier New', 
                    'Georgia', 'Palatino', 'Garamond', 'Bookman', 'Comic Sans MS',
                    'Trebuchet MS', 'Arial Black', 'Impact'
                ];
                
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                const text = 'mmmmmmmmmmlli';
                
                const baselines = {};
                baseFonts.forEach(font => {
                    ctx.font = '72px ' + font;
                    baselines[font] = ctx.measureText(text).width;
                });
                
                const detectedFonts = [];
                testFonts.forEach(font => {
                    let detected = false;
                    baseFonts.forEach(baseFont => {
                        ctx.font = '72px ' + font + ',' + baseFont;
                        const width = ctx.measureText(text).width;
                        if (width !== baselines[baseFont]) {
                            detected = true;
                        }
                    });
                    if (detected) detectedFonts.push(font);
                });
                
                return detectedFonts;
            })(),
            
            // ========== TIMING ==========
            timing: {
                // Performance timing
                performance: performance.timing ? {
                    navigationStart: performance.timing.navigationStart,
                    loadEventEnd: performance.timing.loadEventEnd,
                    domContentLoadedEventEnd: performance.timing.domContentLoadedEventEnd
                } : null,
                
                // High resolution time
                now: performance.now(),
                
                // Проверка на манипуляцию Date
                dateTest: (() => {
                    const d1 = Date.now();
                    const d2 = new Date().getTime();
                    const d3 = +new Date();
                    return {
                        diff_d1_d2: Math.abs(d1 - d2),
                        diff_d2_d3: Math.abs(d2 - d3),
                        suspiciousGap: Math.abs(d1 - d2) > 1 || Math.abs(d2 - d3) > 1
                    };
                })()
            },
            
            // ========== ERRORS & STACKTRACE ==========
            errorAnalysis: (() => {
                try {
                    throw new Error('test');
                } catch (e) {
                    return {
                        stack: e.stack,
                        // Ищем признаки автоматизации в стеке
                        hasAutomationTraces: e.stack ? (
                            e.stack.includes('webdriver') ||
                            e.stack.includes('selenium') ||
                            e.stack.includes('phantomjs') ||
                            e.stack.includes('headless')
                        ) : false
                    };
                }
            })(),
            
            // ========== CSS & MEDIA ==========
            css: {
                prefersColorScheme: window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light',
                prefersReducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
                hoverCapability: window.matchMedia('(hover: hover)').matches,
                pointerType: window.matchMedia('(pointer: coarse)').matches ? 'coarse' : 'fine'
            },
            
            // ========== BATTERY ==========
            battery: await (async () => {
                try {
                    if ('getBattery' in navigator) {
                        const battery = await navigator.getBattery();
                        return {
                            charging: battery.charging,
                            level: battery.level,
                            chargingTime: battery.chargingTime,
                            dischargingTime: battery.dischargingTime
                        };
                    }
                    return null;
                } catch (e) {
                    return {error: e.message};
                }
            })(),
            
            // ========== TIMEZONE ==========
            timezone: {
                offset: new Date().getTimezoneOffset(),
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                locale: Intl.DateTimeFormat().resolvedOptions().locale
            },
            
            // ========== HTTP HEADERS (from page) ==========
            // Эти данные нужно получать через CDP или прокси
            httpHeadersNote: "HTTP headers should be captured via CDP or proxy",
            
            // ========== AUTOMATION DETECTION SUMMARY ==========
            automationFlags: {
                hasWebdriverProperty: navigator.webdriver === true,
                hasWebdriverInWindow: 'webdriver' in window,
                hasCdcProperties: (() => {
                    for (let prop in document) {
                        if (prop.match(/\\$[a-z]dc_/)) return true;
                    }
                    return false;
                })(),
                hasPhantomProperties: '_phantom' in window || 'callPhantom' in window,
                hasAutomationExtension: (() => {
                    const img = document.createElement('img');
                    return img.complete === undefined;
                })(),
                pluginsLengthZero: navigator.plugins.length === 0,
                languagesEmpty: navigator.languages.length === 0,
                chromeObjectMissing: typeof window.chrome === 'undefined'
            }
        };
        
        return fp;
    }
    
    return await collectFullFingerprint();
    """
    
    @staticmethod
    def create_normal_chrome() -> webdriver.Chrome:
        """Создает обычный Chrome с минимальными настройками"""
        logger.info("🌐 Creating NORMAL Chrome browser...")
        
        options = Options()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Chrome(service=Service(), options=options)
        logger.info("✅ Normal Chrome created")
        return driver
    
    @staticmethod
    def create_undetected_chrome() -> uc.Chrome:
        """Создает undetected Chrome"""
        logger.info("🕵️ Creating UNDETECTED Chrome browser...")
        
        options = uc.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        # Блокировка разрешений
        prefs = {
            'profile.default_content_setting_values': {
                'geolocation': 2,
                'notifications': 2,
                'media_stream_mic': 2,
                'media_stream_camera': 2
            },
            'credentials_enable_service': False,
            'profile.password_manager_enabled': False
        }
        options.add_experimental_option('prefs', prefs)
        
        driver = uc.Chrome(options=options, version_main=140)
        logger.info("✅ Undetected Chrome created")
        return driver
    
    @staticmethod
    def collect_fingerprint(driver: webdriver.Chrome, browser_type: str) -> Dict[str, Any]:
        """Собирает полный отпечаток браузера"""
        logger.info(f"📊 Collecting fingerprint for {browser_type}...")
        
        try:
            # Переходим на пустую страницу
            driver.get("about:blank")
            time.sleep(2)
            
            # Выполняем JavaScript для сбора данных
            fingerprint = driver.execute_script(BrowserFingerprintAnalyzer.FINGERPRINT_SCRIPT)
            
            # Добавляем метаданные
            fingerprint['browser_type'] = browser_type
            fingerprint['current_url'] = driver.current_url
            
            logger.info(f"✅ Fingerprint collected for {browser_type}")
            return fingerprint
            
        except Exception as e:
            logger.error(f"❌ Failed to collect fingerprint: {e}")
            return {"error": str(e), "browser_type": browser_type}
    
    @staticmethod
    def save_fingerprint(fingerprint: Dict[str, Any], filename: str):
        """Сохраняет отпечаток в JSON файл"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(fingerprint, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"💾 Fingerprint saved to {filename}")
        except Exception as e:
            logger.error(f"❌ Failed to save fingerprint: {e}")
    
    @staticmethod
    def compare_fingerprints(fp1: Dict[str, Any], fp2: Dict[str, Any]) -> Dict[str, Any]:
        """Сравнивает два отпечатка и находит различия"""
        logger.info("🔍 Comparing fingerprints...")
        
        differences = {}
        
        def compare_recursive(obj1, obj2, path=""):
            if type(obj1) != type(obj2):
                differences[path] = {
                    "type1": type(obj1).__name__,
                    "type2": type(obj2).__name__,
                    "value1": obj1,
                    "value2": obj2
                }
                return
            
            if isinstance(obj1, dict):
                all_keys = set(obj1.keys()) | set(obj2.keys())
                for key in all_keys:
                    new_path = f"{path}.{key}" if path else key
                    if key not in obj1:
                        differences[new_path] = {"missing_in": "fp1", "value": obj2[key]}
                    elif key not in obj2:
                        differences[new_path] = {"missing_in": "fp2", "value": obj1[key]}
                    else:
                        compare_recursive(obj1[key], obj2[key], new_path)
            
            elif isinstance(obj1, list):
                if len(obj1) != len(obj2):
                    differences[f"{path}.__length__"] = {
                        "length1": len(obj1),
                        "length2": len(obj2)
                    }
                for i, (item1, item2) in enumerate(zip(obj1, obj2)):
                    compare_recursive(item1, item2, f"{path}[{i}]")
            
            else:
                if obj1 != obj2:
                    differences[path] = {
                        "value1": obj1,
                        "value2": obj2
                    }
        
        compare_recursive(fp1, fp2)
        
        logger.info(f"✅ Found {len(differences)} differences")
        return differences


def main():
    """Основная функция - собирает и сравнивает отпечатки"""
    
    logger.info("=" * 80)
    logger.info("🚀 Browser Fingerprint Analysis Started")
    logger.info("=" * 80)
    
    # Создаем директорию для результатов
    import os
    results_dir = "../../logs/fingerprints"
    os.makedirs(results_dir, exist_ok=True)
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    # 1. Анализ обычного Chrome
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 1: Normal Chrome Analysis")
    logger.info("=" * 80)
    
    normal_driver = None
    normal_fp = None
    try:
        normal_driver = BrowserFingerprintAnalyzer.create_normal_chrome()
        normal_fp = BrowserFingerprintAnalyzer.collect_fingerprint(normal_driver, "normal_chrome")
        BrowserFingerprintAnalyzer.save_fingerprint(
            normal_fp, 
            f"{results_dir}/normal_chrome_{timestamp}.json"
        )
    except Exception as e:
        logger.error(f"❌ Normal Chrome analysis failed: {e}")
    finally:
        if normal_driver:
            normal_driver.quit()
            logger.info("🚪 Normal Chrome closed")
    
    time.sleep(3)
    
    # 2. Анализ undetected Chrome
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 2: Undetected Chrome Analysis")
    logger.info("=" * 80)
    
    undetected_driver = None
    undetected_fp = None
    try:
        undetected_driver = BrowserFingerprintAnalyzer.create_undetected_chrome()
        undetected_fp = BrowserFingerprintAnalyzer.collect_fingerprint(undetected_driver, "undetected_chrome")
        BrowserFingerprintAnalyzer.save_fingerprint(
            undetected_fp,
            f"{results_dir}/undetected_chrome_{timestamp}.json"
        )
    except Exception as e:
        logger.error(f"❌ Undetected Chrome analysis failed: {e}")
    finally:
        if undetected_driver:
            undetected_driver.quit()
            logger.info("🚪 Undetected Chrome closed")
    
    # 3. Сравнение
    if normal_fp and undetected_fp:
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 3: Comparison")
        logger.info("=" * 80)
        
        differences = BrowserFingerprintAnalyzer.compare_fingerprints(normal_fp, undetected_fp)
        BrowserFingerprintAnalyzer.save_fingerprint(
            differences,
            f"{results_dir}/comparison_{timestamp}.json"
        )
        
        # Выводим критичные различия
        logger.info("\n" + "🔥 CRITICAL AUTOMATION FLAGS:")
        if 'automationFlags' in normal_fp and 'automationFlags' in undetected_fp:
            for flag, value in undetected_fp['automationFlags'].items():
                normal_value = normal_fp['automationFlags'].get(flag)
                if value != normal_value:
                    logger.warning(f"  ⚠️  {flag}: normal={normal_value}, undetected={value}")
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ Analysis Complete!")
    logger.info(f"📁 Results saved to: {results_dir}/")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
