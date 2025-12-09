#!/usr/bin/env python3
"""
Скрипт для обновления конфигурации поиска товаров в Самокате с правильными селекторами
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from sqlalchemy.orm import sessionmaker
from shared.database.connection import sync_engine
from shared.database.models import LSDConfig
from shared.utils.logging import setup_logging, get_logger

logger = setup_logging()


def get_updated_samokat_config():
    """Возвращает обновленную конфигурацию поиска для Самоката с правильными селекторами"""
    
    return {
        # Контейнер со списком товаров
        "result_container_selector": "div[class*='ProductsList']",
        
        # Селектор отдельного товара (ссылка на продукт)
        "result_item_selector": "a[href*='/product/']",
        
        # Название товара 
        "name_selector": "div[class*='ProductCard_name']",
        
        # Цена товара - сложная логика для обычных и акционных цен
        "price_selector": "div[class*='ProductCardActions_text'] span[class*='Text_text']:not([class*='oldPrice'])",
        
        # Альтернативный селектор для акционных цен (без старой цены)
        "price_current_selector": "div[class*='ProductCardActions_text'] span[class*='Text_text']:not([class*='oldPrice']) span",
        
        # Старая цена для акционных товаров
        "price_old_selector": "div[class*='ProductCardActions_text'] span[class*='oldPrice']",
        
        # Единица измерения (последний span в specification)
        "unit_selector": "div[class*='ProductCard_specification'] span[class*='Text_text']:last-child",
        
        # URL товара (из href ссылки)
        "url_selector": "a[href*='/product/']",
        
        # Минимальная сумма заказа
        "min_order_selector": "button[class*='CheckoutButton_control'] span[class*='Text_text']:last-child",
        
        # Дополнительные селекторы для поиска
        "search_input_selector": "input[placeholder*='Поиск'], input[name='search'], input[type='search']",
        "search_button_selector": "button[type='submit'], .search-button",
        
        # Селекторы для состояния товара
        "stock_selector": ".stock, .availability",
        "add_to_cart_selector": "button[class*='AddToCartButton'], button[class*='ProductCardActions']",
        
        # Настройки ожидания
        "wait_for_results": 3000,
        "max_results_to_check": 10,
        
        # Дополнительные настройки для парсинга
        "price_regex": r"(\d+(?:[\s,\.]\d+)*)",  # Для извлечения чисел из текста цены
        "unit_regex": r"(\d+(?:[,\.]\d+)?)\s*(г|кг|мл|л|шт)",  # Для парсинга единиц измерения
        "min_order_regex": r"(\d+(?:[\s,\.]\d+)*)",  # Для извлечения минимальной суммы
        
        # Настройки для обработки результатов
        "ignore_out_of_stock": True,
        "prefer_discounted_price": True,
        
        # URL patterns для валидации
        "base_url": "https://samokat.ru",
        "search_url_pattern": "https://samokat.ru/search?value={query}",
        "product_url_pattern": "https://samokat.ru/product/*"
    }


def update_samokat_search_config():
    """Обновляет конфигурацию поиска для Самоката в базе данных"""
    
    Session = sessionmaker(bind=sync_engine)
    session = Session()
    
    try:
        # Ищем конфигурацию Самоката
        samokat_config = session.query(LSDConfig).filter(
            LSDConfig.name == 'samokat'
        ).first()
        
        if not samokat_config:
            logger.error("❌ Конфигурация для Самоката не найдена в базе данных")
            print("❌ Сначала нужно добавить Самокат в систему")
            return False
            
        # Получаем новую конфигурацию
        new_config = get_updated_samokat_config()
        
        # Обновляем конфигурацию
        samokat_config.search_config_rpa = new_config
        
        # Сохраняем изменения
        session.commit()
        
        logger.info("✅ Конфигурация поиска для Самоката успешно обновлена")
        print(f"✅ Обновлена конфигурация для: {samokat_config.display_name}")
        
        # Показываем обновленную конфигурацию
        print("\n📋 Новая конфигурация поиска для Самоката:")
        print("=" * 60)
        
        import json
        print(json.dumps(new_config, indent=2, ensure_ascii=False))
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении конфигурации Самоката: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def show_samokat_selectors_info():
    """Показывает информацию о новых селекторах Самоката"""
    
    print("\n🎯 Обновленные селекторы для Самоката:")
    print("=" * 50)
    
    selectors_info = {
        "Контейнер результатов": "div[class*='ProductsList']",
        "Карточка товара": "a[href*='/product/']", 
        "Название товара": "div[class*='ProductCard_name']",
        "Цена (обычная)": "div[class*='ProductCardActions_text'] span:not([class*='oldPrice']) span",
        "Цена (акционная)": "span:not([class*='oldPrice']) (исключаем старую цену)",
        "Единица измерения": "div[class*='ProductCard_specification'] span:last-child",
        "URL товара": "href из ссылки a[href*='/product/']",
        "Минимальный заказ": "button[class*='CheckoutButton_control'] span:last-child"
    }
    
    for desc, selector in selectors_info.items():
        print(f"• {desc:20} → {selector}")
    
    print(f"\n🔍 Особенности парсинга:")
    print("• Использование wildcard селекторов [class*='...'] для стабильности")
    print("• Отдельная обработка обычных и акционных цен")
    print("• Извлечение чисел из текста с помощью regex")
    print("• Поддержка различных единиц измерения (г, кг, мл, л, шт)")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--info":
        show_samokat_selectors_info()
    else:
        print("🔧 Обновление конфигурации поиска для Самоката...")
        
        if update_samokat_search_config():
            print("\n✅ Конфигурация успешно обновлена!")
            print("🧪 Теперь можно тестировать поиск товаров в Самокате")
        else:
            print("\n❌ Не удалось обновить конфигурацию")
            sys.exit(1)
