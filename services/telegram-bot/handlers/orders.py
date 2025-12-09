import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType
from shared.utils.logging import get_logger
from shared.utils.product_parser import product_parser
from shared.models.base import OrderStatus, NormalizedOrder, Product
from utils.security import TelegramSecurityUtils
import httpx
import json
from typing import List

logger = get_logger(__name__)


class OrderHandler:
    """Обработчик заказов"""
    
    def __init__(self):
        self.order_service_url = "http://localhost:8003"  # URL Order Service
    
    async def handle_order_message(self, update, context):
        """Обработчик сообщений с потенциальными заказами в группе"""
        message_text = update.message.text.strip()
        user = update.effective_user
        telegram_id = user.id
        chat_id = update.effective_chat.id
        
        logger.info(f"📨 Order message from user {telegram_id} in chat {chat_id}")
        
        # Проверяем авторизацию группы
        if not TelegramSecurityUtils.is_authorized_group(chat_id):
            logger.warning(f"❌ Unauthorized group {chat_id}")
            await update.message.reply_text("❌ Эта группа не авторизована для заказов")
            return
        
        # Проверяем, что это заказ по формату
        is_order, cleaned_text = TelegramSecurityUtils.is_order_message(message_text)
        if not is_order:
            # Игнорируем сообщения, которые не начинаются со строки "Заказ"
            logger.info(f"ℹ️ Not an order format from {telegram_id}, ignoring")
            return
        
        # Обновляем message_text на очищенный текст
        message_text = cleaned_text
        logger.info(f"✅ Valid order detected, processing: {len(message_text)} chars")
        
        try:
            # Проверяем, зарегистрирован ли пользователь в базе данных
            user_data = await self._check_user_registration(telegram_id)
            if not user_data:
                await update.message.reply_text(
                    f"❌ {user.first_name}, вы не зарегистрированы.\n"
                    f"Напишите /start боту в личном чате для регистрации."
                )
                return
                
            # Парсим список продуктов
            products = product_parser.normalize_product_list(message_text)
            
            if not products:
                await update.message.reply_text(
                    "❌ Не удалось распознать список продуктов. Попробуйте переформулировать.\n\n"
                    "Используйте формат:\n"
                    "молоко 2 л\n"
                    "хлеб 1 шт\n"
                    "яблоки 1 кг"
                )
                return
            
            logger.info(f"📝 Parsed {len(products)} products for order")
            
            # Создаем нормализованный заказ
            normalized_order = NormalizedOrder(
                products=products,
                original_text=message_text,
                confidence_score=self._calculate_confidence(products)
            )
            
            # Создаем заказ в Order Service
            order_data = await self._create_order(
                user_id=user_data["id"],
                telegram_message_id=update.message.message_id,
                tg_group=str(update.message.chat.id),  # Добавлено: ID группы
                original_list=message_text,
                normalized_order=normalized_order
            )
            
            if order_data:
                await self._send_confirmation(update, context, order_data, normalized_order)
            else:
                await update.message.reply_text("❌ Ошибка создания заказа. Попробуйте позже.")
        
        except Exception as e:
            logger.error(f"❌ Error handling order message: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await update.message.reply_text("❌ Произошла ошибка при обработке заказа.")
    
    async def _check_user_registration(self, telegram_id: int) -> dict:
        """Проверка регистрации пользователя в базе данных"""
        try:
            from shared.database.connection import get_async_session
            from shared.database.models import User as DBUser
            from sqlalchemy import select
            
            async for db in get_async_session():
                result = await db.execute(
                    select(DBUser).where(DBUser.telegram_id == telegram_id)
                )
                user = result.scalar_one_or_none()
                
                if user and user.phone and user.status in ['active', 'registered']:
                    return {
                        "id": user.id,
                        "telegram_id": user.telegram_id,
                        "status": user.status.value,
                        "phone": user.phone
                    }
                break
                
            return None
            
        except Exception as e:
            logger.error(f"❌ Error checking user registration: {e}")
            return None
    
    async def _create_order(self, user_id: int, telegram_message_id: int, 
                           tg_group: str, original_list: str, normalized_order: NormalizedOrder) -> dict:
        """Создание заказа через Order Service"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.order_service_url}/orders/create",
                    json={
                        "user_id": user_id,  # ID пользователя в БД
                        "telegram_message_id": telegram_message_id,
                        "tg_group": tg_group,  # ID группы Telegram
                        "original_list": original_list,
                        "normalized_list": normalized_order.model_dump()
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        logger.info(f"✅ Order created successfully: {result['data']['id']}")
                        return result["data"]
                    else:
                        logger.error(f"❌ Order creation failed: {result.get('message')}")
                else:
                    logger.error(f"❌ Order service error: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"❌ Error creating order: {e}")
            
        return None
    
    async def _send_confirmation(self, update, context, order_data, normalized_order):
        """Отправка подтверждения заказа с нормализованным списком"""
        order_id = order_data["id"]
        user_id = order_data["user_id"]  # telegram_id
        
        # Форматируем нормализованный список
        formatted_list = self._format_normalized_list(normalized_order.products)
        
        confidence_emoji = "🟢" if normalized_order.confidence_score > 0.8 else "🟡" if normalized_order.confidence_score > 0.6 else "🔴"
        
        confirmation_text = (
            f"🛒 **Ваш заказ обработан** {confidence_emoji}\n\n"
            f"{formatted_list}\n\n"
            f"📊 Товаров: {len(normalized_order.products)} | "
            f"Точность: {int(normalized_order.confidence_score * 100)}%\n\n"
            f"Подтвердите заказ для поиска лучших цен:"
        )
        
        # Создаем inline кнопки
        keyboard = [
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"order_confirm_{order_id}"),
                InlineKeyboardButton("❌ Отменить", callback_data=f"order_cancel_{order_id}")
            ],
            [
                InlineKeyboardButton(
                    "✏️ Исправить", 
                    url=f"https://t.me/share/url?url=&text=Заказ%0A{self._encode_for_url(normalized_order.original_text)}"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отвечаем на исходное сообщение
        await update.message.reply_text(
            confirmation_text,
            parse_mode='Markdown',
            reply_markup=reply_markup,
            reply_to_message_id=update.message.message_id
        )
        
        logger.info(f"📤 Confirmation sent for order {order_id}")
    
    async def handle_order_callback(self, update, context):
        """Обработчик callback'ов для заказов"""
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        user_id = query.from_user.id
        
        logger.info(f"🎯 Order callback: {callback_data} from user {user_id}")
        
        try:
            if callback_data.startswith("order_confirm_"):
                order_id = int(callback_data.split("_")[2])
                await self._handle_order_confirmation(query, order_id)
                
            elif callback_data.startswith("order_cancel_"):
                order_id = int(callback_data.split("_")[2])
                await self._handle_order_cancellation(query, order_id)
                
            else:
                await query.edit_message_text("❓ Неизвестная команда")
                
        except Exception as e:
            logger.error(f"❌ Error handling order callback: {e}")
            await query.edit_message_text("❌ Ошибка обработки команды")
    
    async def _handle_order_confirmation(self, query, order_id: int):
        """Обработка подтверждения заказа"""
        logger.info(f"✅ Confirming order {order_id}")
        
        try:
            # Обновляем статус заказа на CONFIRMED
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.order_service_url}/orders/{order_id}/confirm",
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    await query.edit_message_text(
                        f"✅ Заказ #{order_id} подтвержден! Скоро вернусь.",
                        parse_mode='Markdown'
                    )
                    
                    # Запускаем анализ заказа
                    await self._start_order_analysis(order_id)
                    
                else:
                    await query.edit_message_text(
                        f"❌ Ошибка подтверждения заказа: {response.status_code}"
                    )
                    
        except Exception as e:
            logger.error(f"❌ Error confirming order {order_id}: {e}")
            await query.edit_message_text("❌ Ошибка подтверждения заказа")
    
    async def _handle_order_cancellation(self, query, order_id: int):
        """Обработка отмены заказа"""
        logger.info(f"❌ Cancelling order {order_id}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.order_service_url}/orders/{order_id}/cancel",
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    await query.edit_message_text(
                        f"❌ **Заказ #{order_id} отменен**\n\n"
                        f"Вы можете создать новый заказ в любое время!",
                        parse_mode='Markdown'
                    )
                else:
                    await query.edit_message_text(
                        f"❌ Ошибка отмены заказа: {response.status_code}"
                    )
                    
        except Exception as e:
            logger.error(f"❌ Error cancelling order {order_id}: {e}")
            await query.edit_message_text("❌ Ошибка отмены заказа")
    
    async def _start_order_analysis(self, order_id: int):
        """Запуск анализа заказа"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.order_service_url}/orders/{order_id}/analyze",
                    timeout=5.0  # Не ждем результата
                )
                
                if response.status_code in [200, 202]:
                    logger.info(f"🔍 Analysis started for order {order_id}")
                else:
                    logger.error(f"❌ Failed to start analysis for order {order_id}: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"❌ Error starting analysis for order {order_id}: {e}")
    
    def _calculate_confidence(self, products: List[Product]) -> float:
        """Расчет уверенности в парсинге"""
        if not products:
            return 0.0
            
        total_score = 0.0
        for product in products:
            score = 0.5  # Базовая оценка
            
            # Проверяем наличие количества
            if product.quantity > 0:
                score += 0.2
                
            # Проверяем единицы измерения
            if product.unit in ['кг', 'л', 'шт', 'г', 'мл', 'упак']:
                score += 0.2
                
            # Проверяем длину названия
            if 3 <= len(product.name.split()) <= 5:
                score += 0.1
                
            total_score += min(score, 1.0)
            
        return min(total_score / len(products), 1.0)
    
    def _format_normalized_list(self, products: List[Product]) -> str:
        """Форматирование списка продуктов для отображения"""
        formatted_items = []
        for i, product in enumerate(products, 1):
            if product.quantity == 1.0 and product.unit == 'шт':
                formatted_items.append(f"{i}. {product.name}")
            else:
                formatted_items.append(f"{i}. {product.name} — {product.quantity} {product.unit}")
        
        return '\n'.join(formatted_items)
    
    def _encode_for_url(self, text: str) -> str:
        """Кодирование текста для URL"""
        import urllib.parse
        return urllib.parse.quote(text)
