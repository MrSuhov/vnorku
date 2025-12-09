"""
Функция для отправки документов в Telegram через telegram-bot API
"""
import logging
import httpx
import base64
from typing import Optional

logger = logging.getLogger(__name__)


async def send_telegram_document(
    chat_id: str,
    document: bytes,
    filename: str,
    caption: Optional[str] = None,
    reply_to_message_id: Optional[int] = None,
    order_id: Optional[int] = None,
    telegram_bot_token: str = None  # Оставлен для обратной совместимости, но больше не используется
) -> bool:
    """
    Отправка PDF-документа в Telegram через telegram-bot API с автоматическим логированием.

    Все документы отправляются через централизованный telegram-bot сервис,
    который автоматически логирует их в user_messages таблицу.

    Args:
        chat_id: ID чата/группы
        document: Содержимое файла в bytes
        filename: Имя файла
        caption: Подпись к файлу
        reply_to_message_id: ID сообщения для ответа
        order_id: ID заказа для логирования
        telegram_bot_token: Не используется (оставлен для обратной совместимости)

    Returns:
        True если успешно, False при ошибке
    """
    try:
        logger.info(f"📤 Sending document via telegram-bot API to {chat_id}, size: {len(document)} bytes, filename: {filename}")

        # Кодируем документ в base64
        document_base64 = base64.b64encode(document).decode('utf-8')

        async with httpx.AsyncClient() as client:
            # Формируем payload, исключая None значения
            payload = {
                "chat_id": chat_id,
                "document_base64": document_base64,
                "filename": filename
            }

            # Добавляем необязательные параметры только если они не None
            if caption is not None:
                payload["caption"] = caption
            if order_id is not None:
                payload["order_id"] = order_id
            if reply_to_message_id is not None:
                payload["reply_to_message_id"] = reply_to_message_id

            response = await client.post(
                "http://localhost:8001/api/send-document",
                json=payload,
                timeout=60.0  # Увеличенный таймаут для загрузки файла
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    logger.info(f"✅ Document sent successfully to {chat_id} (telegram_message_id={result.get('telegram_message_id')})")
                    return True
                else:
                    logger.error(f"❌ telegram-bot API returned error: {result.get('error')}")
                    return False
            else:
                logger.error(f"❌ telegram-bot API request failed: {response.status_code} - {response.text}")
                return False

    except httpx.TimeoutException as e:
        logger.error(f"❌ Timeout calling telegram-bot API for {chat_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error calling telegram-bot API for {chat_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
