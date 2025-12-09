#!/usr/bin/env python3
"""
Простая утилита для запуска Config Grabber Service

Использование:
    ./grabber.py - интерактивный режим
    ./grabber.py <url> - прямой запуск для URL
    ./grabber.py demo <url> - демо режим без браузера
"""
import asyncio
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent
sys.path.append(str(root_dir))

from services.config_grabber.generator import ConfigGrabber


def print_usage():
    print("📖 Использование Config Grabber Service:")
    print()
    print("🔧 Команды:")
    print("  ./grabber.py                    - интерактивный выбор ЛСД")
    print("  ./grabber.py <url>              - прямой запуск для URL")
    print("  ./grabber.py demo <url>         - демо режим (без браузера)")
    print()
    print("📝 Примеры:")
    print("  ./grabber.py https://5ka.ru")
    print("  ./grabber.py demo https://magnit.ru")
    print("  ./grabber.py")
    print()
    print("📁 SMS коды через: touch /tmp/config_grabber/sms_codes/1234")


async def interactive_mode():
    """Интерактивный режим с выбором ЛСД"""
    from services.config_grabber.test_grabber import get_lsd_without_rpa_config
    
    print("=" * 60)
    print("🧪 CONFIG GRABBER - ИНТЕРАКТИВНЫЙ РЕЖИМ")
    print("=" * 60)
    
    # Получаем ЛСД без RPA-конфига
    try:
        lsd_configs = await get_lsd_without_rpa_config()
    except:
        # Если не получается подключиться к БД, предлагаем тестовые URL
        print("⚠️  Не удалось подключиться к БД, используем тестовые URL")
        test_urls = [
            "https://5ka.ru",
            "https://magnit.ru", 
            "https://www.utkonos.ru",
            "https://online.metro-cc.ru",
            "https://azbukavkusa.ru"
        ]
        
        print("📋 Доступные тестовые URL:")
        for i, url in enumerate(test_urls, 1):
            print(f"  {i}. {url}")
            
        choice = input(f"\nВыберите URL (1-{len(test_urls)}) или введите свой: ").strip()
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(test_urls):
                selected_url = test_urls[idx]
            else:
                print("❌ Неверный номер")
                return
        except ValueError:
            if choice.startswith("http"):
                selected_url = choice
            else:
                print("❌ Введите корректный URL")
                return
                
        print(f"\n🚀 Запускаем для: {selected_url}")
        await run_grabber(selected_url)
        return
        
    if not lsd_configs:
        print("✅ Все ЛСД уже имеют RPA-конфигурации!")
        return
        
    print("📋 ЛСД без RPA-конфигураций:")
    for i, config in enumerate(lsd_configs, 1):
        print(f"  {i}. {config.name} ({config.display_name})")
        print(f"     URL: {config.base_url}")
        
    print("\n🎯 Выберите ЛСД для генерации конфигурации:")
    
    while True:
        try:
            choice = input(f"Введите номер (1-{len(lsd_configs)}) или 'q' для выхода: ").strip()
            
            if choice.lower() == 'q':
                print("👋 До свидания!")
                return
                
            idx = int(choice) - 1
            if 0 <= idx < len(lsd_configs):
                selected_lsd = lsd_configs[idx]
                break
            else:
                print(f"❌ Неверный номер. Введите число от 1 до {len(lsd_configs)}")
                
        except ValueError:
            print("❌ Введите корректное число или 'q'")
            
    print(f"\n🚀 Запускаем генерацию для: {selected_lsd.display_name}")
    print(f"🌐 URL: {selected_lsd.base_url}")
    
    await run_grabber(selected_lsd.base_url)


async def run_grabber(url: str, demo_mode: bool = False):
    """Запускаем граббер для указанного URL"""
    if demo_mode:
        from demo_config_grabber import DemoConfigGrabber
        grabber_class = DemoConfigGrabber
        print("🎭 ДЕМО РЕЖИМ (без браузера)")
    else:
        grabber_class = ConfigGrabber
        print("🌐 РЕАЛЬНЫЙ РЕЖИМ (с браузером)")
        
    print("=" * 60)
    print(f"🎯 URL: {url}")
    print(f"📁 Рабочая директория: /tmp/config_grabber")
    print(f"📱 SMS коды: touch /tmp/config_grabber/sms_codes/1234")
    print("=" * 60)
    
    try:
        grabber = grabber_class(url, working_dir="/tmp/config_grabber")
        config = await grabber.generate_config()
        
        print("\n" + "=" * 60)
        print("✅ КОНФИГУРАЦИЯ СОЗДАНА УСПЕШНО!")
        print("=" * 60)
        
        domain = grabber._extract_domain()
        config_file = grabber.working_dir / f"rpa_config_{domain}.json"
        
        print(f"📄 Файл: {config_file}")
        print(f"🔧 Шагов: {len(config.get('steps', []))}")
        print(f"🔐 Тип: {config.get('type')}")
        
        # Предлагаем добавить в БД
        if not demo_mode:
            print("\n💾 Хотите добавить конфигурацию в базу данных?")
            add_to_db = input("Введите 'y' для подтверждения: ").strip().lower()
            
            if add_to_db == 'y':
                try:
                    from services.config_grabber.update_db_config import update_rpa_config
                    success = await update_rpa_config(domain, str(config_file))
                    if success:
                        print("🎉 Конфигурация добавлена в базу данных!")
                    else:
                        print("❌ Не удалось добавить в БД")
                except Exception as e:
                    print(f"❌ Ошибка БД: {e}")
            else:
                print(f"💡 Чтобы добавить позже:")
                print(f"   python services/config_grabber/update_db_config.py {domain} {config_file}")
        
    except KeyboardInterrupt:
        print("\n⏹️  Процесс остановлен пользователем")
        print("🔄 При следующем запуске работа продолжится с места остановки")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        print("🔧 Проверьте логи для детальной информации")


async def main():
    """Главная функция"""
    if len(sys.argv) == 1:
        # Интерактивный режим
        await interactive_mode()
        
    elif len(sys.argv) == 2:
        # Прямой запуск для URL
        url = sys.argv[1]
        if url in ['-h', '--help', 'help']:
            print_usage()
            return
            
        await run_grabber(url)
        
    elif len(sys.argv) == 3 and sys.argv[1] == 'demo':
        # Демо режим
        url = sys.argv[2]
        await run_grabber(url, demo_mode=True)
        
    else:
        print("❌ Неверные аргументы")
        print_usage()


if __name__ == "__main__":
    asyncio.run(main())
