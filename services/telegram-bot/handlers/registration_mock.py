import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType
from shared.utils.logging import get_logger
from shared.models.base import UserStatus
from utils.security import TelegramSecurityUtils
import httpx

logger = get_logger(__name__)

# Глобальные mock данные для совместного использования
MOCK_USERS = {}


class RegistrationHandler:
    """Обработчик регистрации пользователей"""
    
    def __init__(self):
        self.user_service_url = "http://localhost:8002"  # URL User Service
        # Используем глобальные mock данные
        self.mock_users = MOCK_USERS
    
    async def initiate_command(self, update, context):
        """Обработчик команды /initiate в группе (deprecated - используйте прямую регистрацию через /start)"""
        # Проверяем, что команда выполняется в группе
        if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await update.message.reply_text(
                "ℹ️ Команда /initiate больше не требуется!\n\n"
                "Просто напишите мне в личные сообщения и нажмите /start для регистрации."
            )
            return

        # Проверяем авторизацию группы
        chat_id = update.effective_chat.id
        if not TelegramSecurityUtils.is_authorized_group(chat_id):
            await update.message.reply_text("❌ Unauthorized group. Contact admin.")
            logger.debug(f"Unauthorized group message: {chat_id}")
            return

        user = update.effective_user
        telegram_id = user.id

        try:
            print(f"🏗️ Creating user {telegram_id} ({user.first_name}) via /initiate (deprecated)")

            # Сохраняем в БД через user-service
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.user_service_url}/users",
                        json={
                            "telegram_id": telegram_id,
                            "username": user.username,
                            "first_name": user.first_name,
                            "last_name": user.last_name,
                            "status": UserStatus.WAITING_CONTACT
                        },
                        timeout=10.0
                    )
                    if response.status_code in [200, 201]:
                        print(f"✅ User {telegram_id} saved to database")
                    else:
                        print(f"⚠️ DB save returned {response.status_code}, continuing with MOCK")
            except Exception as db_error:
                print(f"⚠️ DB save failed: {db_error}, continuing with MOCK")

            # Добавляем пользователя в mock данные для совместимости
            self.mock_users[telegram_id] = {
                "telegram_id": telegram_id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "status": UserStatus.WAITING_CONTACT,
                "phone": None,
                "created_at": "2025-01-01T00:00:00Z"
            }

            # Создаем inline кнопку для перехода в личный чат
            keyboard = [[
                InlineKeyboardButton(
                    "📱 Завершить регистрацию",
                    url=f"https://t.me/{context.bot.username}"
                )
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"✅ {user.first_name}, вы добавлены в систему!\n\n"
                f"ℹ️ Совет: в будущем можете регистрироваться напрямую через /start в личных сообщениях бота.",
                reply_markup=reply_markup
            )
            print(f"✅ User {telegram_id} registered successfully via /initiate")

        except Exception as e:
            logger.error(f"Error in initiate_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")
    
    async def handle_private_message(self, update, context):
        """Обработчик личных сообщений для регистрации"""
        print(f"📨 HANDLE PRIVATE MESSAGE: {update.effective_user.id}")
        
        user = update.effective_user
        telegram_id = user.id
        
        try:
            # MOCK: Получаем данные пользователя из mock данных вместо HTTP запроса
            user_data = self.mock_users.get(telegram_id)
            
            if not user_data:
                print(f"❌ MOCK: User {telegram_id} not found in mock data")
                await update.message.reply_text(
                    "❌ Пользователь не найден. Сначала выполните команду /initiate в группе."
                )
                return
            
            status = user_data.get("status")
            print(f"🔍 MOCK: User {telegram_id} status='{status}'")
            
            # Обрабатываем состояние пользователя согласно статусной модели
            print(f"📝 MOCK: Processing status '{status}'")
            
            if status == UserStatus.WAITING_CONTACT:
                print("📞 MOCK: Requesting contact (WAITING_CONTACT)")
                await self._request_contact(update, context)
            elif status == UserStatus.WAITING_ADDRESS:
                print("🏠 MOCK: Saving address (WAITING_ADDRESS)")
                address = update.message.text.strip()
                if address:
                    self.mock_users[telegram_id]["address"] = address
                    self.mock_users[telegram_id]["status"] = UserStatus.WAITING_APARTMENT
                    print(f"✅ MOCK: Address saved: {address}")
                    await update.message.reply_text(
                        "✅ Адрес сохранен!\n\n"
                        "🏠 Теперь укажите номер квартиры:"
                    )
                else:
                    await update.message.reply_text("❌ Пожалуйста, введите корректный адрес.")
            elif status == UserStatus.WAITING_APARTMENT:
                print("🚺 MOCK: Saving apartment (WAITING_APARTMENT)")
                apartment = update.message.text.strip()
                if apartment:
                    self.mock_users[telegram_id]["apartment"] = apartment
                    self.mock_users[telegram_id]["status"] = UserStatus.ACTIVE
                    print(f"✅ MOCK: Apartment saved: {apartment}")
                    await update.message.reply_text(
                        "✅ Вы зарегистрированы!\n\n"
                        "После запуска сервиса мы направим вам инструкцию по дальнейшим шагам."
                    )
                else:
                    await update.message.reply_text("❌ Пожалуйста, введите корректный номер квартиры.")
            elif status == UserStatus.ACTIVE:
                print("🔐 MOCK: Starting LSD auth (ACTIVE)")
                await self._start_lsd_authorization(update, context, telegram_id)
            else:
                # Для тестирования - всегда показываем авторизацию ЛСД
                print(f"🧪 MOCK: Defaulting to LSD auth for testing (status={status})")
                await self._start_lsd_authorization(update, context, telegram_id)
        
        except Exception as e:
            logger.error(f"Error in handle_private_message: {e}")
            print(f"❌ ERROR in handle_private_message: {e}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")
    
    async def _request_contact(self, update, context):
        """Запрос контакта у пользователя"""
        from telegram import KeyboardButton, ReplyKeyboardMarkup
        
        print("📞 Requesting contact from user")
        keyboard = [[KeyboardButton("📞 Поделиться контактом", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        await update.message.reply_text(
            "👋 Для продолжения мне нужен ваш номер телефона для авторизации в службах доставки.",
            reply_markup=reply_markup
        )
    
    async def handle_contact(self, update, context):
        """Обработчик получения контакта"""
        if not update.message.contact:
            return
        
        contact = update.message.contact
        user = update.effective_user
        telegram_id = user.id
        
        # Проверяем, что контакт принадлежит отправителю
        if contact.user_id != telegram_id:
            await update.message.reply_text("❌ Пожалуйста, поделитесь своим контактом.")
            return
        
        try:
            print(f"📞 MOCK: Saving contact {contact.phone_number} for user {telegram_id}")
            
            # MOCK: Сохраняем контакт в mock данных вместо HTTP запроса
            if telegram_id in self.mock_users:
                self.mock_users[telegram_id]["phone"] = contact.phone_number
                self.mock_users[telegram_id]["status"] = UserStatus.WAITING_ADDRESS
                
                # Убираем клавиатуру
                from telegram import ReplyKeyboardRemove
                
                await update.message.reply_text(
                    "✅ Номер телефона сохранен!\n\n"
                    "🏠 Теперь введите ваш адрес доставки (например: Москва, ул. Пушкина, д. 10):",
                    reply_markup=ReplyKeyboardRemove()
                )
                
                print(f"✅ MOCK: Contact saved, requesting address")
            else:
                await update.message.reply_text("❌ Ошибка: пользователь не найден.")
        
        except Exception as e:
            logger.error(f"Error saving contact: {e}")
            print(f"❌ ERROR saving contact: {e}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")
    
    async def _start_lsd_authorization(self, update, context, telegram_id):
        """Начало авторизации в ЛСД"""
        try:
            print(f"🔐 Starting LSD authorization for user {telegram_id}")
            
            # MOCK: Используем фиксированные ЛСД вместо запроса к БД
            mvp_lsds = [
                ("samokat", "Самокат"),
                ("yandex", "Яндекс Лавка"), 
                ("vkusvill", "ВкусВилл")
            ]
            
            # Создаем кнопки для каждого MVP ЛСД
            keyboard = []
            for name, display_name in mvp_lsds:
                emoji = "🛒" if name == "samokat" else "🍎" if name == "yandex" else "📦"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{emoji} {display_name}", 
                        callback_data=f"auth_{name}_{telegram_id}"
                    )
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            print(f"🔍 Sending {len(keyboard)} LSD buttons to user {telegram_id}")
            for i, row in enumerate(keyboard):
                for j, button in enumerate(row):
                    print(f"🔘 Button [{i}][{j}]: {button.text} -> {button.callback_data}")
            
            await update.message.reply_text(
                "🔐 Выберите службу доставки для авторизации:",
                reply_markup=reply_markup
            )
            print(f"✅ LSD authorization buttons sent to {telegram_id}")
            
        except Exception as e:
            logger.error(f"Error starting LSD authorization: {e}")
            print(f"❌ ERROR starting LSD authorization: {e}")
            await update.message.reply_text(
                "❌ Ошибка при загрузке служб доставки. Попробуйте позже."
            )
