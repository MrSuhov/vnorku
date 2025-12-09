"""
Универсальный RPA-движок для авторизации в различных ЛСД
Поддерживает XPath селекторы, SMS-верификацию и сложные флоу
"""

import asyncio
import json
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
import logging
import re
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from .advanced_stealth import AdvancedStealth
from .ozon_stealth import OzonStealth
from .safari_like import SafariLikeBrowser

logger = logging.getLogger(__name__)


class RPASession:
    """Сессия RPA выполнения"""
    
    def __init__(self, session_id: str, config: Dict[str, Any]):
        self.id = session_id
        self.config = config
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.status = "created"
        self.current_step = 0
        self.step_results = {}
        self.context_data = {}  # Для хранения данных между шагами
        self.created_at = datetime.now()
        
    def get_steps_from(self, step_id: str) -> List[Dict[str, Any]]:
        """Получить шаги начиная с указанного step_id"""
        steps = self.config.get('steps', [])
        start_index = 0
        
        for i, step in enumerate(steps):
            if step.get('id') == step_id:
                start_index = i
                break
                
        return steps[start_index:]


class UniversalRPAEngine:
    """Универсальный RPA-движок"""
    
    def __init__(self, headless: bool = True, debug: bool = False):
        self.headless = headless
        self.debug = debug
        self.active_sessions: Dict[str, RPASession] = {}
        
    async def start_session(self, config: Dict[str, Any]) -> RPASession:
        """Запуск новой RPA сессии"""
        session_id = f"rpa_{int(datetime.now().timestamp())}_{len(self.active_sessions)}"
        session = RPASession(session_id, config)
        
        # Инициализируем браузер
        await self._init_browser(session)
        
        self.active_sessions[session_id] = session
        session.status = "initialized"
        
        logger.info(f"Started RPA session {session_id}")
        return session
        
    async def get_session(self, session_id: str) -> Optional[RPASession]:
        """Получить сессию по ID"""
        return self.active_sessions.get(session_id)
        
    async def execute_step(self, session: RPASession, step: Dict[str, Any], credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнение одного шага"""
        step_id = step.get('id', f'step_{session.current_step}')
        action = step['action']
        
        logger.info(f"Executing step {step_id}: {action}")
        
        # Проверяем зависимость шага
        depends_on = step.get('depends_on')
        if depends_on:
            # Проверяем что зависимый шаг выполнился успешно
            if depends_on in session.step_results:
                dependency_result = session.step_results[depends_on]
                if dependency_result.get('status') != 'success' or not dependency_result.get('verified', True):
                    logger.warning(f"⚠️ Skipping step {step_id} - dependency {depends_on} failed")
                    return {
                        'status': 'skipped',
                        'reason': f'Dependency {depends_on} failed',
                        'dependency_status': dependency_result.get('status')
                    }
            else:
                logger.warning(f"⚠️ Skipping step {step_id} - dependency {depends_on} not executed")
                return {
                    'status': 'skipped', 
                    'reason': f'Dependency {depends_on} not found'
                }
        
        try:
            if action == 'navigate':
                result = await self._navigate(session, step)
            elif action == 'hover':
                result = await self._hover(session, step)
            elif action == 'click':
                result = await self._click_element(session, step)
            elif action == 'wait_and_click':
                result = await self._wait_and_click_element(session, step)
            elif action == 'wait_for_element':
                result = await self._wait_for_element(session, step)
            elif action == 'wait_for_navigation':
                result = await self._wait_for_navigation(session, step)
            elif action == 'type_multi_field':
                result = await self._type_multi_field(session, step, credentials)
            elif action == 'type':
                result = await self._type_text(session, step, credentials)
            elif action == 'uncheck':
                result = await self._uncheck_element(session, step)
            elif action == 'wait_for':
                result = await self._wait_for_element(session, step)
            elif action == 'clear':
                result = await self._clear_element(session, step)
            elif action == 'clear_and_wait':
                result = await self._clear_and_wait(session, step)
            elif action == 'scroll_into_view':
                result = await self._scroll_into_view(session, step)
            elif action == 'save_cookies':
                result = await self._save_cookies(session, step, credentials)
            elif action == 'save_session':
                result = await self._save_cookies(session, step, credentials)
            elif action == 'extract_qr_link':
                result = await self._extract_qr_link(session, step, credentials)
            elif action == 'verify_redirect':
                result = await self._verify_redirect(session, step, credentials)
            elif action == 'cleanup':
                result = await self._cleanup_session(session, step, credentials)
            elif action == 'request_sms_code':
                result = await self._request_sms_code(session, step)
            elif action == 'hover':
                result = await self._hover(session, step)
            else:
                raise ValueError(f"Unknown action: {action}")
                
            # Сохраняем результат
            session.step_results[step_id] = result
            session.current_step += 1
            
            # Проверяем условие успеха
            if step.get('success'):
                # НЕ завершаем сессию сразу! Продолжаем выполнение критичных шагов
                session.context_data['success_step_completed'] = step_id
                logger.info(f"✅ Success step {step_id} completed, but continuing with critical steps...")
                
            return result
            
        except Exception as e:
            logger.error(f"Step {step_id} failed: {e}")
            if step.get('optional', False):
                return {'status': 'skipped', 'reason': str(e)}
            
            # Для критических шагов (save_cookies, verify_success, SMS шаги) не прерываем выполнение
            if step_id in ['save_cookies', 'verify_success', 'save_session', 'cleanup', 'cleanup_session', 'enter_sms', 'submit_sms']:
                logger.warning(f"⚠️ Critical step {step_id} failed, but continuing execution")
                return {'status': 'warning', 'error': str(e)}
            
            # Для остальных шагов - останавливаемся на ошибках
            session.status = 'error'
            raise
    

    async def execute_steps(self, session: RPASession, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнение всех шагов RPA с правильной обработкой success флага и QR авторизации"""
        try:
            steps = session.config.get('steps', [])
            logger.info(f"🚀 Starting execution of {len(steps)} RPA steps for session {session.id}")
            
            # 🔧 ИСПРАВЛЕНИЕ: Сохраняем важные данные из credentials в контекст сессии
            if credentials:
                telegram_id = credentials.get('telegram_id')
                lsd_name = credentials.get('lsd_name')
                phone = credentials.get('phone')
                
                if telegram_id:
                    session.context_data['telegram_id'] = telegram_id
                    logger.info(f"💾 FIXED: Saved telegram_id={telegram_id} to session context")
                if lsd_name:
                    session.context_data['lsd_name'] = lsd_name
                if phone:
                    session.context_data['phone'] = phone
                    
                # Также сохраняем полные credentials в контексте
                session.context_data['credentials'] = credentials
                logger.info(f"📦 Credentials saved to session context: telegram_id={telegram_id}, lsd_name={lsd_name}")
            
            session.status = 'running'
            
            for i, step in enumerate(steps):
                step_id = step.get('id', f'step_{i}')
                
                logger.info(f"▶️ [{i+1}/{len(steps)}] Executing step: {step_id}")
                
                try:
                    result = await self.execute_step(session, step, credentials)
                    logger.info(f"✅ Step {step_id} completed with status: {result.get('status')}")
                    
                    # 🚨 ИСПРАВЛЕНИЕ: Проверяем, требует ли шаг остановки для пользовательского ввода
                    if result.get('status') == 'waiting_for_user_input':
                        logger.info(f"⏸️ PAUSED: Step {step_id} requires user input - stopping execution")
                        session.context_data['paused_at_step'] = i  # Сохраняем индекс текущего шага
                        session.context_data['remaining_steps'] = len(steps) - i - 1  # Количество оставшихся шагов
                        return {
                            'status': 'waiting_for_user_input',
                            'message': result.get('message', 'Требуется пользовательский ввод'),
                            'input_type': result.get('input_type', 'sms_code'),
                            'session_id': session.id,
                            'paused_at_step': step_id,
                            'remaining_steps': len(steps) - i - 1
                        }
                    
                    # Специальная обработка для extract_qr_link - НЕ завершаем сессию!
                    if step_id == 'extract_qr_link':
                        if result.get('status') in ['success', 'no_qr_found']:
                            logger.info(f"📱 QR extraction completed, continuing to wait for user authorization...")
                            # Продолжаем выполнение - НЕ останавливаемся здесь!
                            continue
                    
                    # Проверяем, достигли ли мы НАСТОЯЩЕГО success шага (обычно verify_success)
                    if step.get('success') and result.get('status') == 'success':
                        logger.info(f"🎉 SUCCESS step {step_id} completed! Executing ALL remaining steps...")
                        
                        # 🚨 ИСПРАВЛЕНИЕ: Выполняем ВСЕ оставшиеся шаги после success (особенно save_cookies и cleanup)
                        remaining_steps = steps[i+1:]
                        remaining_steps_executed = 0
                        critical_steps_executed = 0
                        
                        for j, next_step in enumerate(remaining_steps):
                            next_step_id = next_step.get('id', f'step_{i+1+j}')
                            is_critical = next_step_id in ['save_cookies', 'save_session', 'cleanup', 'cleanup_session']
                            
                            logger.info(f"🔄 Executing remaining step after success: {next_step_id} {'(CRITICAL)' if is_critical else ''}")
                            
                            try:
                                next_result = await self.execute_step(session, next_step, credentials)
                                logger.info(f"✅ Post-success step {next_step_id} result: {next_result.get('status')}")
                                remaining_steps_executed += 1
                                if is_critical:
                                    critical_steps_executed += 1
                            except Exception as e:
                                logger.error(f"❌ Post-success step {next_step_id} failed: {e}")
                                if is_critical:
                                    # Для критических шагов продолжаем выполнение даже при ошибках
                                    logger.warning(f"⚠️ Critical step {next_step_id} failed, but continuing execution")
                                    continue
                                else:
                                    # Для некритических шагов тоже продолжаем после success
                                    logger.warning(f"⚠️ Non-critical step {next_step_id} failed after success, continuing")
                                    continue
                        
                        logger.info(f"🔄 Executed {remaining_steps_executed} remaining steps after success ({critical_steps_executed} critical)")
                        
                        # Завершаем сессию как успешную
                        session.status = 'completed'
                        return {
                            'status': 'completed',
                            'success': True,
                            'message': f'RPA завершено успешно на шаге {step_id}',
                            'success_step': step_id,
                            'remaining_steps_executed': remaining_steps_executed,
                            'critical_steps_executed': critical_steps_executed
                        }
                    
                except Exception as e:
                    logger.error(f"❌ Step {step_id} failed: {e}")
                    
                    # Проверяем, критический ли это шаг
                    if step_id in ['save_cookies', 'verify_success', 'save_session', 'cleanup', 'cleanup_session']:
                        logger.warning(f"⚠️ Critical step {step_id} failed, but continuing")
                        continue
                    else:
                        # Для некритических шагов останавливаемся
                        session.status = 'error'
                        return {
                            'status': 'error',
                            'error': f'Step {step_id} failed: {str(e)}',
                            'failed_step': step_id
                        }
            
            # Если дошли до конца без explicit success
            session.status = 'completed'
            return {
                'status': 'completed',
                'success': True,
                'message': 'Все шаги RPA выполнены'
            }
            
        except Exception as e:
            logger.error(f"❌ Fatal error in RPA execution: {e}")
            session.status = 'error'
            return {
                'status': 'error',
                'error': str(e)
            }

    async def _ensure_critical_steps_completion(self, session: RPASession, steps: List[Dict[str, Any]], credentials: Dict[str, Any]):
        """Принудительное выполнение критически важных шагов после success"""
        try:
            success_step = session.context_data.get('success_step_completed')
            if not success_step:
                return
            
            logger.info(f"🔄 Ensuring critical steps are completed after success step: {success_step}")
            
            # Находим критические шаги, которые должны выполниться после success
            critical_step_ids = ['save_cookies', 'save_session', 'cleanup', 'cleanup_session']
            
            for step in steps:
                step_id = step.get('id', '')
                
                if step_id in critical_step_ids:
                    # Проверяем, был ли уже выполнен этот шаг
                    if step_id not in session.step_results:
                        logger.info(f"🚨 Force-executing critical step: {step_id}")
                        
                        try:
                            result = await self.execute_step(session, step, credentials)
                            logger.info(f"✅ Critical step {step_id} completed with result: {result.get('status')}")
                        except Exception as e:
                            logger.error(f"❌ Critical step {step_id} failed: {e}")
                            # Продолжаем выполнение даже при ошибке
                            continue
            
            logger.info("🔄 Critical steps completion check finished")
            
        except Exception as e:
            logger.error(f"❌ Error in critical steps completion: {e}")
            
    async def _init_browser(self, session: RPASession):
        """Инициализация браузера с поддержкой профилей"""
        from browser_profile_manager import profile_manager, UniversalStealth
        
        playwright = await async_playwright().start()
        
        # Проверяем, указан ли browser_profile в RPA конфигурации
        profile_name = session.config.get('browser_profile')
        if profile_name:
            logger.info(f"🎭 Using specified browser profile: {profile_name}")
        else:
            # Определяем профиль по URL или используем дефолтный
            base_url = session.config.get('base_url', '')
            if 'samokat' in base_url.lower():
                profile_name = 'samokat_antibot_profile'
                logger.info(f"🎯 Detected Samokat - auto-selecting profile: {profile_name}")
            elif 'ozon' in base_url.lower():
                profile_name = 'ozon_stealth_profile'  # Если такой есть
                logger.info(f"🎯 Detected Ozon - auto-selecting profile: {profile_name}")
            else:
                profile_name = profile_manager.default_profile
                logger.info(f"🎭 Using default browser profile: {profile_name}")
        
        # Получаем настройки из профиля
        browser_args = profile_manager.get_browser_args(profile_name)
        context_options = profile_manager.get_context_options(profile_name)
        
        logger.info(f"🚀 Launching browser with profile '{profile_name}'")
        
        # Определяем браузер (пока используем Chromium)
        session.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=browser_args,
            slow_mo=0 if not self.debug else 50
        )
        
        # Создаем контекст с настройками из профиля
        session.context = await session.browser.new_context(**context_options)
        session.page = await session.context.new_page()
        
        # Применяем универсальную stealth-маскировку из профиля
        await UniversalStealth.apply_profile_stealth(session.page, profile_name)
        logger.info(f"✅ Browser initialized with profile '{profile_name}' and stealth applied")
        
        if self.debug:
            session.page.on('console', lambda msg: logger.debug(f"Browser console: {msg.text}"))
            session.page.on('response', lambda response: 
                logger.debug(f"Response: {response.url} - {response.status}") 
                if response.status >= 400 else None)
            
    async def _apply_minimal_stealth(self, page: Page) -> None:
        """Минимальная маскировка для быстрой работы"""
        # Только самые базовые скрипты маскировки
        await page.add_init_script("""
            // Убираем только основные признаки автоматизации
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true
            });
            
            // НЕ блокируем картинки и ресурсы!
            console.log('⚡ Minimal stealth mode activated');
        """)        
        
    async def _navigate(self, session: RPASession, step: Dict[str, Any]) -> Dict[str, Any]:
        """Навигация Safari-подобная с поддержкой медленных сайтов"""
        url = step['url']
        timeout = step.get('timeout', 30000)
        wait_for_load = step.get('wait_for_load', 'domcontentloaded')
        additional_wait = step.get('additional_wait', 0)
        
        logger.info(f"Navigating to: {url} (timeout: {timeout}ms, wait_for_load: {wait_for_load})")
        
        # Определяем, это Ozon или другой сайт
        is_ozon = 'ozon' in url.lower()
        
        if is_ozon:
            # Специальная навигация для Ozon
            logger.info("🎯 Using special Ozon navigation")
            success = await OzonStealth.navigate_to_ozon_safely(session.page, url)
            if not success:
                raise Exception("Ozon blocked access - enhanced stealth failed")
        else:
            # Safari-подобная навигация с поддержкой медленных сайтов
            try:
                # Для медленных сайтов ждем networkidle или load
                wait_until = wait_for_load if wait_for_load in ['load', 'domcontentloaded', 'networkidle'] else 'domcontentloaded'
                
                response = await session.page.goto(
                    url, 
                    wait_until=wait_until, 
                    timeout=timeout
                )
                
                if not response or response.status >= 400:
                    raise Exception(f"Navigation failed with status {response.status if response else 'None'}")
                
                logger.info(f"✅ Navigation successful: {response.status} {response.url}")
                
                # Дополнительное ожидание для медленных сайтов
                if additional_wait > 0:
                    logger.info(f"⏳ Additional wait: {additional_wait}ms")
                    await asyncio.sleep(additional_wait / 1000)
                    
            except Exception as e:
                logger.error(f"❌ Navigation error: {e}")
                raise Exception(f"Navigation failed to {url}: {str(e)}")
        
        # Ждем появления элементов если указано
        if 'wait_for' in step:
            await self._wait_for_condition(session, step['wait_for'], timeout)
            
        return {'status': 'success', 'url': session.page.url}
        
    async def _hover(self, session: RPASession, step: Dict[str, Any]) -> Dict[str, Any]:
        """Наведение мыши на элемент (для выпадающих меню)"""
        timeout = step.get('timeout', 10000)
        wait_after = step.get('wait_after', 1000)
        
        logger.info(f"🖱️ Hovering element for step '{step['id']}'")
        
        element = await self._find_element_with_selectors(session, step, timeout)
        if not element:
            raise Exception(f"Element not found for step {step['id']}")
        
        try:
            # Наводим мышь на элемент
            await element.hover()
            logger.info(f"✅ Hover successful on element")
            
            # Ждем появления меню/эффекта
            if wait_after > 0:
                await asyncio.sleep(wait_after / 1000)
                
            return {'status': 'success'}
            
        except Exception as e:
            logger.error(f"❌ Hover failed: {e}")
            raise Exception(f"Hover failed for step {step['id']}: {str(e)}")
    
    async def _click_element(self, session: RPASession, step: Dict[str, Any]) -> Dict[str, Any]:
        """Быстрый клик по элементу"""
        element = await self.find_element(session.page, step)
        if not element:
            raise Exception(f"Element not found for step {step.get('id')}")
        
        # Быстрый клик
        await element.scroll_into_view_if_needed()
        await element.click()
        
        # Ожидаем появления следующих элементов с коротким таймаутом
        if 'wait_for' in step:
            await self._wait_for_condition(session, step['wait_for'], step.get('timeout', 2000))
            
        # Минимальная задержка только если указана
        if step.get('wait_after'):
            await asyncio.sleep(min(step['wait_after'] / 1000, 1.0))  # Максимум 1 секунда
            
        return {'status': 'success'}
        
    async def _extract_qr_link(self, session: RPASession, step: Dict[str, Any], credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Извлечение ссылки из QR кода через новую универсальную функцию extract_qr()"""
        try:
            # Импортируем из services/rpa-service/universal_rpa_engine.py
            import sys
            import os
            
            # Добавляем путь к services/rpa-service если его нет
            rpa_service_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'services', 'rpa-service')
            if rpa_service_path not in sys.path:
                sys.path.append(rpa_service_path)
            
            from universal_rpa_engine import extract_qr
            
            logger.info(f"🚀 Using universal extract_qr() function for step extract_qr_link")
            
            # Получаем telegram_id из credentials
            telegram_id = credentials.get('telegram_id')
            if not telegram_id:
                raise ValueError("telegram_id not found in credentials")
            
            # Используем новую универсальную функцию
            result = await extract_qr(
                driver_or_page=session.page,
                step=step,
                step_id='extract_qr_link',
                telegram_id=telegram_id
            )
            
            # Проверяем результат
            if result.get('status') == 'success':
                logger.info(f"✅ Universal extract_qr() successful: method={result.get('method')}, engine={result.get('engine')}")
                return result
            else:
                logger.error(f"❌ Universal extract_qr() failed: {result.get('message')}")
                return result
                
        except ImportError as e:
            logger.error(f"❌ Missing universal_rpa_engine module: {e}")
            logger.error("⚠️ Falling back to legacy Playwright QR extraction...")
            
            # Fallback на старую логику Playwright
            return await self._extract_qr_link_legacy_playwright(session, step, credentials)
            
        except Exception as e:
            logger.error(f"❌ Error in universal QR extraction: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def _extract_qr_link_legacy_playwright(self, session: RPASession, step: Dict[str, Any], credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Старая логика извлечения QR кода для Playwright (fallback)"""
        try:
            import tempfile
            import os
            from pyzbar import pyzbar
            from PIL import Image
            import httpx
            
            logger.info(f"📱 Using legacy Playwright QR extraction...")
            
            # Ждем немного чтобы QR код полностью загрузился
            await asyncio.sleep(2)
            
            # Делаем скриншот всей страницы
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                screenshot_path = temp_file.name
            
            await session.page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"📸 Legacy screenshot saved: {screenshot_path}")
            
            # Декодируем QR код из полного скриншота
            qr_link = await self._decode_qr_from_image(screenshot_path, "legacy full page")
            
            # Удаляем временный файл
            try:
                os.unlink(screenshot_path)
            except:
                pass
            
            # Если QR код найден, отправляем в Telegram бот
            if qr_link:
                telegram_id = credentials.get('telegram_id')
                if telegram_id:
                    try:
                        # Проверяем что это похоже на QR ссылку
                        if len(qr_link) > 10 and ('http' in qr_link or 'yandex' in qr_link or 'ozon' in qr_link or len(qr_link) > 20):
                            async with httpx.AsyncClient() as client:
                                bot_request = {
                                    "telegram_id": telegram_id,
                                    "qr_link": qr_link,
                                    "action": "qr_code_extracted",
                                    "message": f"Для авторизации пройдите по ссылке\n{qr_link}",
                                    "method": "legacy_playwright_full_page"
                                }
                                
                                response = await client.post(
                                    "http://localhost:8001/rpa/qr-code-extracted",
                                    json=bot_request,
                                    timeout=10.0
                                )
                                
                                if response.status_code == 200:
                                    logger.info("📱 Legacy QR link sent successfully")
                                else:
                                    logger.error(f"❌ Legacy bot request failed: {response.status_code}")
                        else:
                            logger.warning(f"⚠️ Legacy QR link looks invalid: {qr_link}")
                            
                    except Exception as bot_error:
                        logger.error(f"❌ Error sending legacy QR link to bot: {bot_error}")
                        
                return {
                    'status': 'success',
                    'qr_link': qr_link,
                    'method': 'legacy_playwright_full_page',
                    'message': 'QR код найден legacy методом и отправлен в бот'
                }
            else:
                logger.error("❌ No QR code found using legacy Playwright method")
                return {
                    'status': 'no_qr_found',
                    'message': 'QR код не найден legacy Playwright методом'
                }
                
        except Exception as e:
            logger.error(f"❌ Error in legacy Playwright QR extraction: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def _decode_qr_from_image(self, image_path: str, source_name: str) -> Optional[str]:
        """Декодирование QR кода из изображения с несколькими методами"""
        try:
            logger.info(f"🔍 Decoding QR from {source_name}: {image_path}")
            
            # Метод 1: pyzbar
            try:
                from pyzbar import pyzbar
                from PIL import Image
                
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
            
            # Метод 2: QReader
            try:
                from qreader import QReader
                import numpy as np
                from PIL import Image
                
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
                logger.warning("⚠️ QReader not available")
            except Exception as e:
                logger.warning(f"⚠️ QReader failed on {source_name}: {e}")
            
            # Метод 3: cv2 (OpenCV) - если доступен
            try:
                import cv2
                
                # Загружаем изображение
                img = cv2.imread(image_path)
                
                # Преобразуем в оттенки серого для лучшего распознавания
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                
                # Инициализируем детектор QR кодов
                detector = cv2.QRCodeDetector()
                
                # Пытаемся найти и декодировать QR код
                data, vertices_array, _ = detector.detectAndDecode(gray)
                
                if data:
                    logger.info(f"✅ OpenCV found QR: {data[:50]}...")
                    return data
                else:
                    logger.debug(f"⚠️ OpenCV: no QR codes found in {source_name}")
                    
            except ImportError:
                logger.debug("⚠️ OpenCV not available")
            except Exception as e:
                logger.warning(f"⚠️ OpenCV failed on {source_name}: {e}")
            
            logger.warning(f"❌ All QR decoding methods failed for {source_name}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error in QR decoding for {source_name}: {e}")
            return None
    
    async def _verify_redirect(self, session: RPASession, step: Dict[str, Any], credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Проверка успешного редиректа на целевой URL"""
        try:
            expected_url = step.get('expected_url')
            timeout = step.get('timeout', 10000)
            
            if not expected_url:
                raise ValueError("expected_url not specified in verify_redirect step")
            
            logger.info(f"🔍 Verifying redirect to URL containing: {expected_url}")
            
            # Проверяем текущий URL
            current_url = session.page.url
            logger.info(f"🔗 Current URL: {current_url}")
            
            # Проверяем содержит ли URL ожидаемый фрагмент
            # Проверяем исключения сначала
            exclude_patterns = step.get('exclude_patterns', [])
            excluded = False
            
            for exclude_pattern in exclude_patterns:
                if exclude_pattern in current_url:
                    logger.warning(f"⚠️ URL matches exclusion pattern '{exclude_pattern}': {current_url}")
                    excluded = True
                    break
            
            if excluded:
                logger.warning(f"⚠️ Redirect verification failed due to exclusion. Current URL: {current_url}")
                return {
                    'status': 'redirect_failed',
                    'current_url': current_url,
                    'expected_url': expected_url,
                    'verified': False,
                    'exclusion_reason': True,
                    'message': 'URL содержит исключенный паттерн (auth страница)'
                }
            elif step.get('exact_match') and current_url.startswith(expected_url):
                logger.info(f"✅ Redirect verification successful! URL starts with: {expected_url}")
                
                # Дополнительно ждем полной загрузки страницы
                try:
                    await session.page.wait_for_load_state('networkidle', timeout=5000)
                    logger.info("🌐 Page fully loaded")
                except Exception as e:
                    logger.warning(f"⚠️ Page load wait failed: {e}")
                    # Не критично
                
                return {
                    'status': 'success',
                    'current_url': current_url,
                    'verified': True,
                    'message': f'Успешный редирект на {expected_url} (exact match)'
                }
            elif not step.get('exact_match') and expected_url in current_url:
                logger.info(f"✅ Redirect verification successful! URL contains: {expected_url}")
                
                # Дополнительно ждем полной загрузки страницы
                try:
                    await session.page.wait_for_load_state('networkidle', timeout=5000)
                    logger.info("🌐 Page fully loaded")
                except Exception as e:
                    logger.warning(f"⚠️ Page load wait failed: {e}")
                    # Не критично
                
                return {
                    'status': 'success',
                    'current_url': current_url,
                    'verified': True,
                    'message': f'Успешный редирект на {expected_url} (contains match)'
                }
            else:
                logger.warning(f"⚠️ Redirect verification failed. Expected: {expected_url}, Got: {current_url}")
                return {
                    'status': 'redirect_failed',
                    'current_url': current_url,
                    'expected_url': expected_url,
                    'verified': False,
                    'message': f'Редирект не произошел на {expected_url}'
                }
                
        except Exception as e:
            logger.error(f"❌ Error in redirect verification: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def _cleanup_session(self, session: RPASession, step: Dict[str, Any], credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Очистка RPA сессии - ПРИНУДИТЕЛЬНОЕ закрытие браузера ТОЛЬКО после завершения всех операций"""
        try:
            logger.info(f"🧹 STARTING CLEANUP of RPA session {session.id}...")
            
            # Проверяем что куки были сохранены (если это требуется)
            depends_on = step.get('depends_on')
            if depends_on and depends_on in session.step_results:
                dependency_result = session.step_results[depends_on]
                logger.info(f"🔍 Dependency check: {depends_on} status = {dependency_result.get('status')}")
                
                if dependency_result.get('status') != 'success':
                    logger.warning(f"⚠️ Dependency {depends_on} did not complete successfully, but proceeding with cleanup")
            
            logger.info(f"🧹 FORCE-CLEANING RPA session {session.id}...")
            
            cleanup_actions = [
                "📸 Taking final screenshot",
                "🚪 FORCE-CLOSING browser context", 
                "🚪 FORCE-CLOSING browser",
                "💾 Freeing resources"
            ]
            
            for action in cleanup_actions:
                logger.info(action)
            
            # 1. Делаем итоговый скриншот (опционально)
            try:
                if step.get('final_screenshot', False):
                    screenshot_path = f"/tmp/final_session_{session.id}.png"
                    if session.page:
                        await session.page.screenshot(path=screenshot_path, full_page=True)
                        logger.info(f"📸 Final screenshot saved: {screenshot_path}")
            except Exception as e:
                logger.debug(f"Final screenshot failed: {e}")
            
            # 2. ПРИНУДИТЕЛЬНО закрываем браузер и освобождаем ресурсы
            cleanup_success = False
            
            # Закрываем context
            if session.context:
                try:
                    await session.context.close()
                    logger.info("🚪 Browser context FORCE-CLOSED")
                    cleanup_success = True
                except Exception as e:
                    logger.warning(f"⚠️ Context close failed: {e}")
                    try:
                        # Пытаемся принудительно закрыть через низкоуровневый API
                        await asyncio.wait_for(session.context.close(), timeout=5.0)
                        logger.info("🚪 Browser context FORCE-CLOSED (retry)")
                        cleanup_success = True
                    except Exception as e2:
                        logger.error(f"❌ Context force-close retry failed: {e2}")
                        
            # Закрываем browser
            if session.browser:
                try:
                    await session.browser.close()
                    logger.info("🚪 Browser FORCE-CLOSED")
                    cleanup_success = True
                except Exception as e:
                    logger.warning(f"⚠️ Browser close failed: {e}")
                    try:
                        # Пытаемся принудительно закрыть через низкоуровневый API
                        await asyncio.wait_for(session.browser.close(), timeout=5.0)
                        logger.info("🚪 Browser FORCE-CLOSED (retry)")
                        cleanup_success = True
                    except Exception as e2:
                        logger.error(f"❌ Browser force-close retry failed: {e2}")
            
            # 3. Обнуляем ссылки для принудительного освобождения памяти
            session.page = None
            session.context = None
            session.browser = None
            
            # 4. Обновляем статус сессии
            session.status = 'cleaned_up'
            
            if cleanup_success:
                logger.info(f"✅ RPA session {session.id} FORCE-CLEANED successfully")
                return {
                    'status': 'success',
                    'message': 'RPA сессия принудительно завершена и очищена',
                    'session_id': session.id,
                    'cleanup_time': datetime.now().isoformat(),
                    'force_cleanup': True
                }
            else:
                logger.warning(f"⚠️ RPA session {session.id} cleanup had issues but continued")
                return {
                    'status': 'partial_success',
                    'message': 'RPA сессия частично очищена',
                    'session_id': session.id,
                    'cleanup_time': datetime.now().isoformat(),
                    'force_cleanup': True
                }
            
        except Exception as e:
            logger.error(f"❌ Error in FORCE session cleanup: {e}")
            
            # Даже при ошибках пытаемся обнулить ссылки
            try:
                session.page = None
                session.context = None
                session.browser = None
                session.status = 'cleanup_error'
            except:
                pass
                
            return {'status': 'error', 'message': str(e), 'force_cleanup': True}
        
    async def _wait_and_click_element(self, session: RPASession, step: Dict[str, Any]) -> Dict[str, Any]:
        """Быстрое ожидание и клик по элементу"""
        timeout = step.get('timeout', 3000)  # Сократили с 10000 до 3000
        selector = step.get('selector')
        optional = step.get('optional', False)
        
        logger.info(f"⚡ Fast wait & click: {selector}")
        
        try:
            # Быстрое ожидание элемента
            element = None
            for attempt in range(int(timeout / 200)):  # Проверяем каждые 200ms вместо 500ms
                element = await self.find_element(session.page, step)
                if element:
                    break
                await asyncio.sleep(0.2)
            
            if not element:
                if optional:
                    logger.info(f"⏭️ Optional element not found: {selector}")
                    return {'status': 'skipped', 'reason': 'Element not found'}
                else:
                    raise Exception(f"Element not found after {timeout}ms: {selector}")
            
            await element.click()
            
            # Быстрое ожидание следующих элементов
            if 'wait_for' in step:
                await self._wait_for_condition(session, step['wait_for'], min(step.get('timeout', 2000), 2000))
                
            # Минимальная задержка
            if step.get('wait_after'):
                await asyncio.sleep(min(step['wait_after'] / 1000, 0.5))
                
            return {'status': 'success'}
            
        except Exception as e:
            if optional:
                logger.warning(f"⚠️ Optional wait_and_click failed: {e}")
                return {'status': 'skipped', 'reason': str(e)}
            else:
                raise e
        
    async def _save_cookies(self, session: RPASession, step: Dict[str, Any], credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Сохранение куки в базу данных с автоматическим cleanup браузера"""
        try:
            # Получаем все куки из браузера
            cookies = await session.page.context.cookies()
            
            if not cookies:
                logger.warning(f"⚠️ No cookies found for session {session.id}")
                return {'status': 'no_cookies', 'message': 'No cookies to save'}
            
            # Преобразуем куки в формат для сохранения
            cookies_data = []
            for cookie in cookies:
                cookies_data.append({
                    'name': cookie.get('name'),
                    'value': cookie.get('value'),
                    'domain': cookie.get('domain'),
                    'path': cookie.get('path', '/'),
                    'expires': cookie.get('expires'),
                    'httpOnly': cookie.get('httpOnly', False),
                    'secure': cookie.get('secure', False),
                    'sameSite': cookie.get('sameSite', 'Lax')
                })
            
            logger.info(f"🍪 Collected {len(cookies_data)} cookies for saving")
            
            # Получаем telegram_id и lsd_name из credentials/step
            telegram_id = credentials.get('telegram_id') or step.get('telegram_id')
            lsd_name = credentials.get('lsd_name') or step.get('lsd_name') 
            
            if not telegram_id or not lsd_name:
                logger.error(f"❌ Missing telegram_id or lsd_name for cookie saving")
                return {'status': 'error', 'message': 'Missing user identification'}
            
            # Сохраняем куки в базу
            success = await self._store_cookies_in_database(
                telegram_id=telegram_id,
                lsd_name=lsd_name, 
                cookies_data=cookies_data
            )
            
            if success:
                logger.info(f"✅ Successfully saved {len(cookies_data)} cookies for user {telegram_id} on {lsd_name}")
                
                # 🚨 НОВОЕ: АВТОМАТИЧЕСКИЙ CLEANUP БРАУЗЕРА СРАЗУ ПОСЛЕ СОХРАНЕНИЯ КУКОВ!
                logger.info("🧹 AUTO-CLEANUP: Starting browser cleanup immediately after cookie save...")
                cleanup_result = await self._force_cleanup_browser(session)
                
                if cleanup_result.get('success'):
                    logger.info("✅ Browser automatically cleaned up after cookie save!")
                else:
                    logger.warning(f"⚠️ Browser cleanup had issues: {cleanup_result.get('message')}")
                
                return {
                    'status': 'success', 
                    'cookies_count': len(cookies_data),
                    'message': f'Saved {len(cookies_data)} cookies and cleaned up browser',
                    'browser_cleaned': cleanup_result.get('success', False)
                }
            else:
                logger.error(f"❌ Failed to save cookies to database")
                return {'status': 'error', 'message': 'Database save failed'}
                
        except Exception as e:
            logger.error(f"❌ Error saving cookies: {e}")
            return {'status': 'error', 'message': str(e)}
            
    async def _force_cleanup_browser(self, session: RPASession) -> Dict[str, Any]:
        """Принудительная очистка браузера (внутренняя функция для save_cookies)"""
        try:
            logger.info(f"🧹 FORCE-CLEANING browser for session {session.id}...")
            
            cleanup_success = False
            
            # Закрываем context
            if session.context:
                try:
                    await session.context.close()
                    logger.info("🚪 Browser context FORCE-CLOSED")
                    cleanup_success = True
                except Exception as e:
                    logger.warning(f"⚠️ Context close failed: {e}")
                    try:
                        await asyncio.wait_for(session.context.close(), timeout=5.0)
                        logger.info("🚪 Browser context FORCE-CLOSED (retry)")
                        cleanup_success = True
                    except Exception as e2:
                        logger.error(f"❌ Context force-close retry failed: {e2}")
                        
            # Закрываем browser
            if session.browser:
                try:
                    await session.browser.close()
                    logger.info("🚪 Browser FORCE-CLOSED")
                    cleanup_success = True
                except Exception as e:
                    logger.warning(f"⚠️ Browser close failed: {e}")
                    try:
                        await asyncio.wait_for(session.browser.close(), timeout=5.0)
                        logger.info("🚪 Browser FORCE-CLOSED (retry)")
                        cleanup_success = True
                    except Exception as e2:
                        logger.error(f"❌ Browser force-close retry failed: {e2}")
            
            # Обнуляем ссылки
            session.page = None
            session.context = None
            session.browser = None
            
            if cleanup_success:
                logger.info(f"✅ Browser FORCE-CLEANED successfully for session {session.id}")
                return {'success': True, 'message': 'Browser cleaned successfully'}
            else:
                logger.warning(f"⚠️ Browser cleanup had issues for session {session.id}")
                return {'success': False, 'message': 'Browser cleanup had issues'}
                
        except Exception as e:
            logger.error(f"❌ Error in force browser cleanup: {e}")
            return {'success': False, 'message': str(e)}
    
    async def _store_cookies_in_database(self, telegram_id: int, lsd_name: str, cookies_data: list) -> bool:
        """Сохранение куки в базу данных + JSON файл + синхронизация в персистентный профиль"""
        try:
            # Для сохранения куки нужно импортировать базу
            from shared.database import get_async_session
            from shared.database.models import UserSession, LSDConfig
            from sqlalchemy import select, delete
            from datetime import datetime, timedelta
            import json
            from pathlib import Path
            import subprocess

            async for db in get_async_session():
                # 1. Находим LSD config
                lsd_result = await db.execute(select(LSDConfig).where(LSDConfig.name == lsd_name))
                lsd_config = lsd_result.scalar_one_or_none()

                if not lsd_config:
                    logger.error(f"❌ LSD config not found for {lsd_name}")
                    return False

                # 2. Удаляем старые куки пользователя для этого LSD
                await db.execute(
                    delete(UserSession).where(
                        UserSession.telegram_id == telegram_id,
                        UserSession.lsd_config_id == lsd_config.id
                    )
                )

                # 3. Сохраняем новые куки в database
                expires_at = datetime.now() + timedelta(days=30)  # Куки действуют 30 дней

                user_session = UserSession(
                    telegram_id=telegram_id,
                    lsd_config_id=lsd_config.id,  # Прямая ссылка на LSD конфиг
                    session_type=lsd_config.name,  # Записываем наименование ЛСД в session_type
                    data={'cookies': cookies_data},
                    expires_at=expires_at
                )
                db.add(user_session)

                await db.commit()
                logger.info(f"✅ Cookies saved to database for user {telegram_id} on {lsd_name} (config_id: {lsd_config.id})")

                # 4. Сохраняем куки в JSON файл (для бэкапа и синхронизации в профиль)
                try:
                    # Определяем путь к проекту (идем вверх от shared/rpa/)
                    current_file = Path(__file__)
                    project_root = current_file.parent.parent.parent  # shared/rpa/ -> shared/ -> project_root/

                    cookies_dir = project_root / "cookies" / lsd_name
                    cookies_dir.mkdir(parents=True, exist_ok=True)

                    cookie_file_path = cookies_dir / f"{telegram_id}_{lsd_name}.json"

                    # Формируем полный JSON с метаданными
                    cookie_json = {
                        "telegram_id": telegram_id,
                        "lsd_config_id": lsd_config.id,
                        "lsd_name": lsd_name,
                        "cookies": cookies_data,
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                        "session_metadata": {
                            "auth_completed": True,
                            "auth_timestamp": datetime.now().isoformat()
                        }
                    }

                    with open(cookie_file_path, 'w', encoding='utf-8') as f:
                        json.dump(cookie_json, f, ensure_ascii=False, indent=2)

                    logger.info(f"📄 Cookies saved to JSON file: {cookie_file_path}")

                    # 5. Синхронизируем куки в персистентный профиль Chrome (SQLite)
                    try:
                        sync_script_path = project_root / "services" / "rpa-service" / "sync_cookies_to_profile.py"

                        if sync_script_path.exists():
                            logger.info(f"🔄 Syncing cookies to Chrome persistent profile...")

                            # Запускаем скрипт синхронизации
                            result = subprocess.run(
                                ['python3', str(sync_script_path), str(telegram_id), lsd_name],
                                capture_output=True,
                                text=True,
                                timeout=30
                            )

                            if result.returncode == 0:
                                logger.info(f"✅ Cookies synced to Chrome profile successfully!")
                                logger.debug(f"Sync output: {result.stdout}")
                            else:
                                logger.warning(f"⚠️ Cookie sync script failed: {result.stderr}")
                        else:
                            logger.warning(f"⚠️ Sync script not found at {sync_script_path}")

                    except subprocess.TimeoutExpired:
                        logger.warning(f"⚠️ Cookie sync script timed out after 30s")
                    except Exception as sync_error:
                        logger.warning(f"⚠️ Failed to sync cookies to Chrome profile: {sync_error}")

                except Exception as file_error:
                    logger.warning(f"⚠️ Failed to save cookies to JSON file: {file_error}")
                    # Не падаем - куки уже сохранены в database

                return True

        except Exception as e:
            logger.error(f"❌ Database error saving cookies: {e}")
            return False
        
    async def _clear_element(self, session: RPASession, step: Dict[str, Any]) -> Dict[str, Any]:
        """Простая очистка поля ввода"""
        element = await self.find_element(session.page, step)
        if not element:
            if step.get('optional', False):
                return {'status': 'skipped', 'reason': 'Element not found'}
            raise Exception(f"Input element not found for clear step {step.get('id')}")
            
        # Очищаем поле - правильный способ в Playwright
        await element.fill('')
        
        # Ожидание после очистки
        if step.get('wait_after'):
            await asyncio.sleep(step['wait_after'] / 1000)
            
        return {'status': 'success'}
        
    async def _clear_and_wait(self, session: RPASession, step: Dict[str, Any]) -> Dict[str, Any]:
        """Очистка поля ввода с ожиданием"""
        element = await self.find_element(session.page, step)
        if not element:
            if step.get('optional', False):
                return {'status': 'skipped', 'reason': 'Element not found'}
            raise Exception(f"Input element not found for clear step {step.get('id')}")
            
        # Очищаем поле - правильный способ в Playwright
        await element.fill('')
        
        # Ожидание после очистки
        if step.get('wait_after'):
            await asyncio.sleep(step['wait_after'] / 1000)
            
        return {'status': 'success'}
        
    async def _type_multi_field(self, session: RPASession, step: Dict[str, Any], credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Ввод в несколько полей (например, SMS код в отдельные поля)"""
        try:
            # Получаем значение для ввода
            value = self._resolve_value(step.get('value', '{sms_code}'), credentials)
            step_id = step.get('id', 'unknown_step')
            
            logger.info(f"📝 Multi-field typing '{value}' for step '{step_id}'")
            
            # Находим все поля ввода
            elements = []
            selectors = step.get('selectors', [step.get('selector')])
            
            for selector in selectors:
                if not selector:
                    continue
                    
                try:
                    if selector.startswith('//'):
                        element_list = await session.page.query_selector_all(f'xpath={selector}')
                    else:
                        element_list = await session.page.query_selector_all(selector)
                    
                    # Фильтруем только видимые элементы
                    visible_elements = []
                    for el in element_list:
                        if await el.is_visible():
                            visible_elements.append(el)
                    
                    if visible_elements:
                        elements = visible_elements
                        logger.info(f"✅ Found {len(elements)} visible elements with selector: {selector}")
                        break
                        
                except Exception as e:
                    logger.debug(f"Selector failed: {selector}, error: {e}")
                    continue
            
            if not elements:
                raise Exception(f"No input fields found for multi-field typing in step {step_id}")
            
            # Разбиваем значение по символам
            chars = list(value.strip())
            
            logger.info(f"📊 Multi-field state: {len(elements)} fields, {len(chars)} characters")
            
            if len(chars) > len(elements):
                logger.warning(f"⚠️ More characters ({len(chars)}) than fields ({len(elements)}), will truncate")
                chars = chars[:len(elements)]
            elif len(chars) < len(elements):
                logger.warning(f"⚠️ Fewer characters ({len(chars)}) than fields ({len(elements)})")
            
            # Вводим по одному символу в каждое поле
            for i, (element, char) in enumerate(zip(elements, chars)):
                try:
                    logger.info(f"  📝 Field {i+1}: typing '{char}'")
                    
                    # Фокусируемся на поле
                    await element.focus()
                    await asyncio.sleep(0.1)
                    
                    # Очищаем и вводим символ
                    await element.fill('')
                    await element.type(char)  # Используем type для эмуляции реального ввода
                    
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"❌ Failed to type into field {i+1}: {e}")
                    # Продолжаем с остальными полями
                    continue
            
            # Ожидание после ввода
            if step.get('wait_after'):
                await asyncio.sleep(step['wait_after'] / 1000)
            
            logger.info(f"✅ Multi-field typing completed for {len(chars)} characters")
            
            return {
                'status': 'success', 
                'fields_filled': len(chars),
                'total_fields': len(elements)
            }
            
        except Exception as e:
            logger.error(f"❌ Error in multi-field typing: {e}")
            return {'status': 'error', 'message': str(e)}

    async def _type_text(self, session: RPASession, step: Dict[str, Any], credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Ввод текста с подстановкой значений"""
        element = await self.find_element(session.page, step)
        if not element:
            raise Exception(f"Input element not found for step {step.get('id')}")
            
        # Подставляем значения из credentials
        value = self._resolve_value(step['value'], credentials)
        step_id = step.get('id', 'unknown_step')
        
        logger.info(f"📝 Typing '{value}' into field for step '{step_id}'")
        
        # Проверяем, это SMS поле, телефон или обычное поле
        is_sms_field = step_id == 'enter_sms' or 'sms' in step_id.lower()
        is_phone_field = step_id == 'enter_phone' or 'phone' in step_id.lower()
        is_vkusvill = 'vkusvill' in str(session.config.get('base_url', '')).lower()
        is_pyaterochka = '5ka.ru' in str(session.config.get('base_url', '')).lower() or 'pyaterochka' in str(session.config.get('base_url', '')).lower()
        
        final_value = value  # По умолчанию равно введенному значению
        
        # Для ВкусВилл И Пятёрочки используем посимвольный ввод для SMS и телефона
        if (is_sms_field or (is_phone_field and (is_vkusvill or is_pyaterochka))):
            field_type = "SMS" if is_sms_field else "phone"
            lsd_name = "VkusVill" if is_vkusvill else "Pyaterochka" if is_pyaterochka else "Unknown"
            logger.info(f"📱 {field_type} field detected for {lsd_name} - using character-by-character input")
            
            # Для поля телефона убираем префикс "+7" если он есть
            if is_phone_field and (is_vkusvill or is_pyaterochka):
                if value.startswith("+7"):
                    value = value[2:]  # Убираем "+7"
                    logger.info(f"📞 {lsd_name} phone field: removed '+7' prefix, using: '{value}'")
                elif value.startswith("7"):
                    value = value[1:]  # Убираем "7"
                    logger.info(f"📞 {lsd_name} phone field: removed '7' prefix, using: '{value}'")
            
            # Дополнительная проверка готовности поля
            await asyncio.sleep(0.3)  # Короткое ожидание готовности поля
            
            # Проверяем состояние поля до ввода
            is_enabled = await element.is_enabled()
            is_visible = await element.is_visible()
            current_value = await element.input_value()
            
            logger.info(f"📊 {field_type} field state: enabled={is_enabled}, visible={is_visible}, current_value='{current_value}'")
            
            if not is_enabled:
                raise Exception(f"{field_type} input field is not enabled")
            if not is_visible:
                raise Exception(f"{field_type} input field is not visible")
            
            # Фокусируемся на поле
            await element.focus()
            await asyncio.sleep(0.1)
            
            # Очищаем поле и вводим значение
            await element.fill('')  # Сначала очищаем
            await asyncio.sleep(0.1)
            
            # Вместо fill() используем type() для эмуляции реального ввода
            await element.type(value)  # Эмулирует реальный ввод с клавиатуры
            
            # Проверяем, произошла ли навигация (что означает успешный ввод)
            try:
                # Небольшая задержка для возможной навигации
                await asyncio.sleep(0.5)
                
                # Пытаемся получить текущий URL - если навигация произошла, элемент может исчезнуть
                current_url = session.page.url
                
                # Проверяем финальное значение только если элемент еще существует
                try:
                    final_value = await element.input_value()
                    logger.info(f"✅ {field_type} field final value: '{final_value}'")
                    
                    if final_value != value:
                        logger.warning(f"⚠️ {field_type} value mismatch! Expected '{value}', got '{final_value}'")
                        
                except Exception as e:
                    # Элемент исчез - скорее всего навигация произошла (что хорошо!)
                    logger.info(f"🔄 Element disappeared after {field_type} input - likely navigation occurred (success!)")
                    final_value = value  # Считаем что ввод прошел успешно
                    
            except Exception as e:
                logger.info(f"🔄 Navigation detected after {field_type} input: {e}")
                final_value = value
            
        else:
            # Обычный ввод для не-SMS/не-телефон полей
            await element.fill(value)
        
        if step.get('wait_after'):
            await asyncio.sleep(step['wait_after'] / 1000)
            
        return {'status': 'success', 'value': value, 'final_field_value': final_value if is_sms_field else value}
        
    async def _uncheck_element(self, session: RPASession, step: Dict[str, Any]) -> Dict[str, Any]:
        """Снятие галочки с чекбокса"""
        element = await self.find_element(session.page, step)
        if not element:
            if step.get('optional', False):
                return {'status': 'skipped', 'reason': 'Element not found'}
            raise Exception(f"Checkbox not found for step {step.get('id')}")
            
        is_checked = await element.is_checked()
        if is_checked:
            await element.uncheck()
            return {'status': 'success', 'action': 'unchecked'}
        else:
            return {'status': 'success', 'action': 'already_unchecked'}
            
    async def _wait_for_element(self, session: RPASession, step: Dict[str, Any]) -> Dict[str, Any]:
        """Ожидание появления элемента"""
        timeout = step.get('timeout', 10000)
        
        await self._wait_for_condition(session, step, timeout)
        return {'status': 'success'}
        
    async def _wait_for_navigation(self, session: RPASession, step: Dict[str, Any]) -> Dict[str, Any]:
        """Быстрое ожидание навигации с оптимизированными интервалами"""
        url_contains = step.get('url_contains')
        timeout = step.get('timeout', 30000)
        check_interval = step.get('check_interval', 1)  # Сократили с 2 до 1 секунды
        
        logger.info(f"⚡ Fast navigation wait: {url_contains} (timeout: {timeout/1000}s)")
        
        start_time = datetime.now()
        last_log_time = start_time
        
        while (datetime.now() - start_time).total_seconds() * 1000 < timeout:
            current_url = session.page.url
            
            # Быстрая проверка исключений
            exclude_urls = step.get('exclude_urls', [])
            excluded = any(exclude_pattern in current_url for exclude_pattern in exclude_urls)
            
            if not excluded and url_contains in current_url:
                logger.info(f"✅ Navigation detected: {current_url}")
                # Быстрая проверка что это не auth страница
                if 'passport.yandex.ru' not in current_url and '/auth' not in current_url:
                    return {'status': 'success', 'url': current_url}
            
            # Логируем прогресс каждые 15 секунд вместо 30
            if (datetime.now() - last_log_time).total_seconds() >= 15:
                elapsed_minutes = (datetime.now() - start_time).total_seconds() / 60
                logger.info(f"⏳ Waiting... {elapsed_minutes:.1f}min elapsed")
                last_log_time = datetime.now()
            
            await asyncio.sleep(check_interval)
        
        logger.error(f"❌ Navigation timeout after {timeout/1000}s")
        
        # QR авторизация - таймаут не критичен
        if step.get('id') == 'wait_for_auth_success':
            return {
                'status': 'timeout',
                'url': session.page.url,
                'message': 'Пользователь не завершил авторизацию вовремя'
            }
        
        raise Exception(f"Navigation timeout after {timeout}ms. Current URL: {session.page.url}")
        
    async def _scroll_into_view(self, session: RPASession, step: Dict[str, Any]) -> Dict[str, Any]:
        """Прокрутка к элементу"""
        element = await self.find_element(session.page, step)
        if not element:
            if step.get('optional', False):
                return {'status': 'skipped', 'reason': 'Element not found'}
            raise Exception(f"Element not found for scroll step {step.get('id')}")
            
        # Прокручиваем к элементу
        await element.scroll_into_view_if_needed()
        
        # Небольшая задержка после прокрутки
        await asyncio.sleep(0.5)
        
        return {'status': 'success'}
        
    async def _request_sms_code(self, session: RPASession, step: Dict[str, Any]) -> Dict[str, Any]:
        """Запрос SMS кода с уведомлением бота"""
        
        # Проверяем, требуется ли пользовательский ввод
        if step.get('requires_user_input'):
            logger.info("🔔 SMS code requires user input - pausing session for user interaction")
            
            session.status = 'waiting_for_user_input'
            session.context_data['sms_requested_at'] = datetime.now()
            session.context_data['input_type'] = step.get('input_type', 'sms_code')
            session.context_data['prompt'] = step.get('prompt', 'Введите SMS код')
            session.context_data['waiting_step'] = step['id']
            
            # 📢 ОТПРАВЛЯЕМ УВЕДОМЛЕНИЕ БОТУ!
            await self._notify_telegram_bot_for_sms(
                session=session,
                step=step,
                message=step.get('prompt', 'Введите SMS код')
            )
            
            return {
                'status': 'waiting_for_user_input',
                'message': step.get('prompt', 'Введите SMS код'),
                'input_type': step.get('input_type', 'sms_code'),
                'session_id': session.id
            }
        else:
            # Старая логика для обычного SMS handler
            logger.info("🔔 SMS code required - session waiting for user input")
            
            session.status = 'waiting_for_sms'
            session.context_data['sms_requested_at'] = datetime.now()
            
            return {'status': 'sms_requested', 'message': 'SMS код запрошен'}
    
    async def _notify_telegram_bot_for_sms(self, session: RPASession, step: Dict[str, Any], message: str):
        """Уведомление Telegram бота о необходимости SMS кода - ИСПРАВЛЕНО без циклического импорта"""
        try:
            import httpx
            
            # ИСПРАВЛЕННАЯ ЛОГИКА: Получаем telegram_id из контекста сессии
            telegram_id = session.context_data.get('telegram_id')
            
            if not telegram_id:
                logger.error("❌ CRITICAL: No telegram_id found in session context for SMS notification!")
                logger.error(f"❌ Session context_data: {session.context_data}")
                
                # ПОПЫТКА ДОПОЛНИТЕЛЬНОГО ПОИСКА БЕЗ ЦИКЛИЧЕСКОГО ИМПОРТА
                # Проверяем, есть ли telegram_id в других местах контекста
                alternative_locations = [
                    session.context_data.get('credentials', {}).get('telegram_id'),
                    getattr(session, 'telegram_id', None),
                    session.context_data.get('user_data', {}).get('telegram_id'),
                ]
                
                for alt_telegram_id in alternative_locations:
                    if alt_telegram_id:
                        telegram_id = alt_telegram_id
                        logger.info(f"🔧 RECOVERED: Found telegram_id={telegram_id} in alternative location")
                        # Сохраняем в основном контексте для будущих использований
                        session.context_data['telegram_id'] = telegram_id
                        break
                
                if not telegram_id:
                    logger.error("❌ CRITICAL: telegram_id not found in any location!")
                    logger.error("❌ Cannot send SMS request without telegram_id")
                    return
            
            logger.info(f"🤖 Sending SMS request to bot for user {telegram_id}")
            
            bot_request = {
                "telegram_id": telegram_id,
                "message": message,
                "session_id": session.id,
                "input_type": step.get('input_type', 'sms_code'),
                "action": "request_sms_code"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8001/rpa/user-input-request",
                    json=bot_request,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    logger.info("📱 Successfully sent SMS request to bot")
                else:
                    logger.error(f"❌ Bot SMS request failed: {response.status_code}")
                    
        except Exception as bot_error:
            logger.error(f"❌ Error notifying bot about SMS: {bot_error}")
    
    async def _notify_telegram_bot_success(self, session: RPASession, telegram_id: int, lsd_name: str, cookies_count: int):
        """Уведомление Telegram бота об успешной авторизации"""
        try:
            import httpx
            
            # Получаем display_name из контекста сессии
            display_name = session.context_data.get('display_name', lsd_name.title())
            
            logger.info(f"🎉 Sending success notification to bot for user {telegram_id}")
            
            bot_request = {
                "telegram_id": telegram_id,
                "message": f"✅ Авторизация в {display_name} завершена успешно! 🍪 Куки сохранены ({cookies_count} шт.)",
                "action": "auth_success",
                "result": {
                    "status": "completed",
                    "lsd_name": lsd_name,
                    "display_name": display_name,
                    "success": True,
                    "cookies_count": cookies_count
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8001/rpa/auth-success",
                    json=bot_request,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    logger.info("🎉 Successfully sent success notification to bot")
                else:
                    logger.error(f"❌ Bot success notification failed: {response.status_code}")
                    
        except Exception as bot_error:
            logger.error(f"❌ Error sending success notification: {bot_error}")
        
    async def _find_element_with_selectors(self, session: RPASession, step: Dict[str, Any], timeout: int) -> Optional[Any]:
        """Поиск элемента с несколькими селекторами и timeout'ом"""
        selectors = step.get('selectors', [step.get('selector')])
        step_id = step.get('id', 'unknown_step')
        
        logger.info(f"🔍 Searching element for step '{step_id}' with {len(selectors)} selectors")
        
        for i, selector in enumerate(selectors):
            if not selector:
                continue
                
            try:
                logger.info(f"  🎯 Trying selector {i+1}/{len(selectors)}: {selector}")
                element = await self._try_find_element(session.page, selector)
                if element:
                    logger.info(f"  ✅ SUCCESS! Found element with selector: {selector}")
                    return element
                else:
                    logger.info(f"  ❌ Element not found or not visible: {selector}")
            except Exception as e:
                logger.info(f"  💥 Selector failed: {selector}, error: {e}")
                continue
                
        logger.error(f"🚫 No working selectors found for step '{step_id}'")
        return None
    
    async def find_element(self, page: Page, step: Dict[str, Any]) -> Optional[Any]:
        """Быстрый поиск элемента по множественным селекторам"""
        selectors = step.get('selectors', [step.get('selector')])
        step_id = step.get('id', 'unknown_step')
        
        logger.info(f"⚡ Fast element search for '{step_id}' ({len(selectors)} selectors)")
        
        for i, selector in enumerate(selectors):
            if not selector:
                continue
                
            try:
                element = await self._try_find_element(page, selector)
                if element:
                    logger.info(f"✅ Found with selector {i+1}: {selector}")
                    return element
            except Exception as e:
                logger.debug(f"Selector {i+1} failed: {e}")
                continue
                
        logger.error(f"🚫 No elements found for '{step_id}'")
        return None
        
    async def _try_find_element(self, page: Page, selector: str) -> Optional[Any]:
        """Быстрый поиск элемента с минимальным логированием"""
        
        # XPath селектор
        if selector.startswith('//'):
            try:
                element = await page.query_selector(f'xpath={selector}')
                if element and await element.is_visible():
                    return element
            except Exception:
                pass
                
        # CSS селектор
        else:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    return element
            except Exception:
                pass
                
        return None
    
    async def _add_human_behavior(self, session: RPASession, quick: bool = False):
        """Имитация человеческого поведения для обхода детекции ботов"""
        import random
        
        try:
            if quick:
                # Быстрое поведение - только короткая пауза
                await asyncio.sleep(random.uniform(0.1, 0.3))
                return
            
            # Полное человеческое поведение
            
            # 1. Случайная пауза (1-3 секунды)
            pause = random.uniform(1.0, 3.0)
            logger.debug(f"😴 Human behavior: pausing for {pause:.1f}s")
            await asyncio.sleep(pause)
            
            # 2. Случайное движение мыши
            viewport = session.page.viewport_size
            if viewport:
                x = random.randint(100, viewport['width'] - 100)
                y = random.randint(100, viewport['height'] - 100)
                logger.debug(f"🐭 Human behavior: moving mouse to ({x}, {y})")
                await session.page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.1, 0.3))
            
            # 3. Случайный скроллинг (25% вероятность)
            if random.random() < 0.25:
                scroll_amount = random.randint(100, 300)
                direction = random.choice([1, -1])  # вверх или вниз
                logger.debug(f"📜 Human behavior: scrolling {scroll_amount * direction}px")
                await session.page.evaluate(f"window.scrollBy(0, {scroll_amount * direction})")
                await asyncio.sleep(random.uniform(0.2, 0.5))
            
            # 4. Имитация чтения (пауза на странице)
            if random.random() < 0.3:
                read_pause = random.uniform(0.5, 2.0)
                logger.debug(f"📚 Human behavior: reading for {read_pause:.1f}s")
                await asyncio.sleep(read_pause)
                
        except Exception as e:
            logger.debug(f"Human behavior simulation failed: {e}")
            # Не критично - просто продолжаем
        
    async def _wait_for_condition(self, session: RPASession, condition: Union[Dict, str], timeout: int):
        """Ожидание условия с множественными селекторами"""
        if isinstance(condition, str):
            # Простой селектор
            selectors = [condition]
        else:
            # Объект с селекторами
            selectors = condition.get('selectors', [condition.get('selector')])
            
        for selector in selectors:
            if not selector:
                continue
                
            try:
                if selector.startswith('//'):
                    await session.page.wait_for_selector(f'xpath={selector}', timeout=timeout)
                else:
                    await session.page.wait_for_selector(selector, timeout=timeout)
                return True
            except:
                continue
                
        raise Exception("None of the wait conditions were met")
        
    def _resolve_value(self, template: str, credentials: Dict[str, Any]) -> str:
        """Подставляем значения из credentials"""
        if not isinstance(template, str):
            return str(template)
        
        # Обрабатываем специальные плейсхолдеры
        phone = credentials.get('phone', '')
        
        # Обработка {phone_no_prefix} - старый формат
        if '{phone_no_prefix}' in template:
            # Убираем префиксы +7 или 7
            if phone.startswith('+7'):
                phone_no_prefix = phone[2:]
            elif phone.startswith('7'):
                phone_no_prefix = phone[1:]
            else:
                phone_no_prefix = phone
            template = template.replace('{phone_no_prefix}', phone_no_prefix)
        
        # Обработка {phone_without_7} - НОВЫЙ формат для Самоката
        if '{phone_without_7}' in template:
            # Преобразуем '79262041000' в '9262041000' (БЕЗ ПРОБЕЛОВ)
            if phone.startswith('7') and len(phone) == 11:
                # Убираем первую 7, НО пока ОСТАВЛЯЕМ БЕЗ ПРОБЕЛОВ  
                phone_without_7 = phone[1:]  # Просто убираем 7: 79262041000 → 9262041000
            elif phone.startswith('+7') and len(phone) == 12:
                # Убираем +7
                phone_without_7 = phone[2:]  # Убираем +7: +79262041000 → 9262041000
            else:
                # Если формат не стандартный - используем как есть
                phone_without_7 = phone
            
            template = template.replace('{phone_without_7}', phone_without_7)
            logger.info(f"📞 Phone formatting: '{phone}' → '+7{phone_without_7}' (without spaces)")
        
        # Простая подстановка через .format()
        try:
            return template.format(**credentials)
        except KeyError as e:
            logger.warning(f"Missing credential key: {e}")
            return template
            
    async def continue_with_user_input(self, session_id: str, user_input: str) -> Dict[str, Any]:
        """Продолжение выполнения с пользовательским вводом"""
        session = self.active_sessions.get(session_id)
        if not session:
            return {'status': 'error', 'error': 'Session not found'}
            
        if session.status != 'waiting_for_user_input':
            return {'status': 'error', 'error': 'Session is not waiting for user input'}
            
        logger.info(f"📝 Continuing session {session_id} with user input: {user_input}")
        
        # Сохраняем пользовательский ввод
        session.context_data['user_input'] = user_input
        session.status = 'running'
        
        try:
            # 🔧 ИСПРАВЛЕНО: Продолжаем выполнение с места, где остановились
            paused_at_step_index = session.context_data.get('paused_at_step')
            steps = session.config.get('steps', [])
            
            if paused_at_step_index is not None:
                # Новая логика: продолжаем со следующего шага
                continue_from_index = paused_at_step_index + 1
                logger.info(f"📎 Resuming from step {continue_from_index} (paused at step {paused_at_step_index})")
            else:
                # Старая логика: поиск по waiting_step_id
                waiting_step_id = session.context_data.get('waiting_step')
                continue_from_index = 0
                for i, step in enumerate(steps):
                    if step.get('id') == waiting_step_id:
                        continue_from_index = i + 1
                        break
                logger.info(f"📎 Fallback: resuming from step {continue_from_index} (waiting_step: {waiting_step_id})")
            
            # Получаем исходные credentials из контекста сессии и дополняем их пользовательским вводом
            original_credentials = session.context_data.get('credentials', {})
            credentials = {
                'phone': session.context_data.get('phone', '+71234567890'),
                'telegram_id': session.context_data.get('telegram_id'),
                'lsd_name': session.context_data.get('lsd_name', 'vkusvill'),
                'sms_code': user_input,
                'user_input': user_input,
                **original_credentials  # Мерджим с исходными credentials
            }
            logger.info(f"📋 Resuming with credentials: {list(credentials.keys())}")            
            
            # Выполняем оставшиеся шаги с проверкой на waiting_for_user_input
            for i in range(continue_from_index, len(steps)):
                step = steps[i]
                step_id = step.get('id', f'step_{i}')
                
                logger.info(f"▶️ [{i+1}/{len(steps)}] Resuming step: {step_id}")
                
                try:
                    result = await self.execute_step(session, step, credentials)
                    logger.info(f"✅ Step {step_id} completed with status: {result.get('status')}")
                    
                    # 🚨 Проверка: если шаг снова требует пользовательского ввода
                    if result.get('status') == 'waiting_for_user_input':
                        logger.info(f"⏸️ PAUSED AGAIN: Step {step_id} requires additional user input")
                        session.context_data['paused_at_step'] = i
                        session.context_data['waiting_step'] = step_id
                        return {
                            'status': 'waiting_for_user_input',
                            'message': result.get('message', 'Требуется дополнительный ввод'),
                            'input_type': result.get('input_type', 'sms_code'),
                            'session_id': session.id
                        }
                    
                    # 🎯 ИСПРАВЛЕНО: Проверяем условие успеха - НО ВЫПОЛНЯЕМ ВСЕ ОСТАВШИЕСЯ ШАГИ!
                    if step.get('success') and result.get('status') == 'success':
                        logger.info(f"🎉 SUCCESS step {step_id} completed! Executing ALL remaining steps...")
                        
                        # 🚨 ИСПРАВЛЕНИЕ: Выполняем ВСЕ оставшиеся шаги после success (особенно save_cookies и cleanup)
                        remaining_steps = steps[i+1:]
                        remaining_steps_executed = 0
                        critical_steps_executed = 0
                        
                        for remaining_step in remaining_steps:
                            remaining_step_id = remaining_step.get('id', 'unknown')
                            remaining_step_type = remaining_step.get('type', 'unknown')
                            is_critical = remaining_step.get('critical', False)
                            
                            logger.info(f"▶️ Post-success step: {remaining_step_id} ({remaining_step_type}){'[CRITICAL]' if is_critical else ''}")
                            
                            try:
                                remaining_result = await self.execute_step(session, remaining_step, credentials)
                                remaining_steps_executed += 1
                                
                                if is_critical:
                                    critical_steps_executed += 1
                                    
                                logger.info(f"✅ Post-success step {remaining_step_id} result: {remaining_result.get('status')}")
                                
                            except Exception as remaining_error:
                                logger.error(f"❌ Post-success step {remaining_step_id} failed: {remaining_error}")
                                
                                # Критические шаги не должны останавливать выполнение
                                if not is_critical:
                                    logger.info(f"⚠️ Non-critical step failed, continuing...")
                                    continue
                        
                        logger.info(f"🔄 Executed {remaining_steps_executed} remaining steps after success ({critical_steps_executed} critical)")
                        
                        # Теперь завершаем
                        session.status = 'completed'
                        return {
                            'status': 'completed',
                            'success': True,
                            'message': 'Авторизация завершена успешно',
                            'remaining_steps_executed': remaining_steps_executed
                        }
                    
                except Exception as e:
                    logger.error(f"❌ Step {step_id} failed: {e}")
                    
                    # Если это шаг с SMS кодом, проверяем навигацию
                    if step_id in ['enter_sms', 'submit_sms'] and 'navigation' in str(e).lower():
                        logger.info("🔄 SMS step failed due to navigation - checking if we're on success page")
                        
                        # Проверяем текущий URL
                        current_url = session.page.url
                        base_url = session.config.get('base_url', '')
                        
                        # Если мы на главной странице сайта (не на странице авторизации), то успех!
                        if base_url and current_url.startswith(base_url) and '/login' not in current_url and '/auth' not in current_url:
                            logger.info("✅ Navigation to main site detected - authorization successful!")
                            logger.warning("⚠️ Navigation-based success detected - this should be handled by proper RPA steps")
                            
                            session.status = 'completed'
                            return {
                                'status': 'completed',
                                'success': True,
                                'message': 'Авторизация завершена успешно (обнаружена навигация)'
                            }
                    
                    # Если это шаг проверки успеха (verify_success), пробуем его выполнить отдельно
                    if step_id == 'verify_success':
                        try:
                            logger.info(f"🔄 Retrying critical step {step_id}")
                            result = await self.execute_step(session, step, credentials)
                            if step.get('success'):
                                logger.info(f"✅ Authentication verified successfully despite previous errors")
                                
                                session.status = 'completed'
                                return {
                                    'status': 'completed',
                                    'success': True,
                                    'message': 'Авторизация завершена успешно'
                                }
                        except Exception as retry_e:
                            logger.error(f"❌ Retry of {step_id} also failed: {retry_e}")
                    
                    # Для критических шагов (save_cookies, verify_success, SMS шаги) продолжаем выполнение
                    if step_id in ['save_cookies', 'verify_success', 'enter_sms', 'submit_sms']:
                        logger.warning(f"⚠️ Critical step {step_id} failed, but continuing execution")
                        continue
                    
                    # Для остальных шагов - останавливаемся на ошибках
                    session.status = 'error'
                    return {
                        'status': 'error',
                        'error': f'Step {step_id} failed: {str(e)}'
                    }
            
            # Если дошли до конца без явного успеха
            session.status = 'completed'
            return {
                'status': 'completed',
                'success': True,
                'message': 'Все шаги выполнены'
            }
            
        except Exception as e:
            logger.error(f"❌ Error continuing session with user input: {e}")
            session.status = 'error'
            return {
                'status': 'error',
                'error': str(e)
            }

    async def cleanup_session(self, session_id: str):
        """Очистка сессии"""
        session = self.active_sessions.get(session_id)
        if not session:
            return
            
        try:
            if session.context:
                await session.context.close()
            if session.browser:
                await session.browser.close()
                
            logger.info(f"Cleaned up RPA session {session_id}")
        except Exception as e:
            logger.error(f"Error cleaning up session {session_id}: {e}")
        finally:
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
                
    async def cleanup_all_sessions(self):
        """Очистка всех активных сессий"""
        session_ids = list(self.active_sessions.keys())
        for session_id in session_ids:
            await self.cleanup_session(session_id)


class SMSCodeHandler:
    """Обработчик SMS кодов"""
    
    def __init__(self):
        self.pending_requests: Dict[str, Dict[str, Any]] = {}
        
    async def request_sms_code(self, session_id: str, timeout: int = 60) -> Dict[str, Any]:
        """Запрос SMS кода от пользователя"""
        self.pending_requests[session_id] = {
            'requested_at': datetime.now(),
            'timeout': timeout,
            'status': 'pending'
        }
        
        return {
            'status': 'sms_requested',
            'session_id': session_id,
            'message': 'Введите SMS код для продолжения авторизации'
        }
        
    async def submit_sms_code(self, session_id: str, sms_code: str) -> Dict[str, Any]:
        """Подача SMS кода"""
        if session_id not in self.pending_requests:
            return {
                'status': 'error',
                'error': 'SMS код не запрашивался для данной сессии'
            }
            
        request = self.pending_requests[session_id]
        
        # Проверяем таймаут
        if datetime.now() > request['requested_at'] + timedelta(seconds=request['timeout']):
            del self.pending_requests[session_id]
            return {
                'status': 'timeout',
                'error': 'Время ожидания SMS кода истекло'
            }
            
        # Простая валидация кода (4-6 цифр)
        if not re.match(r'^\d{4,6}$', sms_code.strip()):
            return {
                'status': 'invalid',
                'error': 'SMS код должен содержать 4-6 цифр'
            }
            
        # Обновляем статус
        request['status'] = 'submitted'
        request['code'] = sms_code.strip()
        request['submitted_at'] = datetime.now()
        
        return {
            'status': 'accepted',
            'message': 'SMS код принят, продолжаем авторизацию'
        }
        
    def get_sms_code(self, session_id: str) -> Optional[str]:
        """Получить SMS код для сессии"""
        request = self.pending_requests.get(session_id)
        if request and request.get('status') == 'submitted':
            return request.get('code')
        return None
        
    def cleanup_request(self, session_id: str):
        """Очистка запроса SMS кода"""
        if session_id in self.pending_requests:
            del self.pending_requests[session_id]


# Глобальный экземпляр обработчика SMS
sms_handler = SMSCodeHandler()
