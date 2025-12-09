"""
Обработчик пользовательского ввода для RPA (SMS коды и т.д.)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from shared.utils.logging import get_logger
import httpx
import asyncio
from datetime import datetime, timedelta

logger = get_logger(__name__)


class UserInputHandler:
    """Обработчик запросов пользовательского ввода от RPA сервиса"""
    
    def __init__(self):
        self.rpa_service_url = "http://localhost:8004"
        
        # Хранение ожидающих ввод пользователей
        # {telegram_id: {session_id, input_type, requested_at, message}}
        self.pending_inputs = {}
        
        # Таймаут для ожидания ввода (5 минут)
        self.input_timeout = 300  # секунд
    
    async def request_user_input(self, bot, telegram_id: int, message: str, session_id: str, input_type: str):
        """Запрос пользовательского ввода через Telegram"""
        try:
            logger.info(f"📲 Requesting {input_type} from user {telegram_id}")
            
            # Сохраняем информацию о запросе
            self.pending_inputs[telegram_id] = {
                'session_id': session_id,
                'input_type': input_type,
                'message': message,
                'requested_at': datetime.now()
            }
            
            # Формируем сообщение для пользователя
            if input_type == 'sms_code':
                user_message = f"Код из смс?\n❌ Для отмены отправьте: /cancel"
            else:
                user_message = f"💬 Отправьте {input_type} одним сообщением\n"
                user_message += "⏱️ У вас есть 5 минут\n"
                user_message += "❌ Для отмены отправьте: /cancel"
            
            # Отправляем сообщение пользователю
            await bot.send_message(
                chat_id=telegram_id,
                text=user_message,
                parse_mode='Markdown'
            )
            
            # Запускаем таймер для автоматической очистки
            asyncio.create_task(self._cleanup_expired_request(telegram_id))
            
            logger.info(f"✅ User input request sent to user {telegram_id}")
            
        except Exception as e:
            logger.error(f"Error requesting user input: {e}")
            
            # Очищаем запрос при ошибке
            if telegram_id in self.pending_inputs:
                del self.pending_inputs[telegram_id]
    
    async def handle_user_input(self, update, context):
        """Обработка ввода пользователя"""
        user_id = update.effective_user.id
        user_input = update.message.text.strip()
        
        try:
            logger.info(f"📝 STARTING handle_user_input for user {user_id}")
            
            if user_id not in self.pending_inputs:
                logger.warning(f"Received unexpected input from user {user_id}: {user_input}")
                return
                
            request_info = self.pending_inputs[user_id]
            session_id = request_info['session_id']
            input_type = request_info['input_type']
            
            logger.info(f"📝 Processing {input_type} input from user {user_id}: {user_input}")
            
            # Проверяем команду отмены
            if user_input.lower() in ['/cancel', 'отмена', 'cancel']:
                logger.info(f"📝 User requested cancellation")
                await self._handle_cancel_input(update, user_id)
                return
            
            # Убеждаемся, что пользователь есть в MOCK_USERS для правильной обработки
            logger.info(f"📝 Step 1: Ensuring user in MOCK_USERS")
            try:
                await self._ensure_user_in_mock_users(user_id, update)
                logger.info(f"✅ Step 1 completed: User ensured in MOCK_USERS")
            except Exception as e:
                logger.error(f"❌ Step 1 FAILED: Error ensuring user in MOCK_USERS: {e}")
                # Продолжаем дальше, это не критично
            
            # Отправляем подтверждение пользователю
            logger.info(f"📝 Step 2: Sending confirmation message")
            try:
                await update.message.reply_text(
                    "⏳ Обрабатываю ваш код...\nПожалуйста, подождите."
                )
                logger.info(f"✅ Step 2 completed: Confirmation sent")
            except Exception as e:
                logger.error(f"❌ Step 2 FAILED: Error sending confirmation: {e}")
            
            # Отправляем ввод в RPA сервис
            logger.info(f"📝 Step 3: Sending input to RPA service")
            try:
                success = await self._send_input_to_rpa(session_id, user_input, user_id)
                logger.info(f"✅ Step 3 completed: RPA service returned success={success}")
                
                if success:
                    logger.info(f"📝 Step 4: Sending success message")
                    try:
                        await update.message.reply_text(
                            "✅ Код принят! Завершаю авторизацию..."
                        )
                        logger.info(f"✅ Step 4 completed: Success message sent")
                    except Exception as e:
                        logger.error(f"❌ Step 4 FAILED: Error sending success message: {e}")
                else:
                    logger.info(f"📝 Step 4b: Sending error message")
                    try:
                        await update.message.reply_text(
                            "❌ Ошибка обработки кода. Попробуйте еще раз или обратитесь к администратору."
                        )
                        logger.info(f"✅ Step 4b completed: Error message sent")
                    except Exception as e:
                        logger.error(f"❌ Step 4b FAILED: Error sending error message: {e}")
                
            except Exception as e:
                logger.error(f"❌ Step 3 FAILED: Error with RPA service: {e}")
                # Отправляем сообщение об ошибке
                try:
                    await update.message.reply_text(
                        "❌ Ошибка обработки кода. Попробуйте еще раз."
                    )
                except:
                    pass  # Не критично
            
            # Очищаем запрос
            logger.info(f"📝 Step 5: Cleaning up request")
            try:
                if user_id in self.pending_inputs:
                    del self.pending_inputs[user_id]
                    logger.info(f"✅ Step 5 completed: Request cleaned up")
                else:
                    logger.warning(f"⚠️ Step 5: Request already cleaned up")
            except Exception as e:
                logger.error(f"❌ Step 5 FAILED: Error cleaning up request: {e}")
            
            logger.info(f"📝 COMPLETED handle_user_input for user {user_id}")
            
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR in handle_user_input: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            try:
                await update.message.reply_text(
                    "❌ Произошла ошибка при обработке вашего ввода."
                )
            except:
                pass  # Не критично
    
    async def _ensure_user_in_mock_users(self, user_id: int, update):
        """Убеждаемся, что пользователь есть в MOCK_USERS"""
        try:
            from handlers.registration_mock import MOCK_USERS
            from shared.models.base import UserStatus
            
            if user_id not in MOCK_USERS:
                logger.info(f"🔄 Adding user {user_id} to MOCK_USERS for SMS processing")
                
                # Добавляем пользователя в MOCK_USERS с базовыми данными
                MOCK_USERS[user_id] = {
                    "telegram_id": user_id,
                    "username": update.effective_user.username,
                    "first_name": update.effective_user.first_name,
                    "last_name": update.effective_user.last_name,
                    "phone": None,  # Будет обновлено из базы
                    "status": UserStatus.ACTIVE
                }
            
        except Exception as e:
            logger.error(f"Error ensuring user in MOCK_USERS: {e}")
    
    async def _send_input_to_rpa(self, session_id: str, user_input: str, telegram_id: int) -> bool:
        """Сохранение SMS кода в БД для поллинга RPA сервисом"""
        try:
            logger.info(f"📤 Saving SMS code '{user_input}' to database for telegram_id={telegram_id}")

            # Сохраняем SMS код в БД (RPA сервис будет его читать через поллинг)
            from shared.database import get_async_session
            from shared.database.models import User
            from sqlalchemy import update

            async for db in get_async_session():
                try:
                    # Обновляем поле sms_code в таблице users
                    result = await db.execute(
                        update(User)
                        .where(User.telegram_id == telegram_id)
                        .values(sms_code=user_input)
                    )
                    await db.commit()

                    rows_affected = result.rowcount
                    logger.info(f"✅ SMS code saved to database: {rows_affected} row(s) updated")

                    return rows_affected > 0

                except Exception as db_error:
                    logger.error(f"❌ Database error saving SMS code: {db_error}")
                    await db.rollback()
                    return False

        except Exception as e:
            logger.error(f"💥 Error saving SMS code to database: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    async def _handle_cancel_input(self, update, user_id: int):
        """Обработка отмены ввода пользователем"""
        try:
            logger.info(f"🚫 User {user_id} cancelled input")
            
            # Очищаем запрос
            if user_id in self.pending_inputs:
                del self.pending_inputs[user_id]
            
            await update.message.reply_text(
                "❌ Ввод отменен.\n\n"
                "Для повторной авторизации выберите ЛСД в меню."
            )
            
        except Exception as e:
            logger.error(f"Error handling cancel input: {e}")
    
    async def _cleanup_expired_request(self, telegram_id: int):
        """Автоматическая очистка просроченного запроса"""
        try:
            # Ждем таймаут
            await asyncio.sleep(self.input_timeout)
            
            # Проверяем, есть ли еще запрос
            if telegram_id in self.pending_inputs:
                request_info = self.pending_inputs[telegram_id]
                
                # Проверяем, действительно ли запрос просрочен
                elapsed = datetime.now() - request_info['requested_at']
                if elapsed.total_seconds() >= self.input_timeout:
                    logger.info(f"⏰ Cleaning up expired input request for user {telegram_id}")
                    
                    # Очищаем запрос
                    del self.pending_inputs[telegram_id]
                    
                    # TODO: Уведомить пользователя о таймауте (нужен доступ к bot)
                    
        except Exception as e:
            logger.error(f"Error in cleanup expired request: {e}")
    
    async def is_waiting_for_input(self, telegram_id: int) -> bool:
        """Проверка, ожидает ли пользователь ввод"""
        if telegram_id not in self.pending_inputs:
            return False
        
        # Проверяем, не просрочен ли запрос
        request_info = self.pending_inputs[telegram_id]
        elapsed = datetime.now() - request_info['requested_at']
        
        if elapsed.total_seconds() >= self.input_timeout:
            # Запрос просрочен, очищаем
            del self.pending_inputs[telegram_id]
            return False
        
        return True
    
    def get_pending_input_info(self, telegram_id: int) -> dict:
        """Получить информацию о pending запросе"""
        return self.pending_inputs.get(telegram_id, {})
