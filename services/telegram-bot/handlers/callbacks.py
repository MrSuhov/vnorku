import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from shared.utils.logging import get_logger
import httpx
import json

logger = get_logger(__name__)


class CallbackHandler:
    """Обработчик callback queries от inline кнопок"""
    
    def __init__(self):
        self.order_service_url = "http://localhost:8003"
        self.rpa_service_url = "http://localhost:8004"
    
    async def handle_callback(self, update, context):
        """Основной обработчик callback queries"""
        query = update.callback_query
        
        logger.info(f"🎯 CALLBACK RECEIVED: {query.data} from user {query.from_user.id}")
        print(f"🎯 CALLBACK RECEIVED: {query.data} from user {query.from_user.id}")
        
        await query.answer()  # Убираем "loading" индикатор
        
        callback_data = query.data
        user_id = query.from_user.id
        
        try:
            if callback_data.startswith("confirm_order_"):
                await self._handle_order_confirmation(query, callback_data, user_id)
            elif callback_data.startswith("cancel_order_"):
                await self._handle_order_cancellation(query, callback_data, user_id)
            elif callback_data.startswith("auth_"):
                logger.info(f"🔑 Processing LSD auth callback: {callback_data}")
                await self._handle_lsd_auth(query, callback_data, user_id)
            else:
                logger.warning(f"Unknown callback data: {callback_data}")
        
        except Exception as e:
            logger.error(f"Error handling callback {callback_data}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await self._safe_edit_message(query, "❌ Произошла ошибка. Попробуйте позже.")
    
    async def _handle_order_confirmation(self, query, callback_data, user_id):
        """Обработка подтверждения заказа"""
        # Парсим callback_data: confirm_order_{order_id}_{original_user_id}
        parts = callback_data.split("_")
        if len(parts) < 4:
            await self._safe_edit_message(query, "❌ Ошибка данных заказа")
            return

        order_id = int(parts[2])
        original_user_id = int(parts[3])

        # Проверяем, что кнопку нажал тот же пользователь, что создал заказ
        if user_id != original_user_id:
            # Восстанавливаем кнопки для оригинального пользователя
            await self._restore_buttons(query, order_id, original_user_id)
            return

        try:
            async with httpx.AsyncClient() as client:
                # Подтверждаем заказ в Order Service
                response = await client.patch(
                    f"{self.order_service_url}/orders/{order_id}/confirm"
                )

                if response.status_code == 200:
                    # Проверяем наличие персистентных профилей
                    try:
                        profiles_response = await client.get(
                            f"http://localhost:8004/profiles/check/{user_id}"
                        )

                        missing_auth_text = ""
                        if profiles_response.status_code == 200:
                            profiles_data = profiles_response.json()
                            if profiles_data.get('success'):
                                lsds_without_profiles = profiles_data['data'].get('lsds_without_profiles', [])

                                if lsds_without_profiles:
                                    missing_auth_text = (
                                        "\n\n⚠️ <b>Отсутствует авторизация в сервисах:</b>\n"
                                        + "\n".join([f"  • {lsd}" for lsd in lsds_without_profiles])
                                        + "\n\nИспользуйте /auth для авторизации"
                                    )
                    except Exception as profile_error:
                        logger.warning(f"⚠️ Failed to check profiles: {profile_error}")
                        # Продолжаем без проверки профилей

                    confirmation_message = (
                        f"✅ <b>Заказ #{order_id} подтвержден!</b>\n\n"
                        f"🔍 Анализирую цены в службах доставки...\n"
                        f"Результаты будут готовы через несколько минут."
                        f"{missing_auth_text}"
                    )

                    await self._safe_edit_message(
                        query,
                        confirmation_message,
                        parse_mode='HTML'
                    )
                else:
                    await self._safe_edit_message(query, "❌ Ошибка подтверждения заказа")

        except Exception as e:
            logger.error(f"Error confirming order {order_id}: {e}")
            await self._safe_edit_message(query, "❌ Ошибка подтверждения заказа")
    
    async def _handle_order_cancellation(self, query, callback_data, user_id):
        """Обработка отмены заказа"""
        parts = callback_data.split("_")
        if len(parts) < 4:
            await self._safe_edit_message(query, "❌ Ошибка данных заказа")
            return
        
        order_id = int(parts[2])
        original_user_id = int(parts[3])
        
        # Проверяем, что кнопку нажал тот же пользователь
        if user_id != original_user_id:
            await self._restore_buttons(query, order_id, original_user_id)
            return
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.order_service_url}/orders/{order_id}/cancel"
                )
                
                if response.status_code == 200:
                    await self._safe_edit_message(
                        query,
                        "❌ Заказ отменен"
                    )
                else:
                    await self._safe_edit_message(query, "❌ Ошибка отмены заказа")
        
        except Exception as e:
            logger.error(f"Error canceling order {order_id}: {e}")
            await self._safe_edit_message(query, "❌ Ошибка отмены заказа")
    
    async def _handle_lsd_auth(self, query, callback_data, user_id):
        """Обработка авторизации в ЛСД"""
        # Парсим callback_data: auth_{lsd_name}_{telegram_id}
        parts = callback_data.split("_", 2)  # auth, lsd_name, telegram_id
        if len(parts) < 3:
            await self._safe_edit_message(query, "❌ Ошибка данных авторизации")
            return
        
        lsd_name = parts[1]
        telegram_id = int(parts[2])
        
        # Проверяем, что пользователь авторизуется сам
        if user_id != telegram_id:
            return
        
        try:
            lsd_display_name = await self._get_lsd_display_name(lsd_name)
            
            # Формируем новый текст сообщения
            new_message_text = (
                f"🔄 Начинаю авторизацию в {lsd_display_name}...\n"
                f"Это может занять несколько минут.\n\n"
                f"⏳ Ожидание: запуск браузера → генерация QR → ожидание сканирования → сохранение куки"
            )
            
            # Проверяем, отличается ли новое сообщение от текущего
            current_text = query.message.text or ""
            if current_text.strip() != new_message_text.strip():
                await self._safe_edit_message(query, new_message_text)
            else:
                # Если текст не изменился, просто отвечаем на callback без изменения сообщения
                logger.info(f"📝 Message content unchanged, skipping edit for user {telegram_id}")
                await query.answer(f"🔄 Запускаю авторизацию в {lsd_display_name}...", show_alert=True)
            
            # Увеличиваем таймаут для полного цикла авторизации
            async with httpx.AsyncClient(timeout=600.0) as client:  # 10 минут
                response = await client.post(
                    f"{self.rpa_service_url}/auth/start",
                    json={
                        "telegram_id": telegram_id,
                        "lsd_name": lsd_name
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if result.get("success"):
                        data = result.get("data", {})
                        
                        # Проверяем, завершилась ли авторизация полностью
                        if data.get("auth_completed"):
                            # 🎉 Авторизация полностью завершена!
                            await self._safe_edit_message(
                                query,
                                f"✅ **Авторизация в {lsd_display_name} завершена успешно!**\n\n"
                                f"🍪 Куки сохранены в базе данных\n"
                                f"🌐 Финальный URL: `{data.get('final_url', 'N/A')}`\n\n"
                                f"Теперь вы можете создавать заказы через {lsd_display_name}!",
                                parse_mode='Markdown'
                            )
                        elif data.get("requires_qr"):
                            # QR сгенерирован, но авторизация не завершена (таймаут)
                            qr_url = data.get("qr_url")
                            keyboard = [[InlineKeyboardButton("📱 Открыть QR для авторизации", url=qr_url)]]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            
                            await self._safe_edit_message(
                                query,
                                f"⏰ **Таймаут авторизации в {lsd_display_name}**\n\n"
                                f"QR-код сгенерирован, но не был отсканирован в течение 10 минут.\n\n"
                                f"🔄 **Попробуйте еще раз** или обратитесь к администратору.",
                                reply_markup=reply_markup,
                                parse_mode='Markdown'
                            )
                        else:
                            # Неожиданный результат
                            await self._safe_edit_message(
                                query,
                                f"⚠️ Авторизация в {lsd_display_name} завершилась с неопределенным результатом\n\n"
                                f"Сообщение: {data.get('message', 'Нет дополнительной информации')}"
                            )
                    else:
                        # Ошибка авторизации
                        error_msg = result.get("error", "Неизвестная ошибка")
                        await self._safe_edit_message(
                            query,
                            f"❌ **Ошибка авторизации в {lsd_display_name}**\n\n"
                            f"Причина: {error_msg}\n\n"
                            f"🔄 Попробуйте позже или обратитесь к администратору."
                        )
                else:
                    await self._safe_edit_message(
                        query,
                        f"❌ Ошибка сервиса авторизации (HTTP {response.status_code})\n\n"
                        f"Попробуйте позже или обратитесь к администратору."
                    )
        
        except httpx.TimeoutException:
            logger.error(f"Timeout in LSD auth {lsd_name} for user {telegram_id}")
            await self._safe_edit_message(
                query,
                f"⏰ **Таймаут авторизации в {lsd_display_name}**\n\n"
                f"Авторизация заняла более 10 минут.\n"
                f"🔄 Попробуйте еще раз позже."
            )
        except Exception as e:
            logger.error(f"Error in LSD auth {lsd_name}: {e}")
            # Проверяем, не является ли это ошибкой Telegram о неизмененном сообщении
            if "Message is not modified" in str(e):
                logger.info(f"📝 Telegram message not modified error - RPA process may still be running")
                await query.answer(f"🔄 RPA процесс запущен для {lsd_display_name}", show_alert=True)
            else:
                await self._safe_edit_message(
                    query,
                    f"❌ **Критическая ошибка авторизации**\n\n"
                    f"Детали: {str(e)}\n\n"
                    f"🔧 Обратитесь к администратору."
                )
    
    async def _restore_buttons(self, query, order_id, original_user_id):
        """Восстановление кнопок для оригинального пользователя"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_order_{order_id}_{original_user_id}"),
                InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_order_{order_id}_{original_user_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_reply_markup(reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Error restoring buttons: {e}")
    
    async def _safe_edit_message(self, query, new_text: str, **kwargs):
        """Безопасное редактирование сообщения с проверкой на изменения"""
        try:
            current_text = query.message.text or ""
            current_markup = query.message.reply_markup
            new_markup = kwargs.get('reply_markup')
            
            # Проверяем, изменился ли текст или markup
            text_changed = current_text.strip() != new_text.strip()
            markup_changed = str(current_markup) != str(new_markup) if new_markup else current_markup is not None
            
            if text_changed or markup_changed:
                await query.edit_message_text(new_text, **kwargs)
                logger.info(f"📝 Message edited (text_changed={text_changed}, markup_changed={markup_changed})")
            else:
                logger.info(f"📝 Message content and markup unchanged, skipping edit")
                # Просто отвечаем на callback без изменения сообщения
                await query.answer("✅ Обработано", show_alert=False)
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.info(f"📝 Telegram confirmed message not modified - this is expected")
                await query.answer("✅ Обработано", show_alert=False)
            else:
                logger.error(f"Error editing message: {e}")
                # Не пробрасываем исключение дальше, чтобы RPA процесс продолжал работать
                await query.answer("⚠️ Ошибка обновления сообщения", show_alert=True)
    
    async def _get_lsd_display_name(self, lsd_name: str) -> str:
        """Получение отображаемого имени ЛСД из базы данных"""
        try:
            from shared.utils import LSDService
            lsd_config = await LSDService.get_lsd_by_name(lsd_name)
            return lsd_config.display_name if lsd_config else lsd_name
        except Exception as e:
            logger.error(f"Error getting LSD display name for {lsd_name}: {e}")
            return lsd_name
