#!/usr/bin/env python3
"""
Скрипт для запуска всех сервисов Korzinka в режиме разработки
"""

import asyncio
import subprocess
import sys
import os
import signal
import time
from multiprocessing import Process

# Добавляем корневую папку проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.utils.logging import setup_logging, get_logger

logger = setup_logging()


def run_user_service():
    """Запуск User Service"""
    os.chdir("/Users/ss/GenAI/korzinka")
    os.system("./venv/bin/python services/user-service/main.py")


def run_telegram_bot():
    """Запуск Telegram Bot"""
    os.chdir("/Users/ss/GenAI/korzinka")
    os.system("./venv/bin/python services/telegram-bot/main.py")


def run_order_service():
    """Запуск Order Service"""
    os.chdir("/Users/ss/GenAI/korzinka")
    os.system("./venv/bin/python services/order-service/main.py")


def main():
    """Основная функция запуска всех сервисов"""
    logger.info("🚀 Запуск всех сервисов Korzinka...")
    
    processes = []
    
    try:
        # Запускаем User Service
        logger.info("🔧 Запускаем User Service...")
        user_service_process = Process(target=run_user_service)
        user_service_process.start()
        processes.append(("User Service", user_service_process))
        time.sleep(2)  # Даем время на запуск
        
        # Запускаем Order Service  
        logger.info("📦 Запускаем Order Service...")
        order_service_process = Process(target=run_order_service)
        order_service_process.start()
        processes.append(("Order Service", order_service_process))
        time.sleep(2)
        
        # Запускаем Telegram Bot (последним, т.к. зависит от других сервисов)
        logger.info("🤖 Запускаем Telegram Bot...")
        bot_process = Process(target=run_telegram_bot)
        bot_process.start()
        processes.append(("Telegram Bot", bot_process))
        
        logger.info("✅ Все сервисы запущены!")
        logger.info("📋 Активные сервисы:")
        for name, process in processes:
            logger.info(f"  • {name}: PID {process.pid}")
        
        logger.info("\n🎯 Для тестирования:")
        logger.info("  1. Добавьте бота в Telegram группу")
        logger.info("  2. Выполните команду /initiate")
        logger.info("  3. Завершите регистрацию в личном чате с ботом")
        logger.info("  4. Отправляйте списки покупок в группу")
        logger.info("\n⏹️  Для остановки нажмите Ctrl+C")
        
        # Ожидаем сигнал остановки
        try:
            while True:
                # Проверяем, все ли процессы живы
                for name, process in processes:
                    if not process.is_alive():
                        logger.error(f"❌ {name} остановлен неожиданно!")
                        
                time.sleep(5)
                
        except KeyboardInterrupt:
            logger.info("⏹️  Получен сигнал остановки...")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске сервисов: {e}")
    finally:
        # Останавливаем все процессы
        logger.info("🛑 Останавливаем сервисы...")
        for name, process in processes:
            if process.is_alive():
                logger.info(f"  ⏹️  Останавливаем {name}...")
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    logger.warning(f"  ⚠️  Принудительная остановка {name}...")
                    process.kill()
        
        logger.info("✅ Все сервисы остановлены")


if __name__ == "__main__":
    main()
