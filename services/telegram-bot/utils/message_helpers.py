"""
Утилиты для работы с сообщениями в Telegram боте с автоматическим логированием.
"""

import logging
from typing import Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from utils.retry import retry_telegram_operation, is_retryable_error

logger = logging.getLogger(__name__)


async def get_user_id_from_telegram(db: AsyncSession, telegram_id: int) -> Optional[int]:
    """
    Получает user_id из БД по telegram_id.

    Args:
        db: SQLAlchemy async сессия
        telegram_id: Telegram ID пользователя

    Returns:
        user_id из БД или None если не найден
    """
    try:
        from shared.database.models import User

        result = await db.execute(
            select(User.id).filter(User.telegram_id == telegram_id)
        )
        # Result.scalars() returns an iterator, we need to consume it
        user_ids = list(result.scalars())
        return user_ids[0] if user_ids else None

    except Exception as e:
        logger.error(f"Error getting user_id from telegram_id {telegram_id}: {e}")
        return None


async def send_message_with_log(
    bot,
    db: AsyncSession,
    chat_id: Union[int, str],
    text: str,
    category: str,
    telegram_id: Optional[int] = None,
    order_id: Optional[int] = None,
    **kwargs
):
    """
    Отправляет сообщение с автоматическим логированием.

    Args:
        bot: Telegram Bot instance
        db: SQLAlchemy async сессия
        chat_id: ID чата для отправки (int или str для групп)
        text: Текст сообщения
        category: Категория из OutgoingCategory
        telegram_id: Telegram ID пользователя (для получения user_id)
        order_id: ID заказа, если применимо
        **kwargs: Дополнительные аргументы для send_message

    Returns:
        Отправленное сообщение или None при ошибке
    """
    from shared.utils.message_logger import (
        log_outgoing_message,
        log_telegram_api_response
    )

    # Получаем user_id если передан telegram_id
    # ВРЕМЕННО ОТКЛЮЧЕНО из-за проблем с async SQLAlchemy
    user_id = None
    # if telegram_id:
    #     user_id = await get_user_id_from_telegram(db, telegram_id)

    # Логируем намерение отправить
    logger.info(f"📝 About to call log_outgoing_message")
    user_msg_record = await log_outgoing_message(
        db=db,
        chat_id=str(chat_id),  # Конвертируем в строку для VARCHAR колонки
        message_text=text,
        category=category,
        user_id=user_id,
        order_id=order_id,
        parse_mode=kwargs.get('parse_mode'),
        disable_web_page_preview=kwargs.get('disable_web_page_preview'),
        reply_to_telegram_message_id=kwargs.get('reply_to_message_id')  # Маппинг Telegram API -> DB поле
    )
    logger.info(f"✅ log_outgoing_message returned, record_id={user_msg_record.id if user_msg_record else None}")

    # КРИТИЧНО: Коммитим ДО отправки в Telegram чтобы не держать транзакцию открытую
    logger.info(f"🔄 Committing transaction BEFORE sending to Telegram")
    await db.commit()
    logger.info(f"✅ Transaction committed, now sending to Telegram")

    try:
        # Отправляем сообщение с ретраями для сетевых ошибок
        sent_message = await retry_telegram_operation(
            bot.send_message,
            chat_id=chat_id,
            text=text,
            **kwargs
        )

        # Обновляем запись с данными от Telegram API
        if user_msg_record:
            await log_telegram_api_response(
                db=db,
                user_message_id=user_msg_record.id,
                sent_message=sent_message
            )

        logger.debug(f"✅ Message sent and logged: chat_id={chat_id}, category={category}")
        return sent_message

    except TimeoutError as e:
        # Таймаут 5 минут истёк
        logger.error(f"❌ Message send timeout after 5 min: {e}")
        if user_msg_record:
            user_msg_record.error_message = f"Timeout: {e}"
            user_msg_record.response_status = 408
            await db.commit()
        raise

    except Exception as e:
        logger.error(f"❌ Failed to send message: {e}")

        # Логируем ошибку
        if user_msg_record:
            user_msg_record.error_message = str(e)
            user_msg_record.response_status = 400
            await db.commit()

        raise  # Пробрасываем исключение дальше


async def edit_message_with_log(
    query,
    db: AsyncSession,
    new_text: str,
    category: str,
    telegram_id: Optional[int] = None,
    order_id: Optional[int] = None,
    **kwargs
):
    """
    Редактирует сообщение с автоматическим логированием.

    Args:
        query: CallbackQuery объект
        db: SQLAlchemy async сессия
        new_text: Новый текст сообщения
        category: Категория из OutgoingCategory
        telegram_id: Telegram ID пользователя
        order_id: ID заказа
        **kwargs: Дополнительные аргументы для edit_message_text

    Returns:
        True при успехе, False при ошибке
    """
    from shared.utils.message_logger import log_outgoing_message

    # Получаем user_id
    # ВРЕМЕННО ОТКЛЮЧЕНО из-за проблем с async SQLAlchemy
    user_id = None
    # if telegram_id:
    #     user_id = await get_user_id_from_telegram(db, telegram_id)

    # Проверяем, изменился ли текст
    current_text = query.message.text or ""
    current_markup = query.message.reply_markup
    new_markup = kwargs.get('reply_markup')

    text_changed = current_text.strip() != new_text.strip()
    markup_changed = str(current_markup) != str(new_markup) if new_markup else current_markup is not None

    if not text_changed and not markup_changed:
        logger.debug("Message unchanged, skipping edit")
        await query.answer("✅ Обработано", show_alert=False)
        return True

    # Логируем изменение как новое сообщение
    await log_outgoing_message(
        db=db,
        chat_id=str(query.message.chat_id),  # Конвертируем в строку для VARCHAR колонки
        message_text=new_text,
        category=category,
        user_id=user_id,
        order_id=order_id,
        telegram_message_id=query.message.message_id,  # ID редактируемого сообщения
        parse_mode=kwargs.get('parse_mode')
    )

    try:
        await retry_telegram_operation(
            query.edit_message_text,
            new_text,
            **kwargs
        )
        logger.debug(f"✅ Message edited and logged")
        return True

    except TimeoutError as e:
        logger.error(f"❌ Edit message timeout after 5 min: {e}")
        return False

    except Exception as e:
        if "Message is not modified" in str(e):
            logger.debug("Telegram confirmed message not modified")
            try:
                await retry_telegram_operation(
                    query.answer,
                    "✅ Обработано",
                    show_alert=False
                )
            except Exception:
                pass
            return True
        else:
            logger.error(f"❌ Error editing message: {e}")
            try:
                await retry_telegram_operation(
                    query.answer,
                    "⚠️ Ошибка обновления",
                    show_alert=True
                )
            except Exception:
                pass
            return False
