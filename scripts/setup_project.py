#!/usr/bin/env python3
"""
Скрипт быстрой настройки проекта Korzinka
"""

import os
import sys
import subprocess
import asyncio
from pathlib import Path

# Добавляем корневую папку в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.utils.logging import setup_logging, get_logger

logger = setup_logging()


def run_command(command, description, check=True):
    """Выполнение команды с логированием"""
    logger.info(f"🔄 {description}")
    logger.info(f"Команда: {command}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=check,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info(f"✅ {description} - успешно")
            if result.stdout.strip():
                logger.info(f"Output: {result.stdout.strip()}")
        else:
            logger.error(f"❌ {description} - ошибка")
            if result.stderr.strip():
                logger.error(f"Error: {result.stderr.strip()}")
            
        return result.returncode == 0
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ {description} - ошибка: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка в {description}: {e}")
        return False


def check_prerequisites():
    """Проверка предварительных условий"""
    logger.info("🔍 Проверка предварительных условий...")
    
    # Проверка Python
    if not run_command("python --version", "Проверка Python", check=False):
        logger.error("Python не найден!")
        return False
    
    # Проверка pip
    if not run_command("pip --version", "Проверка pip", check=False):
        logger.error("pip не найден!")
        return False
    
    # Проверка Docker
    if not run_command("docker --version", "Проверка Docker", check=False):
        logger.error("Docker не найден! Установите Docker Desktop.")
        return False
    
    # Проверка docker-compose
    if not run_command("docker-compose --version", "Проверка docker-compose", check=False):
        logger.error("docker-compose не найден!")
        return False
    
    return True


def install_dependencies():
    """Установка зависимостей"""
    logger.info("📦 Установка зависимостей...")
    return run_command(
        "pip install -r requirements.txt",
        "Установка Python пакетов"
    )


def setup_environment():
    """Настройка окружения"""
    logger.info("⚙️ Настройка окружения...")
    
    # Создание .env если не существует
    env_file = Path(".env")
    if not env_file.exists():
        example_file = Path(".env.example")
        if example_file.exists():
            run_command("cp .env.example .env", "Создание .env файла")
            logger.warning("⚠️ Не забудьте заполнить .env файл!")
            logger.info("Запустите: python scripts/generate_keys.py для генерации ключей")
        else:
            logger.error("❌ .env.example не найден!")
            return False
    
    # Создание папки для логов
    logs_dir = Path("logs")
    if not logs_dir.exists():
        logs_dir.mkdir()
        logger.info("✅ Создана папка logs/")
    
    return True


def setup_database():
    """Настройка базы данных"""
    logger.info("🗄️ Настройка базы данных...")
    
    # Запуск PostgreSQL и Redis
    if not run_command(
        "docker-compose up -d postgres redis",
        "Запуск PostgreSQL и Redis"
    ):
        return False
    
    # Ожидание запуска базы данных
    logger.info("⏳ Ожидание запуска базы данных (15 сек)...")
    import time
    time.sleep(15)
    
    # Проверка статуса
    run_command(
        "docker-compose ps",
        "Проверка статуса контейнеров",
        check=False
    )
    
    # Создание таблиц
    if not run_command(
        "python scripts/migrate.py create-tables",
        "Создание таблиц базы данных"
    ):
        return False
    
    # Инициализация ЛСД
    csv_file = Path("egrocery_moscow.csv")
    if csv_file.exists():
        if not run_command(
            "python scripts/init_lsd.py",
            "Инициализация конфигурации ЛСД"
        ):
            return False
    else:
        logger.warning("⚠️ egrocery_moscow.csv не найден. Пропускаем инициализацию ЛСД.")
        logger.info("Скопируйте файл и запустите: python scripts/init_lsd.py")
    
    return True


def verify_setup():
    """Проверка настройки"""
    logger.info("🔍 Проверка настройки...")
    
    # Проверка .env файла
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, 'r') as f:
            env_content = f.read()
            
        required_vars = [
            "DATABASE_URL",
            "REDIS_URL", 
            "SECRET_KEY",
            "ENCRYPTION_KEY"
        ]
        
        missing_vars = []
        for var in required_vars:
            if f"{var}=" not in env_content or f"{var}=your_" in env_content:
                missing_vars.append(var)
        
        if missing_vars:
            logger.warning(f"⚠️ Незаполненные переменные в .env: {', '.join(missing_vars)}")
            return False
        else:
            logger.info("✅ .env файл настроен корректно")
    else:
        logger.error("❌ .env файл не найден!")
        return False
    
    # Проверка подключения к базе данных
    if not run_command(
        'docker exec korzinka-postgres-1 psql -U korzinka_user -d korzinka -c "SELECT 1;"',
        "Проверка подключения к PostgreSQL",
        check=False
    ):
        logger.warning("⚠️ Не удалось подключиться к PostgreSQL")
        return False
    
    logger.info("✅ База данных доступна")
    return True


def main():
    """Основная функция настройки"""
    logger.info("🚀 Начинаем настройку проекта Korzinka...")
    
    # Проверка предварительных условий
    if not check_prerequisites():
        logger.error("❌ Не выполнены предварительные условия!")
        return False
    
    # Установка зависимостей
    if not install_dependencies():
        logger.error("❌ Ошибка установки зависимостей!")
        return False
    
    # Настройка окружения
    if not setup_environment():
        logger.error("❌ Ошибка настройки окружения!")
        return False
    
    # Настройка базы данных
    if not setup_database():
        logger.error("❌ Ошибка настройки базы данных!")
        return False
    
    # Проверка настройки
    if not verify_setup():
        logger.warning("⚠️ Настройка завершена с предупреждениями")
    else:
        logger.info("✅ Настройка завершена успешно!")
    
    logger.info("\n" + "="*50)
    logger.info("🎉 ПРОЕКТ KORZINKA ГОТОВ К ЗАПУСКУ!")
    logger.info("="*50)
    logger.info("📋 Следующие шаги:")
    logger.info("1. Заполните .env файл (TELEGRAM_BOT_TOKEN, API ключи)")
    logger.info("2. Запустите сервисы: python scripts/run_dev.py")
    logger.info("3. Протестируйте бота в Telegram")
    logger.info("\n📖 Подробная инструкция: SETUP.md")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
