#!/usr/bin/env python3
"""
Скрипт для добавления конфигураций поиска товаров в существующие ЛСД
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


def get_search_configs():
    """Возвращает конфигурации поиска для каждого ЛСД"""
    
    search_configs = {
        "samokat": {
            "search_input_selector": "input[placeholder*='Поиск'], input[name='search'], input[type='search']",
            "search_button_selector": "button[type='submit'], .search-button",
            "result_item_selector": ".product-card, [data-testid='product-card'], .catalog-item",
            "name_selector": ".product-title, .product-name, h3, [data-testid='product-title']",
            "price_selector": ".price, .product-price, [data-testid='price']",
            "unit_selector": ".unit, .product-unit, .weight",
            "add_to_cart_selector": ".add-to-cart, [data-testid='add-to-cart']",
            "stock_selector": ".stock, .availability",
            "discount_selector": ".discount, .sale-price",
            "wait_for_results": 3000,
            "max_results_to_check": 5
        },
        
        "yandex_lavka": {
            "search_input_selector": "input[placeholder*='поиск'], input[name='search']", 
            "search_button_selector": "button[type='submit'], .search-submit",
            "result_item_selector": ".product, .goods-item, [data-zone-name='product-card']",
            "name_selector": ".product__title, .goods-item__title, h3",
            "price_selector": ".price, .product__price, .goods-item__price",
            "unit_selector": ".unit, .product__unit",
            "add_to_cart_selector": ".add-button, .product__add-button",
            "stock_selector": ".stock-status",
            "discount_selector": ".discount-price, .old-price",
            "wait_for_results": 2000,
            "max_results_to_check": 3
        },
        
        "ozon_fresh": {
            "search_input_selector": "input[placeholder*='Поиск'], input[name='text']",
            "search_button_selector": "button[type='submit'], .search-button",
            "result_item_selector": ".tile, .product-tile, [data-widget='searchResultsV2']",
            "name_selector": ".tile-hover-target, .product-title",
            "price_selector": ".price, .c2h5, .c3015",
            "unit_selector": ".unit-info, .weight-info",
            "add_to_cart_selector": ".add-to-cart, .c4021",
            "stock_selector": ".availability",
            "discount_selector": ".discount-price",
            "wait_for_results": 2500,
            "max_results_to_check": 5
        },
        
        "vkusvill": {
            "search_input_selector": "input[name='q'], input[placeholder*='поиск']",
            "search_button_selector": "button[type='submit'], .btn-search",
            "result_item_selector": ".product-item, .goods-tile",
            "name_selector": ".product-name, .goods-tile__title",
            "price_selector": ".price, .product-price", 
            "unit_selector": ".unit, .weight",
            "add_to_cart_selector": ".add-to-basket, .btn-add",
            "stock_selector": ".stock-info",
            "discount_selector": ".old-price",
            "wait_for_results": 2000,
            "max_results_to_check": 3
        },
        
        "pyaterochka": {
            "search_input_selector": "input[placeholder*='Поиск товаров'], input[name='search']",
            "search_button_selector": "button[type='submit'], .search-btn",
            "result_item_selector": ".product-card, .goods-card",
            "name_selector": ".product-card__title, .goods-card__name",
            "price_selector": ".price, .product-card__price",
            "unit_selector": ".unit, .product-card__unit",
            "add_to_cart_selector": ".add-button, .product-card__add",
            "stock_selector": ".availability-status",
            "discount_selector": ".discount, .old-price",
            "wait_for_results": 3000,
            "max_results_to_check": 5
        },
        
        "perekrestok": {
            "search_input_selector": "input[placeholder*='поиск'], input[name='query']",
            "search_button_selector": "button[type='submit'], .search-submit",
            "result_item_selector": ".xf-product-tile, .product-card",
            "name_selector": ".xf-product-tile__title, .product-name",
            "price_selector": ".price, .xf-price",
            "unit_selector": ".unit-label",
            "add_to_cart_selector": ".add-to-cart-btn",
            "stock_selector": ".stock-label",
            "discount_selector": ".old-price, .discount-price",
            "wait_for_results": 2500,
            "max_results_to_check": 4
        }
    }
    
    return search_configs


def add_search_configs_to_lsd():
    """Добавляет конфигурации поиска к существующим ЛСД"""
    
    Session = sessionmaker(bind=sync_engine)
    session = Session()
    
    try:
        search_configs = get_search_configs()
        
        # Получаем все ЛСД из базы
        lsd_configs = session.query(LSDConfig).all()
        
        logger.info(f"Найдено {len(lsd_configs)} ЛСД в базе данных")
        
        updated_count = 0
        
        for lsd_config in lsd_configs:
            lsd_name = lsd_config.name
            
            # Проверяем, есть ли конфигурация поиска для этого ЛСД
            if lsd_name in search_configs:
                search_config = search_configs[lsd_name]
                
                # Обновляем поле search_config_rpa
                lsd_config.search_config_rpa = search_config
                
                logger.info(f"✅ Добавлена search_config_rpa для {lsd_config.display_name}")
                updated_count += 1
                
            else:
                # Если нет специфичной конфигурации, добавляем базовую
                base_config = {
                    "search_input_selector": "input[type='search'], input[name='search'], input[placeholder*='поиск']",
                    "search_button_selector": "button[type='submit'], .search-button, .btn-search",
                    "result_item_selector": ".product, .product-card, .goods-item, .tile",
                    "name_selector": ".product-name, .product-title, .title, h3",
                    "price_selector": ".price, .product-price, .cost",
                    "unit_selector": ".unit, .weight, .volume",
                    "add_to_cart_selector": ".add-to-cart, .btn-add, .add-button",
                    "stock_selector": ".stock, .availability",
                    "discount_selector": ".discount, .sale-price, .old-price",
                    "wait_for_results": 3000,
                    "max_results_to_check": 5
                }
                
                lsd_config.search_config_rpa = base_config
                
                logger.warning(f"⚠️  Добавлена базовая search_config_rpa для {lsd_config.display_name}")
                updated_count += 1
        
        # Сохраняем изменения
        session.commit()
        
        logger.info(f"🎉 Успешно обновлено {updated_count} ЛСД с конфигурациями поиска")
        
        # Показываем результат
        print(f"\n📊 Обновленные ЛСД:")
        for lsd_config in session.query(LSDConfig).all():
            has_search_config = "✅" if lsd_config.search_config_rpa else "❌"
            print(f"  • {lsd_config.display_name} ({lsd_config.name}) - {has_search_config}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении конфигураций поиска: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def show_search_config_example():
    """Показывает пример конфигурации поиска"""
    
    print("\n📋 Пример конфигурации поиска:")
    print("=" * 50)
    
    example_config = {
        "search_input_selector": "input[placeholder*='Поиск']",
        "search_button_selector": "button[type='submit']", 
        "result_item_selector": ".product-card",
        "name_selector": ".product-title",
        "price_selector": ".price",
        "unit_selector": ".unit",
        "add_to_cart_selector": ".add-to-cart",
        "stock_selector": ".stock",
        "discount_selector": ".discount",
        "wait_for_results": 3000,
        "max_results_to_check": 5
    }
    
    import json
    print(json.dumps(example_config, indent=2, ensure_ascii=False))
    
    print("\n📝 Описание полей:")
    print("• search_input_selector - селектор поля поиска")
    print("• search_button_selector - селектор кнопки поиска (опционально)")
    print("• result_item_selector - селектор элементов результатов поиска")
    print("• name_selector - селектор названия товара в результате")
    print("• price_selector - селектор цены товара")
    print("• unit_selector - селектор единицы измерения")
    print("• add_to_cart_selector - селектор кнопки добавления в корзину")
    print("• stock_selector - селектор информации о наличии")
    print("• discount_selector - селектор скидочной цены")
    print("• wait_for_results - время ожидания результатов (мс)")
    print("• max_results_to_check - максимальное количество результатов для проверки")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--example":
        show_search_config_example()
    else:
        print("🔍 Добавление конфигураций поиска товаров в ЛСД...")
        add_search_configs_to_lsd()
        print("\n✅ Готово! Теперь можно использовать поиск товаров через RPA.")
