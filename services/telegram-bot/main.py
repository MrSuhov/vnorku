#!/usr/bin/env python3
"""
Исправленная версия main.py с динамическими ЛСД кнопками из базы данных
"""
import asyncio
import sys
import os

# Добавляем корневую папку проекта в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config.settings import settings
from shared.utils.unified_logging import setup_service_logging
import logging as log_module  # Избегаем конфликта с переменной logging
from shared.database import get_async_session
from shared.database.models import User, LSDConfig
from shared.models.base import UserStatus
from sqlalchemy import select
# Импорты модулей с дефисами через sys.path
import importlib.util
import sys
import os

# Добавляем telegram-bot в path
telegram_bot_path = os.path.join(os.path.dirname(__file__))
sys.path.insert(0, telegram_bot_path)

# Импортируем handlers
from handlers.registration_mock import RegistrationHandler  # Используем исправленную версию
from handlers.orders import OrderHandler
from handlers.callbacks import CallbackHandler
from handlers.user_input import UserInputHandler
from handlers.meal_plan import MealPlanHandler
from handlers.exclusions import exclusions_handler
from utils.security import NGrokUtils

# Импорты для логирования сообщений
from shared.utils.message_logger import (
    log_incoming_message,
    log_outgoing_message,
    IncomingCategory,
    OutgoingCategory
)
from shared.database.connection import SessionLocal
from utils.message_helpers import send_message_with_log, get_user_id_from_telegram
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import threading
import asyncio

# HTTP client with retries
from shared.utils.http_client import (
    RetryableHTTPClient,
    get_user_service_client,
    get_order_service_client,
    get_rpa_service_client
)

# Защита от повторной настройки логирования
if not os.environ.get('_TELEGRAM_LOGGING_SETUP'):
    setup_service_logging('telegram-bot', level=log_module.INFO)
    os.environ['_TELEGRAM_LOGGING_SETUP'] = '1'
logger = log_module.getLogger(__name__)


class KorzinkaTelegramBot:
    """Основной класс Telegram бота Korzinka"""
    
    def __init__(self):
        self.application = None
        self.registration_handler = RegistrationHandler()
        self.order_handler = OrderHandler()
        self.callback_handler = CallbackHandler()
        self.user_input_handler = UserInputHandler()  # Новый обработчик
        self.meal_plan_handler = MealPlanHandler()  # Обработчик планов питания

        # FastAPI для RPA запросов
        self.api_app = FastAPI(title="Telegram Bot API")
        self._setup_api_routes()
    
    async def get_active_lsd_buttons(self, user_id: int):
        """Получение активных ЛСД из базы данных и создание кнопок с индикацией наличия персистентных профилей"""
        try:
            logger.info(f"🔍 Loading active LSD configs for user {user_id}")

            # Проверяем наличие персистентных профилей через RPA-service
            lsds_with_profiles = set()

            try:
                rpa_client = get_rpa_service_client()
                response = await rpa_client.get(f"/profiles/check/{user_id}")

                if response and response.status_code == 200:
                    profiles_data = response.json()
                    if profiles_data.get('success'):
                        # Получаем список display_name ЛСД с профилями
                        profile_names = profiles_data['data'].get('lsds_with_profiles', [])
                        lsds_with_profiles = set(profile_names)
                        logger.info(f"✅ LSDs with persistent profiles: {profile_names}")
                    else:
                        logger.warning(f"⚠️ Profile check returned success=False")
                elif response:
                    logger.warning(f"⚠️ Profile check failed with status {response.status_code}")
                else:
                    logger.warning(f"⚠️ Profile check failed after retries")
            except Exception as profile_error:
                logger.error(f"❌ Error checking persistent profiles: {profile_error}")
                # Продолжаем без проверки профилей (все кнопки без галочек)

            async for db in get_async_session():
                # Загружаем все активные ЛСД
                result = await db.execute(
                    select(LSDConfig.id, LSDConfig.name, LSDConfig.display_name)
                    .where(LSDConfig.is_active == True)
                    .order_by(LSDConfig.display_name)
                )
                active_lsds = result.all()

                logger.info(f"🔍 Found {len(active_lsds)} active LSD configs:")
                for lsd in active_lsds:
                    logger.info(f"  - {lsd.name} ({lsd.display_name})")

                if not active_lsds:
                    return []

                # Создаем кнопки для каждого активного ЛСД
                keyboard = []

                for lsd in active_lsds:
                    lsd_id, name, display_name = lsd

                    # Добавляем ✅ если есть валидный персистентный профиль
                    if display_name in lsds_with_profiles:
                        button_text = f"✅ {display_name}"
                    else:
                        button_text = display_name

                    keyboard.append([
                        InlineKeyboardButton(
                            button_text,
                            callback_data=f"auth_{name}_{user_id}"
                        )
                    ])

                logger.info(f"🔘 Created {len(keyboard)} LSD buttons for user {user_id}")
                for i, row in enumerate(keyboard):
                    for j, button in enumerate(row):
                        logger.info(f"  Button [{i}][{j}]: {button.text} -> {button.callback_data}")

                return keyboard

        except Exception as e:
            logger.error(f"❌ Error loading active LSD configs: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return []
    
    def setup_handlers(self):
        """Настройка обработчиков команд и сообщений"""
        app = self.application
        
        # Команды
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("browse", self.browse_command))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CommandHandler("initiate", self.registration_handler.initiate_command))
        app.add_handler(CommandHandler("status", self.status_command))
        app.add_handler(CommandHandler("meal", self.meal_plan_handler.meal_command))
        app.add_handler(CommandHandler("settings", self.settings_command))
        app.add_handler(CommandHandler("delete", self.delete_command))
        
        # Callback queries (инлайн кнопки) - ЛОГИКА АВТОРИЗАЦИИ ЛСД
        print("🔧 Adding LSD authorization callback handler")
        async def safe_edit_message(query, new_text: str, **kwargs):
            """Безопасное редактирование сообщения"""
            try:
                current_text = query.message.text or ""
                current_markup = query.message.reply_markup
                new_markup = kwargs.get('reply_markup')
                
                # Проверяем изменения
                text_changed = current_text.strip() != new_text.strip()
                markup_changed = str(current_markup) != str(new_markup) if new_markup else current_markup is not None
                
                if text_changed or markup_changed:
                    await query.edit_message_text(new_text, **kwargs)
                    print(f"📝 Message edited (text_changed={text_changed}, markup_changed={markup_changed})")
                else:
                    print(f"📝 Message unchanged, skipping edit")
                    await query.answer("✅ Обработано", show_alert=False)
            except Exception as e:
                if "Message is not modified" in str(e):
                    print(f"📝 Telegram confirmed message not modified - continuing")
                    await query.answer("✅ Обработано", show_alert=False)
                else:
                    print(f"❌ Error editing message: {e}")
                    await query.answer("⚠️ Ошибка обновления", show_alert=True)
        
        async def lsd_auth_callback_handler(update, context):
            query = update.callback_query
            user_id = query.from_user.id
            data = query.data
            print(f"🎯 LSD AUTH CALLBACK: {data} from {user_id}")
            
            await query.answer()
            
            # Парсим callback_data формата: auth_[lsd_name]_[user_id]
            if data.startswith("auth_"):
                parts = data.split("_")
                if len(parts) >= 3:
                    # Обрабатываем случай ozon_fresh
                    if len(parts) == 4 and parts[1] == "ozon" and parts[2] == "fresh":
                        lsd_name = "ozon_fresh"
                        user_id_from_callback = parts[3]
                    else:
                        lsd_name = parts[1]
                        user_id_from_callback = parts[2]
                    
                    # Получаем отображаемое имя ЛСД из конфигурации
                    display_name = await self.get_lsd_display_name(lsd_name)
                    print(f"🔐 Starting REAL RPA auth for {lsd_name} ({display_name})")
                    
                    # Отправляем запрос в реальный RPA сервис
                    await safe_edit_message(
                        query,
                        f"🔐 Авторизация в {display_name}\n"
                        f"⏳ Это займет около 1 мин"
                    )
                    
                    try:
                        # Отправляем запрос в SELENIUM RPA сервис с ретраями
                        rpa_client = get_rpa_service_client()
                        response = await rpa_client.post(
                            "/auth/start",
                            json={
                                "telegram_id": user_id,
                                "lsd_name": lsd_name
                            }
                        )

                        if response and response.status_code == 200:
                            data = response.json()
                            
                            if data.get("success"):
                                session_id = data["data"].get("session_id")
                                status = data["data"].get("status")
                                message = data["data"].get("message")
                                
                                print(f"🎆 RPA session started: {session_id} (status: {status})")
                                
                                await safe_edit_message(
                                    query,
                                    f"🔐 Авторизация в {display_name}\n"
                                    f"⏳ Это займет около 1 мин"
                                )
                                
                                # Сохраняем session_id для отслеживания
                                # ТОДО: имплементировать поллинг статуса сессии
                                
                            else:
                                await safe_edit_message(
                                    query,
                                    f"❌ Ошибка запуска RPA: {data.get('detail', 'Неизвестная ошибка')}"
                                )
                        else:
                            # Ошибка RPA сервиса
                            await safe_edit_message(
                                query,
                                f"❌ Ошибка RPA сервиса: {response.status_code}\n\n"
                                f"Проверьте, что сервис запущен..."
                            )
                            
                    except Exception as e:
                        # Ошибка подключения к RPA
                        print(f"❌ RPA connection error: {e}")
                        # Проверяем, не является ли это ошибкой "Message is not modified"
                        if "Message is not modified" in str(e):
                            print(f"📝 Detected Telegram 'Message is not modified' error - RPA process may still be running")
                            await query.answer(f"🔄 RPA процесс запущен для {display_name}", show_alert=True)
                        else:
                            await safe_edit_message(
                                query,
                                f"❌ Не удалось подключиться к RPA сервису\n\n"
                                f"Ошибка: {e}\n\n"
                                f"Проверьте, что сервис запущен..."
                            )
                    
                    # Обновляем статус пользователя
                    from handlers.registration_mock import MOCK_USERS
                    from shared.models.base import UserStatus
                    
                    if user_id in MOCK_USERS:
                        MOCK_USERS[user_id]["status"] = UserStatus.ACTIVE
                        print(f"✅ Updated user {user_id} status to ACTIVE (after LSD auth)")
                    
                else:
                    await safe_edit_message(query, "❌ Неправильный формат callback данных")
            # Обработка выбора адреса
            elif data.startswith("addr_select_"):
                await self._handle_address_selection(update, context, query, data)
                return
            # Обработка заказов callback'ов
            elif data.startswith("order_"):
                await self.order_handler.handle_order_callback(update, context)
                return
            # Обработка browse callback'ов
            elif data.startswith("browse_"):
                parts = data.split("_")
                if len(parts) >= 2:
                    # Обрабатываем случаи с подчеркиваниями в именах ЛСД
                    if len(parts) == 3 and parts[1] == "ozon" and parts[2] == "fresh":
                        lsd_name = "ozon_fresh"
                    else:
                        lsd_name = parts[1]
                    
                    # Получаем отображаемое имя
                    display_name = await self.get_lsd_display_name(lsd_name)
                    print(f"🌍 Opening browser for {lsd_name} ({display_name})")
                    
                    await safe_edit_message(
                        query,
                        f"🌍 Открываю браузер для {display_name}..."
                    )
                    
                    try:
                        # Отправляем запрос на открытие браузера с куками (с ретраями)
                        rpa_client = RetryableHTTPClient(
                            base_url="http://localhost:8004",
                            max_retries=5,
                            timeout=90.0
                        )
                        response = await rpa_client.post(
                            "/browse/open",
                            json={
                                "telegram_id": user_id,
                                "lsd_name": lsd_name,
                                "auto_close_timeout": 60  # Браузер будет открыт 60 секунд
                            }
                        )

                        if response and response.status_code == 200:
                            data = response.json()
                            
                            if data.get("success"):
                                browser_info = data["data"]
                                message = browser_info.get("message")
                                cookies_count = browser_info.get("cookies_loaded", 0)
                                
                                await safe_edit_message(
                                    query,
                                    f"✅ {message}\n\n"
                                    f"🍪 Загружено кук: {cookies_count}\n"
                                    f"🌍 Браузер открыт для покупок!"
                                )
                                
                            else:
                                await safe_edit_message(
                                    query,
                                    f"❌ Ошибка: {data.get('message', 'Неизвестная ошибка')}"
                                )
                        else:
                            await safe_edit_message(
                                query,
                                f"❌ Ошибка сервиса: {response.status_code}"
                            )
                            
                    except Exception as e:
                        print(f"❌ Browser open error: {e}")
                        await safe_edit_message(
                            query,
                            f"❌ Не удалось открыть браузер: {e}"
                        )
            elif data.startswith("meal_"):
                # Обработка callback'ов планов питания
                await self.meal_plan_handler.handle_meal_callback(update, context)
            elif data.startswith("excl_"):
                # Обработка callback'ов исключений продуктов
                handled = await exclusions_handler.handle_callback(update, context)
                if not handled and data.startswith("excl_back_settings_"):
                    # Возврат к основным настройкам
                    await self._show_settings_menu(update, context)
            elif data.startswith("settings_"):
                # Обработка callback'ов настроек
                await self._handle_settings_callback(update, context, query, data)
            elif data.startswith("delete_"):
                # Обработка callback'ов удаления аккаунта
                await self._handle_delete_callback(update, context, query, data)
            else:
                await safe_edit_message(query, f"❓ Неизвестный callback: {data}")

        app.add_handler(CallbackQueryHandler(lsd_auth_callback_handler))

        # Контакты (для регистрации) - ДОЛЖНЫ БЫТЬ ПЕРВЫМИ!
        print("🔧 Adding contact handler FIRST")
        async def database_contact_handler(update, context):
            contact = update.message.contact
            user_id = update.effective_user.id
            phone = contact.phone_number
            db = context.bot_data.get('db_session')
            
            # Логируем входящий контакт
            if db:
                log_incoming_message(
                    db=db,
                    update=update,
                    category=IncomingCategory.CONTACT
                )
            
            # Нормализуем номер телефона - добавляем + если его нет
            if not phone.startswith('+'):
                phone = '+' + phone
            
            print(f"📞 CONTACT RECEIVED: {phone} from {user_id}")
            
            # Проверяем, что контакт принадлежит отправителю
            if contact.user_id != user_id:
                if db:
                    await send_message_with_log(
                        bot=context.bot,
                        db=db,
                        chat_id=update.effective_chat.id,
                        text="❌ Пожалуйста, поделитесь своим контактом.",
                        category=OutgoingCategory.ERROR,
                        telegram_id=user_id
                    )
                else:
                    await update.message.reply_text("❌ Пожалуйста, поделитесь своим контактом.")
                return
            
            # Сохраняем пользователя в базу данных с реальным телефоном
            user_data = {
                "username": update.effective_user.username,
                "first_name": update.effective_user.first_name,
                "last_name": update.effective_user.last_name
            }
            
            success = await self.save_user_to_database(user_id, user_data, phone)
            
            if success:
                print(f"✅ Saved user {user_id} to database: phone={phone[:3]}***{phone[-4:]}")
                
                # Обновляем статус на WAITING_ADDRESS (с ретраями)
                try:
                    user_client = get_user_service_client()
                    response = await user_client.patch(
                        f"/users/{user_id}",
                        json={
                            "status": UserStatus.WAITING_ADDRESS
                        }
                    )
                    if response:
                        print(f"✅ Updated user {user_id} status to WAITING_ADDRESS")
                    else:
                        print(f"⚠️ Failed to update user {user_id} status after retries")
                except Exception as e:
                    print(f"❌ Error updating status: {e}")
                
                # Также обновляем MOCK данные для совместимости
                from handlers.registration_mock import MOCK_USERS
                
                MOCK_USERS[user_id] = {
                    "telegram_id": user_id,
                    "username": update.effective_user.username,
                    "first_name": update.effective_user.first_name,
                    "last_name": update.effective_user.last_name,
                    "phone": phone,
                    "status": UserStatus.WAITING_ADDRESS
                }
                
                # Убираем клавиатуру и запрашиваем адрес с квартирой
                from telegram import ReplyKeyboardRemove

                if db:
                    await send_message_with_log(
                        bot=context.bot,
                        db=db,
                        chat_id=update.effective_chat.id,
                        text=f"✅ Номер телефона {phone[:3]}***{phone[-4:]} сохранен!\n\n"
                             f"📍 Пришлите адрес доставки с номером квартиры\n\n"
                             f"Пример: Профсоюзная 34, кв 25",
                        category=OutgoingCategory.REGISTRATION,
                        telegram_id=user_id,
                        reply_markup=ReplyKeyboardRemove()
                    )
                else:
                    await update.message.reply_text(
                        f"✅ Номер телефона {phone[:3]}***{phone[-4:]} сохранен!\n\n"
                        f"📍 Пришлите адрес доставки с номером квартиры\n\n"
                        f"Пример: Профсоюзная 34, кв 25",
                        reply_markup=ReplyKeyboardRemove()
                    )
            else:
                if db:
                    await send_message_with_log(
                        bot=context.bot,
                        db=db,
                        chat_id=update.effective_chat.id,
                        text="❌ Ошибка сохранения данных. Попробуйте позже.",
                        category=OutgoingCategory.ERROR,
                        telegram_id=user_id
                    )
                else:
                    await update.message.reply_text(
                        "❌ Ошибка сохранения данных. Попробуйте позже."
                    )
        
        app.add_handler(MessageHandler(filters.CONTACT, database_contact_handler))

        # Обычные сообщения - СНАЧАЛА SMS, ПОТОМ РЕГИСТРАЦИЯ
        print("🔧 Adding SMS handler FIRST, then registration")
        async def smart_message_handler(update, context):
            user_id = update.effective_user.id
            text = update.message.text
            chat_type = update.effective_chat.type
            db = context.bot_data.get('db_session')
            
            print(f"📨 SMART HANDLER: '{text}' from {user_id} in {chat_type}")
            
            # Пропускаем команды - они обрабатываются отдельными CommandHandler'ами
            if text and text.startswith('/'):
                print(f"🔄 Skipping command '{text}' - handled by CommandHandler")
                return
            
            # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: если сообщения нет или оно пустое, не обрабатываем
            if not text or not text.strip():
                print("🔄 Skipping empty text message")
                return

            # Проверяем, ожидает ли пользователь ввода продукта для исключений
            if await exclusions_handler.handle_product_input(update, context):
                print("✅ Product input handled by exclusions_handler")
                return

            if chat_type in ['group', 'supergroup']:
                # Групповые сообщения - обработка заказов
                print(f"👥 Group message - order processing")
                await self.order_handler.handle_order_message(update, context)
                return
            
            # Личные сообщения - СНАЧАЛА получаем статус пользователя
            print(f"👤 Private message - checking status first")
            
            # Логируем входящее сообщение (категорию определим позже)
            if db:
                log_incoming_message(
                    db=db,
                    update=update,
                    category=IncomingCategory.TEXT  # По умолчанию, уточним позже
                )
            
            # ПОЛУЧАЕМ СТАТУС ПОЛЬЗОВАТЕЛЯ ПЕРВЫМ!
            from handlers.registration_mock import MOCK_USERS
            
            user_data = MOCK_USERS.get(user_id)
            
            # Если пользователя нет в MOCK_USERS, пробуем загрузить из базы данных
            if not user_data:
                print(f"❌ User {user_id} not found in MOCK_USERS, checking database...")
                
                # Проверяем базу данных
                db_user = await self.get_user_from_database(user_id)
                
                if db_user and db_user.get('telegram_id'):
                    print(f"✅ User {user_id} found in database, updating MOCK_USERS")

                    # Добавляем пользователя в MOCK_USERS
                    db_status = db_user.get('status', UserStatus.WAITING_CONTACT)
                    MOCK_USERS[user_id] = {
                        "telegram_id": db_user['telegram_id'],
                        "username": db_user.get('username'),
                        "first_name": db_user.get('first_name'),
                        "last_name": db_user.get('last_name'),
                        "phone": db_user.get('phone'),
                        "status": db_status
                    }
                    print(f"✅ User {user_id} synced to MOCK_USERS with status: {db_status}")

                    user_data = MOCK_USERS[user_id]  # Используем обновленные данные
                    
                else:
                    # Новый пользователь - автоматически начинаем регистрацию
                    print(f"🆕 New user {user_id} - auto-starting registration")

                    # Создаем пользователя в базе
                    user_data_dict = {
                        "username": update.effective_user.username,
                        "first_name": update.effective_user.first_name,
                        "last_name": update.effective_user.last_name
                    }
                    await self.save_user_to_database(user_id, user_data_dict)

                    # Добавляем в MOCK_USERS
                    MOCK_USERS[user_id] = {
                        "telegram_id": user_id,
                        "username": update.effective_user.username,
                        "first_name": update.effective_user.first_name,
                        "last_name": update.effective_user.last_name,
                        "phone": None,
                        "status": UserStatus.WAITING_CONTACT
                    }

                    # Запрашиваем контакт
                    from telegram import KeyboardButton, ReplyKeyboardMarkup
                    keyboard = [[KeyboardButton("📞 Поделиться контактом", request_contact=True)]]
                    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

                    registration_text = (
                        "👋 Привет! Я - бот Vnorku для персонального трека калорий.\n"
                        "📞 Для регистрации поделитесь своим контактом, нажав кнопку ниже.\n"
                        "📋 Продолжая регистрацию, вы принимаете [Условия сервиса](https://vnorku.ru/terms) "
                        "и [Политику обработки персональных данных](https://vnorku.ru/privacy).\n"
                        "Для изменения данных нажми /settings\n"
                        "Для удаления учетной записи нажми /delete\n"
                        "Для управления планом питания нажми /meals"
                    )

                    if db:
                        await send_message_with_log(
                            bot=context.bot,
                            db=db,
                            chat_id=update.effective_chat.id,
                            text=registration_text,
                            category=OutgoingCategory.REGISTRATION,
                            telegram_id=user_id,
                            reply_markup=reply_markup,
                            parse_mode="Markdown",
                            disable_web_page_preview=True
                        )
                    else:
                        await update.message.reply_text(
                            registration_text,
                            reply_markup=reply_markup,
                            parse_mode="Markdown",
                            disable_web_page_preview=True
                        )
                    return
                    
            status = user_data.get("status")
            
            print(f"🔍 Status: {status}")
            
            # 1️⃣ ПРОВЕРЯЕМ SMS КОД ПЕРВЫМ!
            try:
                is_waiting = await self.user_input_handler.is_waiting_for_input(user_id)
                print(f"📱 SMS WAITING RESULT: {is_waiting}")

                if is_waiting:
                    # Обработка SMS кода
                    print(f"📱 ⚡ SMS CODE processing for {user_id}")
                    await self.user_input_handler.handle_user_input(update, context)
                    return  # Важно: останавливаемся на SMS

            except Exception as e:
                print(f"❌ SMS CHECK ERROR: {e}")

            # 1.5️⃣ ПРОВЕРЯЕМ ВВОД ДЛЯ КАЛЬКУЛЯТОРА КБЖУ
            try:
                meal_handled = await self.meal_plan_handler.process_calc_input(update, context)
                if meal_handled:
                    print(f"🍽️ Meal calculator input processed for {user_id}")
                    return
            except Exception as e:
                print(f"❌ MEAL CALC CHECK ERROR: {e}")
            
            # 2️⃣ ПРОВЕРЯЕМ ОЖИДАНИЕ АДРЕСА
            if status == UserStatus.WAITING_ADDRESS:
                print(f"📍 Processing address for user {user_id}")

                # Текст сообщения = адрес с квартирой
                address_query = text.strip()

                # Получаем подсказки от DaData
                from shared.utils.dadata_helper import DaDataHelper

                suggestions = await DaDataHelper.get_address_suggestions(address_query, count=5)

                if not suggestions:
                    # Нет подсказок - просим уточнить адрес
                    print(f"❌ No DaData suggestions for query: {address_query}")
                    if db:
                        await send_message_with_log(
                            bot=context.bot,
                            db=db,
                            chat_id=update.effective_chat.id,
                            text="❌ Не удалось найти адрес. Пожалуйста, уточните адрес.\n\n"
                                 "Пример: Профсоюзная 34, кв 25",
                            category=OutgoingCategory.ERROR,
                            telegram_id=user_id
                        )
                    else:
                        await update.message.reply_text(
                            "❌ Не удалось найти адрес. Пожалуйста, уточните адрес.\n\n"
                            "Пример: Профсоюзная 34, кв 25"
                        )
                    return

                # Создаем inline кнопки с подсказками
                keyboard = []
                for i, suggestion in enumerate(suggestions):
                    button_text = DaDataHelper.format_suggestion_for_button(suggestion)
                    # Callback data формата: addr_select_{index}_{user_id}
                    callback_data = f"addr_select_{i}_{user_id}"
                    keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

                # Сохраняем подсказки в context.user_data для использования в callback
                context.user_data['address_suggestions'] = suggestions

                reply_markup = InlineKeyboardMarkup(keyboard)

                print(f"✅ Sending {len(suggestions)} address suggestions to user {user_id}")

                if db:
                    await send_message_with_log(
                        bot=context.bot,
                        db=db,
                        chat_id=update.effective_chat.id,
                        text="📍 Выберите ваш адрес из списка:",
                        category=OutgoingCategory.REGISTRATION,
                        telegram_id=user_id,
                        reply_markup=reply_markup
                    )
                else:
                    await update.message.reply_text(
                        "📍 Выберите ваш адрес из списка:",
                        reply_markup=reply_markup
                    )

                return  # Останавливаемся после обработки адреса
            
            # 3️⃣ ПРОВЕРЯЕМ ОЖИДАНИЕ НОМЕРА КВАРТИРЫ
            if status == UserStatus.WAITING_APARTMENT:
                print(f"🏠 Processing apartment for user {user_id}")
                
                # Текст сообщения = номер квартиры
                apartment = text.strip()
                
                # Сохраняем номер квартиры в базу данных (с ретраями)
                try:
                    user_client = get_user_service_client()
                    response = await user_client.patch(
                        f"/users/{user_id}",
                        json={
                            "apartment": apartment,
                            "status": UserStatus.ACTIVE
                        }
                    )

                    if response and response.status_code == 200:
                        print(f"✅ Apartment saved for user {user_id}")

                        # Обновляем MOCK данные
                        MOCK_USERS[user_id]["apartment"] = apartment
                        MOCK_USERS[user_id]["status"] = UserStatus.ACTIVE

                        # Показываем ЛСД кнопки
                        keyboard = await self.get_active_lsd_buttons(user_id)

                        if keyboard:
                            reply_markup = InlineKeyboardMarkup(keyboard)

                            if db:
                                await send_message_with_log(
                                    bot=context.bot,
                                    db=db,
                                    chat_id=update.effective_chat.id,
                                    text="✅ Вы зарегистрированы!\n\n"
                                         "После запуска сервиса мы направим вам инструкцию по дальнейшим шагам.",
                                    category=OutgoingCategory.REGISTRATION,
                                    telegram_id=user_id
                                )
                            else:
                                await update.message.reply_text(
                                    "✅ Вы зарегистрированы!\n\n"
                                    "После запуска сервиса мы направим вам инструкцию по дальнейшим шагам."
                                )
                        else:
                            if db:
                                await send_message_with_log(
                                    bot=context.bot,
                                    db=db,
                                    chat_id=update.effective_chat.id,
                                    text="✅ Вы зарегистрированы!\n\n"
                                         "После запуска сервиса мы направим вам инструкцию по дальнейшим шагам.",
                                    category=OutgoingCategory.REGISTRATION,
                                    telegram_id=user_id
                                )
                            else:
                                await update.message.reply_text(
                                    "✅ Вы зарегистрированы!\n\n"
                                    "После запуска сервиса мы направим вам инструкцию по дальнейшим шагам."
                                )
                    else:
                        print(f"❌ Error saving apartment: {response.status_code if response else 'no response'}")
                        if db:
                            await send_message_with_log(
                                bot=context.bot,
                                db=db,
                                chat_id=update.effective_chat.id,
                                text="❌ Ошибка сохранения номера квартиры. Попробуйте еще раз.",
                                category=OutgoingCategory.ERROR,
                                telegram_id=user_id
                            )
                        else:
                            await update.message.reply_text(
                                "❌ Ошибка сохранения номера квартиры. Попробуйте еще раз."
                            )

                except Exception as e:
                    print(f"❌ Error calling user-service: {e}")
                    if db:
                        await send_message_with_log(
                            bot=context.bot,
                            db=db,
                            chat_id=update.effective_chat.id,
                            text="❌ Ошибка сохранения номера квартиры. Попробуйте позже.",
                            category=OutgoingCategory.ERROR,
                            telegram_id=user_id
                        )
                    else:
                        await update.message.reply_text(
                            "❌ Ошибка сохранения номера квартиры. Попробуйте позже."
                        )
                
                return  # Останавливаемся после обработки номера квартиры
            
            # 4️⃣ ОБРАБОТКА ПО СТАТУСУ ПОЛЬЗОВАТЕЛЯ
            print(f"🔐 Processing by status: {status}")
            
            # Логика по статусной модели
            if status == UserStatus.BLOCKED:
                print("🚫 User is blocked")
                if db:
                    await send_message_with_log(
                        bot=context.bot,
                        db=db,
                        chat_id=update.effective_chat.id,
                        text="🚫 Ваш аккаунт заблокирован.\n\n"
                             "Для разблокировки обратитесь к администратору.",
                        category=OutgoingCategory.ERROR,
                        telegram_id=user_id
                    )
                else:
                    await update.message.reply_text(
                        "🚫 Ваш аккаунт заблокирован.\n\n"
                        "Для разблокировки обратитесь к администратору."
                    )
                return
                
            elif status == UserStatus.WAITING_CONTACT:
                print("📞 Requesting contact")
                # Просим поделиться контактом
                from telegram import KeyboardButton, ReplyKeyboardMarkup
                keyboard = [[KeyboardButton("📞 Поделиться контактом", request_contact=True)]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

                contact_text = (
                    "👋 Для продолжения поделитесь своим контактом, нажав кнопку ниже.\n\n"
                    "📋 Продолжая регистрацию, вы принимаете [Условия сервиса](https://vnorku.ru/terms) "
                    "и [Политику обработки персональных данных](https://vnorku.ru/privacy)."
                )

                if db:
                    await send_message_with_log(
                        bot=context.bot,
                        db=db,
                        chat_id=update.effective_chat.id,
                        text=contact_text,
                        category=OutgoingCategory.REGISTRATION,
                        telegram_id=user_id,
                        reply_markup=reply_markup,
                        parse_mode="Markdown",
                        disable_web_page_preview=True
                    )
                else:
                    await update.message.reply_text(
                        contact_text,
                        reply_markup=reply_markup,
                        parse_mode="Markdown",
                        disable_web_page_preview=True
                    )
                return
            
            elif status == UserStatus.WAITING_ADDRESS:
                print("📍 User should send address")
                if db:
                    await send_message_with_log(
                        bot=context.bot,
                        db=db,
                        chat_id=update.effective_chat.id,
                        text="📍 Пришлите адрес доставки с указанием индекса, улицы и номера дома\n\n"
                             "Пример: 117335, Профсоюзная 32",
                        category=OutgoingCategory.REGISTRATION,
                        telegram_id=user_id
                    )
                else:
                    await update.message.reply_text(
                        "📍 Пришлите адрес доставки с указанием индекса, улицы и номера дома\n\n"
                        "Пример: 117335, Профсоюзная 32"
                    )
                return
            
            elif status == UserStatus.WAITING_APARTMENT:
                print("🏠 User should send apartment")
                if db:
                    await send_message_with_log(
                        bot=context.bot,
                        db=db,
                        chat_id=update.effective_chat.id,
                        text="🏠 Пришлите номер квартиры\n\n"
                             "Пример: 42",
                        category=OutgoingCategory.REGISTRATION,
                        telegram_id=user_id
                    )
                else:
                    await update.message.reply_text(
                        "🏠 Пришлите номер квартиры\n\n"
                        "Пример: 42"
                    )
                return
                
            elif status == UserStatus.ACTIVE:
                # Заглушка - прямые заказы в боте ещё не реализованы
                print("✅ User ACTIVE - showing stub message")

                # Получаем адрес и квартиру пользователя для отображения
                address = user_data.get('address', '')
                apartment = user_data.get('apartment', '')

                stub_text = "✅ Вы зарегистрированы!\n\n"
                if address:
                    stub_text += f"📍 {address}\n"
                if apartment:
                    stub_text += f"🏠 Квартира: {apartment}\n\n"
                stub_text += "После запуска сервиса мы направим вам инструкцию по дальнейшим шагам."

                if db:
                    await send_message_with_log(
                        bot=context.bot,
                        db=db,
                        chat_id=update.effective_chat.id,
                        text=stub_text,
                        category=OutgoingCategory.REGISTRATION,
                        telegram_id=user_id
                    )
                else:
                    await update.message.reply_text(stub_text)
                return
                
            else:
                # Неизвестный статус
                print(f"🧐 Unknown status: {status}")
                if db:
                    await send_message_with_log(
                        bot=context.bot,
                        db=db,
                        chat_id=update.effective_chat.id,
                        text=f"🧐 Неизвестное состояние: {status}\n"
                             f"Попробуйте /start для перезапуска регистрации.",
                        category=OutgoingCategory.ERROR,
                        telegram_id=user_id
                    )
                else:
                    await update.message.reply_text(
                        f"🧐 Неизвестное состояние: {status}\n"
                        f"Попробуйте /start для перезапуска регистрации."
                    )
                return
        
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), smart_message_handler))

        # Обработка ошибок
        app.add_error_handler(self.error_handler)
    
    async def save_user_to_database(self, telegram_id: int, user_data: dict, phone: str = None) -> bool:
        """Сохранение пользователя в базу данных"""
        try:
            async for db in get_async_session():
                # Проверяем, есть ли пользователь
                result = await db.execute(select(User).where(User.telegram_id == telegram_id))
                existing_user = result.scalar_one_or_none()
                
                if existing_user:
                    # Обновляем существующего
                    if phone:
                        existing_user.phone = phone
                        existing_user.status = UserStatus.ACTIVE
                    
                    if user_data.get('username'):
                        existing_user.username = user_data['username']
                    if user_data.get('first_name'):
                        existing_user.first_name = user_data['first_name']
                    if user_data.get('last_name'):
                        existing_user.last_name = user_data['last_name']
                        
                    logger.info(f"✅ Updated user {telegram_id} in database")
                else:
                    # Создаем нового
                    new_user = User(
                        telegram_id=telegram_id,
                        username=user_data.get('username'),
                        first_name=user_data.get('first_name'),
                        last_name=user_data.get('last_name'),
                        phone=phone,
                        status=UserStatus.ACTIVE if phone else UserStatus.WAITING_CONTACT
                    )
                    db.add(new_user)
                    logger.info(f"✅ Created new user {telegram_id} in database")
                    
                await db.commit()
                return True
                
        except Exception as e:
            logger.error(f"❌ Error saving user to database: {e}")
            return False
        
    async def get_user_from_database(self, telegram_id: int) -> dict:
        """Получение пользователя из базы данных"""
        try:
            async for db in get_async_session():
                result = await db.execute(select(User).where(User.telegram_id == telegram_id))
                user = result.scalar_one_or_none()

                if user:
                    return {
                        "telegram_id": user.telegram_id,
                        "username": user.username,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "phone": user.phone,
                        "address": user.address,
                        "apartment": user.apartment,
                        "status": user.status
                    }
                return {}
        except Exception as e:
            logger.error(f"❌ Error getting user from database: {e}")
            return {}
    
    async def _handle_address_selection(self, update, context, query, callback_data):
        """Обработка выбора адреса из DaData подсказок"""
        user_id = query.from_user.id

        try:
            # Парсим callback_data: addr_select_{index}_{user_id}
            parts = callback_data.split("_")
            if len(parts) < 4:
                await query.answer("❌ Ошибка данных", show_alert=True)
                return

            suggestion_index = int(parts[2])

            # Получаем сохраненные подсказки из context.user_data
            suggestions = context.user_data.get('address_suggestions')

            if not suggestions or suggestion_index >= len(suggestions):
                await query.answer("❌ Адрес не найден. Попробуйте ещё раз.", show_alert=True)
                return

            selected_suggestion = suggestions[suggestion_index]

            # Извлекаем адрес и квартиру
            address = selected_suggestion.get('address', '')
            apartment = selected_suggestion.get('apartment', '')

            print(f"✅ User {user_id} selected address: {address}, apartment: {apartment}")

            # Сохраняем адрес и квартиру в базу данных (с ретраями)
            user_client = get_user_service_client()
            response = await user_client.patch(
                f"/users/{user_id}",
                json={
                    "address": address,
                    "apartment": apartment,
                    "status": UserStatus.ACTIVE
                }
            )

            if not response or response.status_code != 200:
                print(f"❌ Error saving address: {response.status_code if response else 'no response'}")
                await query.answer("❌ Ошибка сохранения адреса", show_alert=True)
                return

            # Обновляем MOCK данные
            from handlers.registration_mock import MOCK_USERS
            if user_id in MOCK_USERS:
                MOCK_USERS[user_id]["address"] = address
                MOCK_USERS[user_id]["apartment"] = apartment
                MOCK_USERS[user_id]["status"] = UserStatus.ACTIVE

            # Удаляем подсказки из context
            context.user_data.pop('address_suggestions', None)

            # Отвечаем на callback
            await query.answer("✅ Адрес сохранен", show_alert=False)

            # Редактируем сообщение с подтверждением регистрации
            await query.edit_message_text(
                f"✅ Вы зарегистрированы!\n\n"
                f"📍 {address}\n"
                f"🏠 Квартира: {apartment}\n\n"
                f"После запуска сервиса мы направим вам инструкцию по дальнейшим шагам."
            )

        except Exception as e:
            print(f"❌ Error handling address selection: {e}")
            import traceback
            traceback.print_exc()
            await query.answer("❌ Ошибка обработки адреса", show_alert=True)

    async def get_lsd_display_name(self, lsd_name: str) -> str:
        """Получение отображаемого имени ЛСД из базы данных"""
        try:
            async for db in get_async_session():
                result = await db.execute(
                    select(LSDConfig.display_name)
                    .where(LSDConfig.name == lsd_name)
                )
                lsd_config = result.scalar_one_or_none()
                
                if lsd_config:
                    return lsd_config
                break
        except Exception as e:
            logger.error(f"❌ Error getting LSD display name: {e}")
        
        # Fallback к hardcoded маппингу
        lsd_display_names = {
            "samokat": "🛒 Самокат",
            "yandex": "🍎 Яндекс Лавка", 
            "vkusvill": "📦 ВкусВилл",
            "perekrestok": "🏪 Перекрёсток",
            "ozon_fresh": "📦 Ozon Fresh",
            "utkonos": "🐧 Утконос",
            "pyaterochka": "5️⃣ Пятёрочка",
            "magnit": "🧲 Магнит",
            "lenta": "🎀 Лента",
            "auchan": "🏬 Ашан",
            "metro": "🚇 METRO",
            "azbuka_vkusa": "📖 Азбука Вкуса",
            "globus": "🌍 Глобус"
        }
        
        return lsd_display_names.get(lsd_name, lsd_name.title())
    
    def _setup_api_routes(self):
        
        class UserInputRequest(BaseModel):
            telegram_id: int
            message: str
            session_id: str
            input_type: str
            action: str
        
        class QRLinkRequest(BaseModel):
            telegram_id: int
            qr_link: str
            prompt: str

        class AuthSuccessRequest(BaseModel):
            telegram_id: int
            message: str
            action: str
            result: dict
            qr_message_id: int = None  # Добавляем message_id сообщения со ссылкой

        @self.api_app.post("/rpa/user-input-request")
        async def handle_user_input_request(request: UserInputRequest):
            """Обработка запроса на пользовательский ввод"""
            try:
                logger.info(f"📲 Received user input request for user {request.telegram_id}")
                
                # Передаем запрос обработчику
                await self.user_input_handler.request_user_input(
                    self.application.bot,
                    request.telegram_id,
                    request.message,
                    request.session_id,
                    request.input_type
                )
                
                return {"success": True, "message": "User input request sent"}
                
            except Exception as e:
                logger.error(f"Error handling user input request: {e}")
                return {"success": False, "error": str(e)}
        
        @self.api_app.post("/rpa/send-qr-link")
        async def handle_send_qr_link(request: QRLinkRequest):
            """Отправка QR ссылки пользователю"""
            try:
                logger.info(f"🔗 Sending QR link to user {request.telegram_id}: {request.qr_link[:50]}...")
                
                # Отправляем QR ссылку пользователю в Telegram БЕЗ preview
                message = await self.application.bot.send_message(
                    chat_id=request.telegram_id,
                    text=f"{request.prompt}\n{request.qr_link}",
                    parse_mode=None,
                    disable_web_page_preview=True  # Отключаем предпросмотр
                )
                
                logger.info(f"✅ QR link sent successfully to user {request.telegram_id}, message_id={message.message_id}")
                return {"success": True, "message": "QR link sent to user", "message_id": message.message_id}
                
            except Exception as e:
                logger.error(f"❌ Error sending QR link to user: {e}")
                return {"success": False, "error": str(e)}
        
        @self.api_app.post("/rpa/qr-code-extracted")
        async def handle_qr_code_extracted(request: QRLinkRequest):
            """Обработка экстракции QR кода - отправка ссылки без предпросмотра"""
            try:
                logger.info(f"📱 Sending extracted QR link to user {request.telegram_id}")
                
                # Отправляем сообщение со ссылкой без предпросмотра
                message = await self.application.bot.send_message(
                    chat_id=request.telegram_id,
                    text=f"{request.prompt}\n{request.qr_link}",
                    parse_mode=None,
                    disable_web_page_preview=True  # Отключаем предпросмотр линков
                )
                
                logger.info(f"✅ QR link sent successfully, message_id={message.message_id}")
                return {"success": True, "message": "QR link sent", "message_id": message.message_id}
                
            except Exception as e:
                logger.error(f"❌ Error sending QR link: {e}")
                return {"success": False, "error": str(e)}
        
        @self.api_app.post("/rpa/auth-success")
        async def handle_auth_success(request: AuthSuccessRequest):
            """Обработка успешной авторизации"""
            try:
                logger.info(f"🎉 Received auth success for user {request.telegram_id}")
                
                lsd_name = request.result.get("lsd_name", "")
                display_name = request.result.get("display_name", "службе доставки")
                
                # Удаляем сообщение со ссылкой если оно есть
                if request.qr_message_id:
                    try:
                        await self.application.bot.delete_message(
                            chat_id=request.telegram_id,
                            message_id=request.qr_message_id
                        )
                        logger.info(f"🗑️ Deleted QR link message {request.qr_message_id}")
                    except Exception as e:
                        logger.error(f"❌ Error deleting QR link message: {e}")
                
                # Отправляем уведомление об успешной авторизации
                success_message = f"🎉 Авторизация в {display_name} завершена успешно!\n\n"
                success_message += f"✅ Куки сохранены"
                
                await self.application.bot.send_message(
                    chat_id=request.telegram_id,
                    text=success_message,
                    parse_mode=None
                )
                
                return {"success": True, "message": "Auth success notification sent"}
                
            except Exception as e:
                logger.error(f"Error sending auth success notification: {e}")
                return {"success": False, "error": str(e)}
        
        class SendMessageRequest(BaseModel):
            chat_id: str
            text: str
            order_id: int = None
            reply_to_message_id: int = None
            parse_mode: str = "HTML"
            disable_web_page_preview: bool = True

        class SendDocumentRequest(BaseModel):
            chat_id: str
            document_base64: str
            filename: str
            caption: str = None
            order_id: int = None
            reply_to_message_id: int = None

        @self.api_app.post("/api/send-message")
        async def api_send_message(request: SendMessageRequest):
            """
            API endpoint для отправки сообщений в Telegram с автоматическим логированием
            """
            # Используем async session вместо синхронной
            async for db in get_async_session():
                try:
                    logger.info(f"📤 API request to send message to {request.chat_id}")

                    # Отправляем сообщение с автоматическим логированием
                    sent_message = await send_message_with_log(
                        bot=self.application.bot,
                        db=db,
                        chat_id=request.chat_id,
                        text=request.text,
                        category=OutgoingCategory.ORDER_RESULT,
                        order_id=request.order_id,
                        parse_mode=request.parse_mode,
                        disable_web_page_preview=request.disable_web_page_preview,
                        reply_to_message_id=request.reply_to_message_id
                    )

                    return {
                        "success": True,
                        "message": "Message sent successfully",
                        "telegram_message_id": sent_message.message_id if sent_message else None
                    }

                except Exception as e:
                    logger.error(f"❌ Error sending message via API: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return {
                        "success": False,
                        "error": str(e)
                    }

        @self.api_app.post("/api/send-document")
        async def api_send_document(request: SendDocumentRequest):
            """
            API endpoint для отправки документов в Telegram с автоматическим логированием
            """
            # Создаем НОВУЮ АСИНХРОННУЮ сессию для КАЖДОГО запроса
            from shared.database.connection import AsyncSessionLocal

            async with AsyncSessionLocal() as db:
                try:
                    import base64
                    from io import BytesIO

                    logger.info(f"📄 API request to send document to {request.chat_id}: {request.filename}")

                    # Декодируем base64 в bytes
                    document_bytes = base64.b64decode(request.document_base64)

                    # Создаем файловый объект
                    document_file = BytesIO(document_bytes)
                    document_file.name = request.filename

                    # Отправляем документ
                    sent_message = await self.application.bot.send_document(
                        chat_id=request.chat_id,
                        document=document_file,
                        caption=request.caption,
                        reply_to_message_id=request.reply_to_message_id
                    )

                    # Логируем отправку документа
                    from shared.utils.message_logger import log_outgoing_message, log_telegram_api_response

                    user_msg_record = await log_outgoing_message(
                        db=db,
                        chat_id=request.chat_id,
                        message_text=request.caption or f"Document: {request.filename} ({len(document_bytes)} bytes)",
                        category=OutgoingCategory.ORDER_RESULT,
                        order_id=request.order_id,
                        reply_to_telegram_message_id=request.reply_to_message_id
                    )

                    # ВАЖНО: Коммитим сразу после логирования
                    await db.commit()

                    # Обновляем с данными от Telegram API
                    if user_msg_record:
                        await log_telegram_api_response(
                            db=db,
                            user_message_id=user_msg_record.id,
                            sent_message=sent_message
                        )

                    logger.info(f"✅ Document sent successfully, message_id={sent_message.message_id}")

                    return {
                        "success": True,
                        "message": "Document sent successfully",
                        "telegram_message_id": sent_message.message_id
                    }

                except Exception as e:
                    logger.error(f"❌ Error sending document via API: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return {
                        "success": False,
                        "error": str(e)
                    }

        @self.api_app.get("/health")
        async def health():
            return {"status": "healthy", "service": "telegram-bot"}
            
        @self.api_app.get("/mock-users/{telegram_id}")
        async def get_mock_user(telegram_id: int):
            """API для получения MOCK данных пользователя"""
            try:
                from handlers.registration_mock import MOCK_USERS
                user_data = MOCK_USERS.get(telegram_id)
                if user_data:
                    return user_data
                else:
                    return {"error": "User not found"}
            except Exception as e:
                return {"error": str(e)}
    
    async def start_command(self, update, context):
        """Обработчик команды /start - Проверка базы данных"""
        user_id = update.effective_user.id

        print(f"🚀 /start from {user_id}")
        
        # Проверяем, есть ли пользователь в базе данных
        user_data = await self.get_user_from_database(user_id)
        
        # Проверяем статус
        status = user_data.get('status') if user_data else None

        # Синхронизируем с MOCK_USERS если пользователь найден в БД
        if user_data and user_data.get('telegram_id'):
            from handlers.registration_mock import MOCK_USERS
            MOCK_USERS[user_id] = {
                "telegram_id": user_data['telegram_id'],
                "username": user_data.get('username'),
                "first_name": user_data.get('first_name'),
                "last_name": user_data.get('last_name'),
                "phone": user_data.get('phone'),
                "status": user_data.get('status', UserStatus.WAITING_CONTACT)
            }
            print(f"✅ User {user_id} synced to MOCK_USERS from DB (status: {status})")

        # Обработка по статусу
        if status == UserStatus.WAITING_CONTACT:
            # Пользователь начал регистрацию, но не отправил контакт
            print(f"📞 User {user_id} waiting for contact - requesting again")
            from telegram import KeyboardButton, ReplyKeyboardMarkup
            keyboard = [[KeyboardButton("📞 Поделиться контактом", request_contact=True)]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

            await update.message.reply_text(
                f"👋 С возвращением! Для продолжения регистрации поделитесь контактом.\n\n"
                f"📋 Продолжая регистрацию, вы принимаете [Условия сервиса](https://vnorku.ru/terms) "
                f"и [Политику обработки персональных данных](https://vnorku.ru/privacy).",
                reply_markup=reply_markup,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            return

        if status == UserStatus.WAITING_ADDRESS:
            print(f"📍 User {user_id} waiting for address")
            await update.message.reply_text(
                f"👋 Привет! Ваш номер уже сохранен.\n\n"
                f"📍 Пришлите адрес доставки с указанием индекса, улицы и номера дома\n\n"
                f"Пример: 117335, Профсоюзная 32"
            )
            return
        
        if status == UserStatus.WAITING_APARTMENT:
            print(f"🏠 User {user_id} waiting for apartment")
            await update.message.reply_text(
                f"👋 Привет! Ваш адрес уже сохранен.\n\n"
                f"🏠 Пришлите номер квартиры\n\n"
                f"Пример: 42"
            )
            return
        
        if user_data and user_data.get('phone') and status == UserStatus.ACTIVE:
            # Заглушка - прямые заказы в боте ещё не реализованы
            print(f"✅ User {user_id} found in database with phone and ACTIVE status - showing stub")

            # Получаем адрес и квартиру пользователя для отображения
            address = user_data.get('address', '')
            apartment = user_data.get('apartment', '')

            stub_text = "✅ Вы зарегистрированы!\n\n"
            if address:
                stub_text += f"📍 {address}\n"
            if apartment:
                stub_text += f"🏠 Квартира: {apartment}\n\n"
            stub_text += "После запуска сервиса мы направим вам инструкцию по дальнейшим шагам."

            await update.message.reply_text(stub_text)
        else:
            # Пользователь новый или нет телефона - запрашиваем контакт
            print(f"🚀 New user {user_id} - requesting contact (direct registration)")

            # Создаем пользователя в базе без телефона
            user_data_dict = {
                "username": update.effective_user.username,
                "first_name": update.effective_user.first_name,
                "last_name": update.effective_user.last_name
            }
            await self.save_user_to_database(user_id, user_data_dict)

            # Синхронизируем с MOCK_USERS для совместимости с остальным flow
            from handlers.registration_mock import MOCK_USERS
            MOCK_USERS[user_id] = {
                "telegram_id": user_id,
                "username": update.effective_user.username,
                "first_name": update.effective_user.first_name,
                "last_name": update.effective_user.last_name,
                "phone": None,
                "status": UserStatus.WAITING_CONTACT
            }
            print(f"✅ User {user_id} added to MOCK_USERS with status WAITING_CONTACT")

            # Запрашиваем контакт
            from telegram import KeyboardButton, ReplyKeyboardMarkup
            keyboard = [[KeyboardButton("📞 Поделиться контактом", request_contact=True)]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

            await update.message.reply_text(
                f"👋 Привет! Я - бот Vnorku для персонального трека калорий.\n"
                f"📞 Для регистрации поделитесь своим контактом, нажав кнопку ниже.\n"
                f"📋 Продолжая регистрацию, вы принимаете [Условия сервиса](https://vnorku.ru/terms) "
                f"и [Политику обработки персональных данных](https://vnorku.ru/privacy).\n"
                f"Для изменения данных нажми /settings\n"
                f"Для удаления учетной записи нажми /delete\n"
                f"Для управления планом питания нажми /meals",
                reply_markup=reply_markup,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
    
    async def _start_registration(self, update, context):
        """Начать процесс регистрации - создать пользователя и запросить контакт"""
        user_id = update.effective_user.id
        print(f"🚀 Starting registration for user {user_id}")

        # Создаем пользователя в базе без телефона
        user_data_dict = {
            "username": update.effective_user.username,
            "first_name": update.effective_user.first_name,
            "last_name": update.effective_user.last_name
        }
        await self.save_user_to_database(user_id, user_data_dict)

        # Синхронизируем с MOCK_USERS для совместимости с остальным flow
        from handlers.registration_mock import MOCK_USERS
        MOCK_USERS[user_id] = {
            "telegram_id": user_id,
            "username": update.effective_user.username,
            "first_name": update.effective_user.first_name,
            "last_name": update.effective_user.last_name,
            "phone": None,
            "status": UserStatus.WAITING_CONTACT
        }
        print(f"✅ User {user_id} added to MOCK_USERS with status WAITING_CONTACT")

        # Запрашиваем контакт
        from telegram import KeyboardButton, ReplyKeyboardMarkup
        keyboard = [[KeyboardButton("📞 Поделиться контактом", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

        await update.message.reply_text(
            f"👋 Привет! Я - бот Vnorku для персонального трека калорий.\n"
            f"📞 Для регистрации поделитесь своим контактом, нажав кнопку ниже.\n"
            f"📋 Продолжая регистрацию, вы принимаете [Условия сервиса](https://vnorku.ru/terms) "
            f"и [Политику обработки персональных данных](https://vnorku.ru/privacy).\n"
            f"Для изменения данных нажми /settings\n"
            f"Для удаления учетной записи нажми /delete\n"
            f"Для управления планом питания нажми /meals",
            reply_markup=reply_markup,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

    async def browse_command(self, update, context):
        """Обработчик команды /browse - Открыть браузер с сохраненными куками"""
        user_id = update.effective_user.id
        db = context.bot_data.get('db_session')
        
        # Логируем входящую команду
        if db:
            log_incoming_message(
                db=db,
                update=update,
                category=IncomingCategory.COMMAND
            )
        
        print(f"🌍 /browse from {user_id}")
        
        try:
            # Получаем список ЛСД с сохраненными куками
            from shared.database import get_async_session
            from shared.database.models import UserSession, LSDConfig
            from sqlalchemy import select
            
            lsd_with_cookies = []
            
            async for db in get_async_session():
                # Находим все сессии пользователя с данными
                result = await db.execute(
                    select(UserSession, LSDConfig).join(
                        LSDConfig, UserSession.lsd_config_id == LSDConfig.id
                    ).where(
                        UserSession.telegram_id == user_id
                    ).where(
                        UserSession.data.isnot(None)  # Есть данные
                    )
                )
                
                sessions = result.all()
                print(f"🔍 Found {len(sessions)} sessions for user {user_id}")
                
                for session, lsd_config in sessions:
                    print(f"🔍 Checking session {session.id} for LSD {lsd_config.name} (id: {lsd_config.id})")
                    print(f"   Session data: {type(session.data)} - {session.data is not None}")
                    
                    # Проверяем что data это не пустой словарь {}
                    if session.data and isinstance(session.data, dict) and len(session.data) > 0:
                        # Проверяем наличие ссылки на файл с cookies (новый формат)
                        cookie_file = session.data.get('cookie_file')
                        # Или старый формат с cookies напрямую
                        cookies = session.data.get('cookies', [])
                        auth_data = session.data.get('auth_data')
                        cookie_count = session.data.get('cookie_count', 0) if cookie_file else len(cookies)

                        print(f"📊 LSD {lsd_config.name}: cookie_file={bool(cookie_file)}, {len(cookies)} inline cookies, auth_data: {bool(auth_data)}")

                        # Если есть куки (файл или inline) или другие данные авторизации
                        if cookie_file or cookies or auth_data:
                            lsd_with_cookies.append({
                                'name': lsd_config.name,
                                'display_name': lsd_config.display_name,
                                'cookies_count': cookie_count,
                                'session_id': session.id
                            })
                            print(f"✅ Added {lsd_config.name} to browse list (cookies_count={cookie_count})")
                        else:
                            print(f"⚠️ Skipped {lsd_config.name} - data exists but no cookies/auth_data")
                    else:
                        print(f"❌ Skipped {lsd_config.name} - empty or invalid session data: {session.data}")
                        
                break  # Выходим из async for
            
            print(f"✅ Final LSD list: {[lsd['name'] for lsd in lsd_with_cookies]}")
            
            if not lsd_with_cookies:
                if db:
                    await send_message_with_log(
                        bot=context.bot,
                        db=db,
                        chat_id=update.effective_chat.id,
                        text="❌ У вас нет сохраненных кук.\n\n"
                             "🔐 Сначала выполните авторизацию через /start",
                        category=OutgoingCategory.SYSTEM_NOTIFICATION,
                        telegram_id=user_id
                    )
                else:
                    await update.message.reply_text(
                        "❌ У вас нет сохраненных кук.\n\n"
                        "🔐 Сначала выполните авторизацию через /start"
                    )
                return
            
            # Создаем инлайн кнопки для ЛСД с куками
            keyboard = []
            for lsd_info in lsd_with_cookies:
                button_text = f"🛒 {lsd_info['display_name']} (🍪 {lsd_info['cookies_count']})"
                callback_data = f"browse_{lsd_info['name']}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
                print(f"🔘 Created button: '{button_text}' -> '{callback_data}'")
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if db:
                await send_message_with_log(
                    bot=context.bot,
                    db=db,
                    chat_id=update.effective_chat.id,
                    text="🌍 Выберите магазин для открытия в браузере:\n\n"
                         "🍪 В скобках указано количество сохраненных кук",
                    category=OutgoingCategory.SYSTEM_NOTIFICATION,
                    telegram_id=user_id,
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    "🌍 Выберите магазин для открытия в браузере:\n\n"
                    "🍪 В скобках указано количество сохраненных кук",
                    reply_markup=reply_markup
                )
            
        except Exception as e:
            print(f"❌ Error in browse_command: {e}")
            import traceback
            traceback.print_exc()
            if db:
                await send_message_with_log(
                    bot=context.bot,
                    db=db,
                    chat_id=update.effective_chat.id,
                    text="❌ Ошибка при получении списка магазинов. Попробуйте позже.",
                    category=OutgoingCategory.ERROR,
                    telegram_id=user_id
                )
            else:
                await update.message.reply_text(
                    "❌ Ошибка при получении списка магазинов. Попробуйте позже."
                )
    
    async def help_command(self, update, context):
        """Обработчик команды /help"""
        db = context.bot_data.get('db_session')
        
        # Логируем входящую команду
        if db:
            log_incoming_message(
                db=db,
                update=update,
                category=IncomingCategory.COMMAND
            )
        
        help_text = (
            "🛒 *Korzinka Bot* - ваш помощник для оптимальных покупок\n\n"
            "*Как пользоваться:*\n"
            "1. В группе напишите `/initiate` для начала регистрации\n"
            "2. Завершите регистрацию в личном чате с ботом\n"
            "3. Отправляйте списки покупок в группу - я найду лучшие цены!\n\n"
            "*Команды:*\n"
            "/start - начать работу\n"
            "/browse - открыть браузер с куками\n"
            "/initiate - регистрация (только в группах)\n"
            "/status - проверить статус аккаунта\n"
            "/help - эта справка"
        )
        
        if db:
            await send_message_with_log(
                bot=context.bot,
                db=db,
                chat_id=update.effective_chat.id,
                text=help_text,
                category=OutgoingCategory.SYSTEM_NOTIFICATION,
                telegram_id=update.effective_user.id,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def status_command(self, update, context):
        """Обработчик команды /status"""
        user_id = update.effective_user.id
        db = context.bot_data.get('db_session')
        
        # Логируем входящую команду
        if db:
            log_incoming_message(
                db=db,
                update=update,
                category=IncomingCategory.COMMAND
            )
        
        try:
            # Получаем данные пользователя
            user_data = await self.get_user_from_database(user_id)
            
            if not user_data or not user_data.get('telegram_id') or not user_data.get('phone'):
                # Пользователь не зарегистрирован или не завершил регистрацию - начинаем с начала
                await self._start_registration(update, context)
                return

            status = user_data.get('status')
            phone = user_data.get('phone')
            address = user_data.get('address')
            
            # Формируем сообщение о статусе
            status_messages = {
                UserStatus.WAITING_CONTACT: "📞 Ожидание телефона",
                UserStatus.WAITING_ADDRESS: "📍 Ожидание адреса",
                UserStatus.WAITING_APARTMENT: "🏠 Ожидание номера квартиры",
                UserStatus.ACTIVE: "✅ Активен",
                UserStatus.BLOCKED: "🚫 Заблокирован"
            }
            
            status_text = status_messages.get(status, f"❓ {status}")
            
            message = f"🔍 **Ваш статус**\n\n"
            message += f"🔸 Статус: {status_text}\n"
            
            if phone:
                message += f"📞 Телефон: {phone[:3]}***{phone[-4:]}\n"
            
            if address:
                # Показываем первые 50 символов адреса
                short_address = address[:50] + "..." if len(address) > 50 else address
                message += f"🏠 Адрес: {short_address}\n"
            
            # Проверяем наличие авторизованных ЛСД
            from shared.database.models import UserSession
            async for db in get_async_session():
                sessions_result = await db.execute(
                    select(UserSession.lsd_config_id)
                    .where(
                        UserSession.telegram_id == user_id,
                        UserSession.data.isnot(None)
                    )
                )
                lsd_sessions = sessions_result.scalars().all()
                
                if lsd_sessions:
                    message += f"\n🔐 Авторизованных ЛСД: {len(lsd_sessions)}"
                else:
                    message += f"\n⚠️ Нет авторизованных ЛСД"
                
                break
            
            # Добавляем подсказки в зависимости от статуса
            if status == UserStatus.WAITING_CONTACT:
                message += "\n\n👉 Отправьте мне свой контакт для продолжения"
            elif status == UserStatus.WAITING_ADDRESS:
                message += "\n\n👉 Отправьте ваш адрес доставки"
            elif status == UserStatus.WAITING_APARTMENT:
                message += "\n\n👉 Отправьте номер квартиры"
            elif status == UserStatus.ACTIVE:
                message += "\n\n👉 Используйте /start для авторизации в ЛСД или отправляйте списки покупок!"
            elif status == UserStatus.BLOCKED:
                message += "\n\n⚠️ Обратитесь к администратору для разблокировки"
            
            if db:
                await send_message_with_log(
                    bot=context.bot,
                    db=db,
                    chat_id=update.effective_chat.id,
                    text=message,
                    category=OutgoingCategory.SYSTEM_NOTIFICATION,
                    telegram_id=user_id,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"❌ Error in status_command: {e}")
            if db:
                await send_message_with_log(
                    bot=context.bot,
                    db=db,
                    chat_id=update.effective_chat.id,
                    text="❌ Ошибка при получении статуса. Попробуйте позже.",
                    category=OutgoingCategory.ERROR,
                    telegram_id=user_id
                )
            else:
                await update.message.reply_text(
                    "❌ Ошибка при получении статуса. Попробуйте позже."
                )
    
    async def settings_command(self, update, context):
        """Обработчик команды /settings - Настройки пользователя"""
        user_id = update.effective_user.id

        print(f"⚙️ /settings from {user_id}")

        # Проверяем, зарегистрирован ли пользователь
        user_data = await self.get_user_from_database(user_id)

        if not user_data or not user_data.get('telegram_id') or not user_data.get('phone'):
            # Пользователь не зарегистрирован или не завершил регистрацию - начинаем с начала
            await self._start_registration(update, context)
            return

        await self._show_settings_menu(update, context, user_data)

    async def _show_settings_menu(self, update, context, user_data=None):
        """Показать меню настроек"""
        user_id = update.effective_user.id

        if not user_data:
            user_data = await self.get_user_from_database(user_id)

        # Создаем кнопки настроек
        keyboard = [
            [InlineKeyboardButton(
                "📍 Изменить адрес доставки",
                callback_data=f"settings_change_address_{user_id}"
            )],
            [InlineKeyboardButton(
                "🚫 Исключения продуктов",
                callback_data=f"excl_menu_{user_id}"
            )]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Показываем текущий адрес если есть
        current_address = user_data.get('address') if user_data else None
        current_apartment = user_data.get('apartment') if user_data else None

        if current_address:
            address_info = current_address
            if current_apartment:
                address_info += f", кв. {current_apartment}"
        else:
            address_info = "Не указан"

        text = (
            f"⚙️ *Настройки*\n\n"
            f"📍 Адрес: {address_info}\n\n"
            f"Выберите действие:"
        )

        # Отправляем или редактируем сообщение
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

    async def delete_command(self, update, context):
        """Обработчик команды /delete - Удаление учетной записи"""
        user_id = update.effective_user.id

        print(f"🗑️ /delete from {user_id}")

        # Проверяем, зарегистрирован ли пользователь
        user_data = await self.get_user_from_database(user_id)

        if not user_data or not user_data.get('telegram_id') or not user_data.get('phone'):
            # Пользователь не зарегистрирован или не завершил регистрацию - начинаем с начала
            await self._start_registration(update, context)
            return

        # Создаем кнопки подтверждения
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, удалить", callback_data=f"delete_confirm_{user_id}"),
                InlineKeyboardButton("❌ Нет, отмена", callback_data=f"delete_cancel_{user_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "⚠️ *Удаление учетной записи*\n\n"
            "Вы уверены, что хотите удалить свою учетную запись?\n\n"
            "❗ Это действие удалит:\n"
            "• Ваши данные (телефон, адрес)\n"
            "• Все сохраненные сессии в службах доставки\n"
            "• Историю заказов\n"
            "• Планы питания\n\n"
            "*Это действие необратимо!*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    async def _handle_settings_callback(self, update, context, query, callback_data):
        """Обработка callback'ов настроек"""
        user_id = query.from_user.id

        if callback_data.startswith("settings_change_address_"):
            # Переводим пользователя в режим ввода адреса
            print(f"📍 User {user_id} changing address")

            # Обновляем статус пользователя на WAITING_ADDRESS (с ретраями)
            try:
                user_client = get_user_service_client()
                response = await user_client.patch(
                    f"/users/{user_id}",
                    json={
                        "status": UserStatus.WAITING_ADDRESS
                    }
                )

                if response and response.status_code == 200:
                    # Обновляем MOCK данные
                    from handlers.registration_mock import MOCK_USERS
                    if user_id in MOCK_USERS:
                        MOCK_USERS[user_id]["status"] = UserStatus.WAITING_ADDRESS
                    else:
                        # Если нет в MOCK - добавляем
                        user_data = await self.get_user_from_database(user_id)
                        if user_data:
                            MOCK_USERS[user_id] = {
                                "telegram_id": user_data['telegram_id'],
                                "username": user_data.get('username'),
                                "first_name": user_data.get('first_name'),
                                "last_name": user_data.get('last_name'),
                                "phone": user_data.get('phone'),
                                "status": UserStatus.WAITING_ADDRESS
                            }

                    await query.answer("Введите новый адрес", show_alert=False)
                    await query.edit_message_text(
                        "📍 Пришлите новый адрес доставки с номером квартиры\n\n"
                        "Пример: Профсоюзная 34, кв 25"
                    )
                    print(f"✅ User {user_id} status changed to WAITING_ADDRESS")
                else:
                    await query.answer("❌ Ошибка обновления статуса", show_alert=True)

            except Exception as e:
                print(f"❌ Error updating status: {e}")
                await query.answer("❌ Ошибка. Попробуйте позже.", show_alert=True)

    async def _handle_delete_callback(self, update, context, query, callback_data):
        """Обработка callback'ов удаления аккаунта"""
        user_id = query.from_user.id

        if callback_data.startswith("delete_confirm_"):
            # Подтверждение удаления
            print(f"🗑️ User {user_id} confirmed deletion")

            await query.answer("Удаление...", show_alert=False)
            await query.edit_message_text("⏳ Удаление учетной записи...")

            try:
                # Удаляем все данные пользователя из БД
                success = await self._delete_user_data(user_id)

                if success:
                    # Очищаем MOCK данные
                    from handlers.registration_mock import MOCK_USERS
                    if user_id in MOCK_USERS:
                        del MOCK_USERS[user_id]

                    await query.edit_message_text(
                        "✅ Ваша учетная запись успешно удалена.\n\n"
                        "Для повторной регистрации используйте команду /start"
                    )
                    print(f"✅ User {user_id} data deleted successfully")
                else:
                    await query.edit_message_text(
                        "❌ Ошибка при удалении данных. Попробуйте позже."
                    )

            except Exception as e:
                print(f"❌ Error deleting user data: {e}")
                await query.edit_message_text(
                    "❌ Ошибка при удалении данных. Попробуйте позже."
                )

        elif callback_data.startswith("delete_cancel_"):
            # Отмена удаления
            print(f"❌ User {user_id} cancelled deletion")
            await query.answer("Отменено", show_alert=False)
            await query.edit_message_text(
                "✅ Удаление отменено.\n\n"
                "Ваши данные сохранены."
            )

    async def _delete_user_data(self, telegram_id: int) -> bool:
        """Удаление всех данных пользователя из БД с учетом foreign keys"""
        try:
            async for db in get_async_session():
                from sqlalchemy import text

                # Получаем user.id по telegram_id
                result = await db.execute(
                    select(User.id).where(User.telegram_id == telegram_id)
                )
                user_record = result.scalar_one_or_none()

                if not user_record:
                    print(f"⚠️ User {telegram_id} not found in database")
                    return True  # Считаем успехом - нечего удалять

                user_db_id = user_record
                print(f"🗑️ Deleting user data for telegram_id={telegram_id}, db_id={user_db_id}")

                # Удаляем в правильном порядке (сначала дочерние таблицы)

                # Meal plan данные
                await db.execute(text(f"DELETE FROM meal_entries WHERE daily_log_id IN (SELECT id FROM meal_daily_logs WHERE user_id = {user_db_id})"))
                await db.execute(text(f"DELETE FROM meal_daily_logs WHERE user_id = {user_db_id}"))
                await db.execute(text(f"DELETE FROM meal_plans WHERE user_id = {user_db_id}"))

                # Заказы и связанные данные
                await db.execute(text(f"""
                    DELETE FROM order_basket_items WHERE basket_id IN (
                        SELECT id FROM order_baskets WHERE order_id IN (
                            SELECT id FROM orders WHERE user_id = {user_db_id}
                        )
                    )
                """))
                await db.execute(text(f"""
                    DELETE FROM order_baskets WHERE order_id IN (
                        SELECT id FROM orders WHERE user_id = {user_db_id}
                    )
                """))
                await db.execute(text(f"""
                    DELETE FROM basket_delivery_costs WHERE combination_id IN (
                        SELECT id FROM basket_combinations WHERE analysis_id IN (
                            SELECT id FROM basket_analyses WHERE order_id IN (
                                SELECT id FROM orders WHERE user_id = {user_db_id}
                            )
                        )
                    )
                """))
                await db.execute(text(f"""
                    DELETE FROM basket_combinations WHERE analysis_id IN (
                        SELECT id FROM basket_analyses WHERE order_id IN (
                            SELECT id FROM orders WHERE user_id = {user_db_id}
                        )
                    )
                """))
                await db.execute(text(f"""
                    DELETE FROM basket_analyses WHERE order_id IN (
                        SELECT id FROM orders WHERE user_id = {user_db_id}
                    )
                """))
                await db.execute(text(f"""
                    DELETE FROM lsd_stocks WHERE order_id IN (
                        SELECT id FROM orders WHERE user_id = {user_db_id}
                    )
                """))
                await db.execute(text(f"""
                    DELETE FROM order_items WHERE order_id IN (
                        SELECT id FROM orders WHERE user_id = {user_db_id}
                    )
                """))
                await db.execute(text(f"DELETE FROM orders WHERE user_id = {user_db_id}"))

                # Промокоды пользователей
                await db.execute(text(f"DELETE FROM promocode_verifications WHERE user_id = {user_db_id}"))

                # Сессии и аккаунты (по telegram_id)
                await db.execute(text(f"DELETE FROM user_sessions WHERE telegram_id = {telegram_id}"))
                await db.execute(text(f"DELETE FROM lsd_accounts WHERE user_id = {user_db_id}"))

                # Сообщения (по telegram_id)
                await db.execute(text(f"DELETE FROM user_messages WHERE telegram_id = {telegram_id}"))

                # Наконец, сам пользователь
                await db.execute(text(f"DELETE FROM users WHERE id = {user_db_id}"))

                await db.commit()
                print(f"✅ All data deleted for user {telegram_id}")
                return True

        except Exception as e:
            print(f"❌ Error in _delete_user_data: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def error_handler(self, update, context):
        """Обработчик ошибок с экспоненциальными ретраями для сетевых ошибок"""
        from utils.retry import is_retryable_error, retry_telegram_operation

        error = context.error
        logger.error(f"Error occurred: {error}", exc_info=error)

        if not update or not update.effective_message:
            return

        # Для сетевых ошибок пытаемся отправить сообщение с ретраями
        if is_retryable_error(error):
            try:
                await retry_telegram_operation(
                    update.effective_message.reply_text,
                    "❌ Сервис перегружен. Мы вернёмся к вам позже, когда можно будет продолжить."
                )
            except TimeoutError:
                # Таймаут 5 минут истёк, логируем и молча завершаем
                logger.error(f"Failed to notify user after 5 min retry timeout: {error}")
            except Exception as e:
                logger.error(f"Failed to send error message after retries: {e}")
        else:
            # Для остальных ошибок отправляем стандартное сообщение
            try:
                await update.effective_message.reply_text(
                    "❌ Произошла ошибка. Попробуйте позже или обратитесь в поддержку."
                )
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")
    
    def _run_api_server(self):
        """Запуск FastAPI сервера в отдельном потоке"""
        try:
            import uvicorn
            config = uvicorn.Config(
                self.api_app,
                host="127.0.0.1",
                port=8001,  # Порт для FastAPI
                log_config=None,
                access_log=False
            )
            server = uvicorn.Server(config)
            
            # Создаем новый event loop для этого потока
            import asyncio
            asyncio.run(server.serve())
        except Exception as e:
            logger.error(f"Error starting API server: {e}")


def main() -> None:
    """Точка входа для запуска бота"""
    # Защита от повторного логирования при перезагрузке
    if not os.environ.get('_TELEGRAM_BOT_STARTED'):
        logger.info("🚀 Starting Korzinka Telegram Bot...")
        os.environ['_TELEGRAM_BOT_STARTED'] = '1'
    else:
        logger.debug("♻️ Telegram Bot reloaded (skipping startup log)")
    
    bot = KorzinkaTelegramBot()

    # Создаем приложение
    bot.application = Application.builder().token(settings.telegram_bot_token).build()

    # Настраиваем обработчики
    bot.setup_handlers()
    
    # Запускаем FastAPI в отдельном потоке
    import threading
    api_thread = threading.Thread(
        target=bot._run_api_server,
        daemon=True
    )
    api_thread.start()
    logger.info("🚀 FastAPI server started in background thread")
    
    logger.info("✅ Telegram bot started successfully")

    # Запускаем бота
    bot.application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
