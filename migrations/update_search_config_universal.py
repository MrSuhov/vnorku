#!/usr/bin/env python3
"""
Миграция для обновления search_config_rpa для универсального парсинга
Добавляет новые параметры для конфигурируемого поиска
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import sessionmaker
from shared.database.connection import sync_engine
from shared.database.models import LSDConfig
from shared.utils.logging import setup_logging, get_logger

logger = setup_logging()


def update_search_configs():
    """Обновление конфигураций поиска для универсального парсинга"""
    
    # Расширенные конфигурации поиска
    search_configs = {
        "vkusvill": {
            "search_method": "url",
            "search_url_pattern": "{base_url}/search/?isComplete=0&type=products&q={query}",
            
            # Основные селекторы (обязательные)
            "result_item_selector": ".ProductCard",
            "name_selector": ".ProductCard__link.js-product-detail-link",
            "price_selector": ".Price.Price--md.Price--gray.Price--label",
            
            # Опциональные селекторы
            "unit_selector": ".ProductCard__weight",
            "url_selector": ".ProductCard__link",
            "availability_selector": ".CartButton__textInner",
            "image_selector": ".ProductCard img",
            
            # Параметры обработки
            "require_availability": True,
            "availability_text_required": ["В корзину"],
            "max_results_to_process": 24,
            "wait_for_results": 3000,
            
            # Дополнительные параметры
            "encoding": "utf-8",
            "url_attribute": "href",
            "url_base": "https://vkusvill.ru",
            "result_container_selector": "#section_lvl2"
        },
        
        "yandex_lavka": {
            "search_method": "selector",
            "search_input_selector": "input[placeholder*='Найти товар']",
            "search_button_selector": "button[type='submit']",
            
            # Основные селекторы
            "result_item_selector": "[data-testid*='product-card']",
            "name_selector": "[data-testid*='product-title']",
            "price_selector": "[data-testid*='product-price']",
            
            # Опциональные селекторы
            "unit_selector": "[data-testid*='product-weight']",
            "url_selector": "a[href*='/products/']",
            "availability_selector": "[data-testid*='add-button']",
            
            # Параметры обработки
            "require_availability": False,  # Яндекс Лавка не всегда показывает кнопки
            "availability_text_required": ["В корзину", "Добавить"],
            "max_results_to_process": 20,
            "wait_for_results": 2000,
            
            "encoding": "utf-8",
            "url_base": "https://lavka.yandex.ru"
        },
        
        "samokat": {
            "search_method": "selector",
            "search_input_selector": "input[name='search']",
            
            # Основные селекторы
            "result_item_selector": ".product-card",
            "name_selector": ".product-card__title",
            "price_selector": ".product-card__price",
            
            # Опциональные селекторы
            "unit_selector": ".product-card__unit",
            "url_selector": ".product-card__link",
            "availability_selector": ".add-to-cart-button",
            
            # Параметры обработки
            "require_availability": True,
            "availability_text_required": ["В корзину", "Купить"],
            "max_results_to_process": 15,
            "wait_for_results": 2500,
            
            "encoding": "utf-8",
            "url_base": "https://samokat.ru"
        },
        
        "perekrestok": {
            "search_method": "url",
            "search_url_pattern": "{base_url}/cat/search/?text={query}",
            
            # Основные селекторы
            "result_item_selector": ".xf-product-tile",
            "name_selector": ".xf-product-tile__title",
            "price_selector": ".xf-price",
            
            # Опциональные селекторы  
            "unit_selector": ".xf-product-tile__unit",
            "url_selector": ".xf-product-tile__link",
            "availability_selector": ".xf-button--add-to-cart",
            
            # Параметры обработки
            "require_availability": True,
            "availability_text_required": ["В корзину"],
            "max_results_to_process": 18,
            "wait_for_results": 3000,
            
            "encoding": "utf-8",
            "url_base": "https://www.perekrestok.ru"
        }
    }
    
    Session = sessionmaker(bind=sync_engine)
    session = Session()
    
    try:
        # Получаем все ЛСД
        lsd_configs = session.query(LSDConfig).all()
        
        for lsd in lsd_configs:
            logger.info(f"Обновляем search_config_rpa для {lsd.name}")
            
            if lsd.name in search_configs:
                # Сохраняем некоторые параметры из старой конфигурации, если они есть
                old_config = lsd.search_config_rpa or {}
                new_config = search_configs[lsd.name].copy()
                
                # Сохраняем кастомные настройки, если они были
                preserved_keys = ['custom_selectors', 'special_handling', 'debug_mode']
                for key in preserved_keys:
                    if key in old_config:
                        new_config[key] = old_config[key]
                
                lsd.search_config_rpa = new_config
                logger.info(f"  ✅ Обновлен search_config_rpa для {lsd.name}")
                
                # Логируем ключевые изменения
                logger.info(f"    🔍 Search method: {new_config.get('search_method')}")
                logger.info(f"    📦 Max results: {new_config.get('max_results_to_process')}")
                logger.info(f"    ✅ Require availability: {new_config.get('require_availability')}")
                
            else:
                # Дефолтная конфигурация для неизвестных ЛСД
                default_config = {
                    "search_method": "selector",
                    "search_input_selector": "input[type='search'], input[name*='search'], input[placeholder*='поиск']",
                    
                    # Универсальные селекторы
                    "result_item_selector": ".product, .item, .card, [class*='product'], [class*='item']",
                    "name_selector": ".title, .name, h1, h2, h3, [class*='title'], [class*='name']",
                    "price_selector": ".price, .cost, [class*='price'], [class*='cost']",
                    
                    # Опциональные с fallback
                    "unit_selector": ".unit, .weight, [class*='unit'], [class*='weight']",
                    "url_selector": "a",
                    "availability_selector": ".button, .btn, [class*='add'], [class*='cart']",
                    
                    # Безопасные параметры
                    "require_availability": False,
                    "availability_text_required": ["В корзину", "Купить", "Добавить", "Add"],
                    "max_results_to_process": 10,
                    "wait_for_results": 3000,
                    
                    "encoding": "utf-8"
                }
                
                lsd.search_config_rpa = default_config
                logger.info(f"  ⚠️ Установлена дефолтная search_config_rpa для {lsd.name}")
        
        session.commit()
        logger.info("🎉 Миграция search_config_rpa завершена успешно!")
        
        # Показываем результат
        logger.info("\n📊 Результат миграции:")
        for lsd in lsd_configs:
            config = lsd.search_config_rpa or {}
            method = config.get('search_method', 'unknown')
            max_results = config.get('max_results_to_process', '?')
            require_avail = config.get('require_availability', '?')
            logger.info(f"  • {lsd.display_name}: {method} | max:{max_results} | avail:{require_avail}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении search_config_rpa: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    update_search_configs()
