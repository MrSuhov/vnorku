"""
Утилиты для логирования сообщений Telegram в базу данных.

Модуль предоставляет функции для сохранения всех значимых входящих и исходящих
сообщений в таблицу user_messages для аудита, аналитики и отладки.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from telegram import Update, Message
from telegram.constants import ChatType

from shared.database.models import UserMessage

logger = logging.getLogger(__name__)


# Категории входящих сообщений
class IncomingCategory:
    COMMAND = "command"  # /start, /initiate, /help
    ORDER = "order"  # Список продуктов в группе
    REGISTRATION = "registration"  # Процесс регистрации
    SMS_CODE = "sms_code"  # SMS коды для авторизации
    ADDRESS = "address"  # Адрес доставки
    CONTACT = "contact"  # Контакт (телефон)
    CALLBACK = "callback"  # Нажатие inline-кнопки
    TEXT = "text"  # Обычные текстовые сообщения
    OTHER = "other"  # Прочие сообщения


# Категории исходящих сообщений
class OutgoingCategory:
    ORDER_CONFIRMATION = "order_confirmation"  # Подтверждение заказа
    ORDER_ANALYSIS = "order_analysis"  # Процесс анализа
    ORDER_RESULT = "order_result"  # Результат анализа заказа
    SYSTEM_NOTIFICATION = "system_notification"  # Системные уведомления
    ERROR = "error"  # Сообщения об ошибках
    REGISTRATION = "registration"  # Сообщения регистрации
    OTHER = "other"  # Прочие сообщения


def get_chat_type(chat_id) -> str:
    """
    Определяет тип чата на основе chat_id.

    Args:
        chat_id: ID чата в Telegram (int или str)

    Returns:
        'private', 'group' или 'supergroup'
    """
    # Преобразуем в int для сравнения
    try:
        chat_id_int = int(chat_id)
    except (ValueError, TypeError):
        return "private"  # По умолчанию

    if chat_id_int > 0:
        return "private"
    elif chat_id_int > -1000000000000:
        return "group"
    else:
        return "supergroup"


def get_user_id_from_update(update: Update) -> Optional[int]:
    """
    Извлекает user_id (из БД) из Telegram update.
    Пока возвращает None, так как требуется запрос к БД.
    
    Args:
        update: Telegram Update объект
        
    Returns:
        user_id из БД или None
    """
    # TODO: Добавить запрос к БД для получения user_id по telegram_id
    # Для этого потребуется передавать session в функцию
    return None


def categorize_incoming_message(update: Update) -> str:
    """
    Автоматическая категоризация входящего сообщения.
    
    Args:
        update: Telegram Update объект
        
    Returns:
        Категория сообщения из IncomingCategory
    """
    # Callback query
    if update.callback_query:
        return IncomingCategory.CALLBACK
    
    message = update.effective_message
    if not message:
        return IncomingCategory.OTHER
    
    # Команды
    if message.text and message.text.startswith('/'):
        return IncomingCategory.COMMAND
    
    # Контакт (телефон)
    if message.contact:
        return IncomingCategory.CONTACT
    
    # Адрес или координаты
    if message.location or (message.text and ('адрес' in message.text.lower() or 'улица' in message.text.lower())):
        return IncomingCategory.ADDRESS
    
    # SMS код (4 цифры)
    if message.text and message.text.isdigit() and len(message.text) == 4:
        return IncomingCategory.SMS_CODE
    
    # Список продуктов (эвристика: содержит несколько строк или запятые)
    if message.text and ('\n' in message.text or message.text.count(',') >= 2):
        return IncomingCategory.ORDER
    
    return IncomingCategory.OTHER


def log_incoming_message(
    db: Session,
    update: Update,
    category: Optional[str] = None,
    is_significant: bool = True,
    user_id: Optional[int] = None,
    order_id: Optional[int] = None
) -> Optional[UserMessage]:
    """
    Логирует входящее сообщение от пользователя.
    
    Args:
        db: SQLAlchemy сессия
        update: Telegram Update объект
        category: Категория сообщения (автоматически определяется, если не указана)
        is_significant: Флаг значимости сообщения
        user_id: ID пользователя в БД (опционально)
        order_id: ID заказа, если сообщение связано с заказом
        
    Returns:
        Созданный объект UserMessage или None при ошибке
    """
    try:
        message = update.effective_message
        if not message:
            # Может быть callback_query без сообщения
            if update.callback_query:
                message = update.callback_query.message
                message_text = f"[CALLBACK] {update.callback_query.data}"
            else:
                logger.warning("No message in update, skipping log")
                return None
        else:
            # Формируем текст сообщения
            if message.text:
                message_text = message.text
            elif message.contact:
                message_text = f"[CONTACT] {message.contact.phone_number}"
            elif message.location:
                message_text = f"[LOCATION] lat={message.location.latitude}, lon={message.location.longitude}"
            else:
                message_text = "[MEDIA OR OTHER]"
        
        # Автоматическая категоризация, если не указана
        if category is None:
            category = categorize_incoming_message(update)
        
        # Определяем тип чата
        chat_type = "private"
        if message.chat.type == ChatType.GROUP:
            chat_type = "group"
        elif message.chat.type == ChatType.SUPERGROUP:
            chat_type = "supergroup"
        
        # Создаём запись
        user_message = UserMessage(
            user_id=user_id,
            order_id=order_id,
            chat_id=message.chat.id,
            telegram_message_id=message.message_id,
            reply_to_telegram_message_id=message.reply_to_message.message_id if message.reply_to_message else None,
            message_direction="incoming",
            chat_type=chat_type,
            message_category=category,
            message_text=message_text,
            raw_update=update.to_dict() if hasattr(update, 'to_dict') else None,
            is_significant=is_significant
        )
        
        db.add(user_message)
        db.commit()
        db.refresh(user_message)
        
        logger.debug(
            f"Logged incoming message: chat_id={message.chat.id}, "
            f"category={category}, text_preview={message_text[:50]}"
        )
        
        return user_message
        
    except Exception as e:
        logger.error(f"Failed to log incoming message: {e}", exc_info=True)
        db.rollback()
        return None


async def log_outgoing_message(
    db: "AsyncSession",
    chat_id: int,
    message_text: str,
    category: str,
    user_id: Optional[int] = None,
    order_id: Optional[int] = None,
    telegram_message_id: Optional[int] = None,
    reply_to_telegram_message_id: Optional[int] = None,
    parse_mode: Optional[str] = None,
    disable_web_page_preview: Optional[bool] = None,
    response_status: Optional[int] = None,
    response_body: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    is_significant: bool = True
) -> Optional[UserMessage]:
    """
    Логирует исходящее сообщение от бота.

    Args:
        db: SQLAlchemy async сессия
        chat_id: ID чата в Telegram
        message_text: Текст сообщения
        category: Категория из OutgoingCategory
        user_id: ID пользователя в БД (опционально)
        order_id: ID заказа, если сообщение связано с заказом
        telegram_message_id: ID отправленного сообщения
        reply_to_telegram_message_id: ID сообщения, на которое отвечаем
        parse_mode: Режим парсинга (HTML, Markdown)
        disable_web_page_preview: Отключить превью ссылок
        response_status: HTTP статус ответа от Telegram API
        response_body: Полный ответ от Telegram API
        error_message: Сообщение об ошибке, если отправка не удалась
        is_significant: Флаг значимости сообщения

    Returns:
        Созданный объект UserMessage или None при ошибке
    """
    try:
        # Определяем тип чата
        chat_type = get_chat_type(chat_id)

        # Создаём запись - конвертируем chat_id в строку
        user_message = UserMessage(
            user_id=user_id,
            order_id=order_id,
            chat_id=str(chat_id),  # Конвертируем в строку для VARCHAR колонки
            telegram_message_id=telegram_message_id,
            reply_to_telegram_message_id=reply_to_telegram_message_id,
            message_direction="outgoing",
            chat_type=chat_type,
            message_category=category,
            message_text=message_text,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
            response_status=response_status,
            response_body=response_body,
            error_message=error_message,
            is_significant=is_significant
        )

        db.add(user_message)
        logger.info("⏱️  About to call db.flush()")
        await db.flush()  # Flush чтобы получить ID, но НЕ commit
        logger.info(f"✅ db.flush() completed, user_message.id={user_message.id}")

        logger.debug(
            f"Logged outgoing message: chat_id={chat_id}, "
            f"category={category}, text_preview={message_text[:50]}"
        )

        return user_message

    except Exception as e:
        logger.error(f"Failed to log outgoing message: {e}", exc_info=True)
        await db.rollback()
        return None


async def log_telegram_api_response(
    db: "AsyncSession",
    user_message_id: int,
    sent_message: Message,
    response_status: int = 200
) -> bool:
    """
    Обновляет запись сообщения данными от Telegram API после отправки.

    Args:
        db: SQLAlchemy async сессия
        user_message_id: ID записи UserMessage
        sent_message: Объект отправленного сообщения от Telegram
        response_status: HTTP статус (обычно 200)

    Returns:
        True при успехе, False при ошибке
    """
    try:
        from sqlalchemy import select

        result = await db.execute(
            select(UserMessage).filter(UserMessage.id == user_message_id)
        )
        user_message = result.scalar_one_or_none()

        if not user_message:
            logger.warning(f"UserMessage with id={user_message_id} not found")
            return False

        user_message.telegram_message_id = sent_message.message_id
        user_message.response_status = response_status
        user_message.response_body = sent_message.to_dict() if hasattr(sent_message, 'to_dict') else None

        await db.commit()

        logger.debug(f"Updated UserMessage {user_message_id} with telegram_message_id={sent_message.message_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to update UserMessage with API response: {e}", exc_info=True)
        await db.rollback()
        return False
