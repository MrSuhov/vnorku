#!/usr/bin/env python3
"""
Самый простой запуск бота для тестирования
"""

import asyncio
import sys
import os

# Добавляем корневую папку проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram.ext import Application, CommandHandler, MessageHandler, filters
from config.settings import settings
from shared.utils.logging import setup_logging, get_logger

logger = setup_logging()


async def start(update, context):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "👋 Привет! Я Korzinka бот!\n\n"
        "🔧 Тестовые команды:\n"
        "/start - это сообщение\n"
        "/test - тестовая команда\n"
        "/initiate - начать регистрацию (работает в группах)\n\n"
        "📝 Отправьте любое сообщение для тестирования."
    )


async def test_command(update, context):
    """Тестовая команда"""
    user = update.effective_user
    chat = update.effective_chat
    
    await update.message.reply_text(
        f"✅ Тест успешен!\n"
        f"👤 Пользователь: {user.first_name} ({user.id})\n"
        f"💬 Чат: {chat.type} ({chat.id})\n"
        f"📍 Заголовок: {chat.title if chat.title else 'Личный чат'}"
    )


async def initiate_command(update, context):
    """Команда /initiate"""
    chat_type = update.effective_chat.type
    user = update.effective_user
    chat = update.effective_chat
    
    if chat_type in ['group', 'supergroup']:
        await update.message.reply_text(
            f"✅ {user.first_name}, команда /initiate получена!\n"
            f"📍 Группа: {chat.title}\n"
            f"🆔 ID группы: {chat.id}\n"
            f"👥 Тип: {chat_type}\n\n"
            f"Теперь напишите боту @{context.bot.username} в личные сообщения!"
        )
        logger.info(f"Initiate command from {user.first_name} in group {chat.title} ({chat.id})")
    else:
        await update.message.reply_text(
            f"❌ Команда /initiate работает только в группах!\n"
            f"Текущий тип чата: {chat_type}\n\n"
            f"Добавьте бота в группу и выполните команду там."
        )


async def handle_message(update, context):
    """Обработчик всех текстовых сообщений"""
    chat_type = update.effective_chat.type
    user = update.effective_user
    text = update.message.text
    
    if chat_type in ['group', 'supergroup']:
        # Сообщение в группе
        logger.info(f"Group message from {user.first_name}: {text[:50]}")
        
        if 'заказ' in text.lower():
            await update.message.reply_text(
                f"🛒 Обнаружено ключевое слово 'заказ'!\n"
                f"👤 От: {user.first_name}\n"
                f"📝 Текст: {text[:100]}{'...' if len(text) > 100 else ''}\n\n"
                f"✅ Бот видит сообщения в группе!"
            )
    else:
        # Личное сообщение
        await update.message.reply_text(
            f"💬 Получил личное сообщение!\n"
            f"👤 От: {user.first_name}\n"
            f"📝 Текст: {text}\n\n"
            f"✅ Связь установлена!"
        )
        logger.info(f"Private message from {user.first_name}: {text}")


async def main():
    """Основная функция"""
    logger.info("🤖 Запускаю простого Telegram бота для тестирования...")
    
    # Создаем приложение
    application = Application.builder().token(settings.telegram_bot_token).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("test", test_command))
    application.add_handler(CommandHandler("initiate", initiate_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Проверяем бота
    try:
        bot_info = await application.bot.get_me()
        logger.info(f"✅ Бот подключен: @{bot_info.username} ({bot_info.first_name})")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к боту: {e}")
        return
    
    # Запускаем
    try:
        logger.info("🚀 Запускаем polling...")
        await application.run_polling()
    except KeyboardInterrupt:
        logger.info("👋 Получен сигнал остановки")
    except Exception as e:
        logger.error(f"❌ Ошибка работы бота: {e}")
    finally:
        logger.info("🛑 Бот остановлен")


if __name__ == "__main__":
    print("🤖 Korzinka Bot - Простая версия для тестирования")
    print("📱 Добавьте бота в группу и протестируйте команды!")
    print("⏹️  Для остановки: Ctrl+C")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
