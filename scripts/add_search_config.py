#!/usr/bin/env python3
"""
Добавление конфигурации поиска для ЛСД
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from shared.database import get_async_session
from shared.database.models import LSDConfig
from sqlalchemy import select, update
import json

async def add_search_configs():
    """Добавление конфигурации поиска для ЛСД"""
    
    # Конфигурация поиска для VkusVill
    vkusvill_search_config = {
        "search_input_selector": 'input[placeholder*="Поиск"], input[type="search"], input.search-input',
        "search_button_selector": 'button[type="submit"], .search-button, button:has(svg)',
        "result_item_selector": '.product-card, .product-item, [data-testid*="product"], .catalog-item',
        "name_selector": '.product-title, .product-name, h3, .name',
        "price_selector": '.price, .cost, .product-price, [data-testid*="price"]',
        "unit_selector": '.unit, .measure, .weight',
        "stock_selector": '.stock, .available, .in-stock',
        "discount_selector": '.discount, .old-price, .sale-price'
    }
    
    # Конфигурация поиска для Samokat
    samokat_search_config = {
        "search_input_selector": 'input[placeholder*="поиск"], input[type="search"]',
        "search_button_selector": 'button[type="submit"], .search-btn',
        "result_item_selector": '.product-card, .product-item',
        "name_selector": '.product-title, .product-name',
        "price_selector": '.price, .cost',
        "unit_selector": '.unit, .measure',
        "stock_selector": '.stock',
        "discount_selector": '.discount'
    }
    
    # Конфигурация поиска для Yandex Lavka
    yandex_search_config = {
        "search_input_selector": 'input[placeholder*="Поиск"], input[data-testid*="search"]',
        "search_button_selector": 'button[type="submit"]',
        "result_item_selector": '[data-testid*="product-card"], .product-card',
        "name_selector": '[data-testid*="product-title"], .product-title',
        "price_selector": '[data-testid*="price"], .price',
        "unit_selector": '.unit',
        "stock_selector": '.stock',
        "discount_selector": '.old-price'
    }
    
    # Конфигурация поиска для Ozon Fresh
    ozon_search_config = {
        "search_input_selector": 'input[placeholder*="Искать"], input[type="search"]',
        "search_button_selector": 'button[type="submit"]',
        "result_item_selector": '.product-card, [data-testid*="product"]',
        "name_selector": '.product-title, .name',
        "price_selector": '.price, .cost',
        "unit_selector": '.unit',
        "stock_selector": '.stock',
        "discount_selector": '.discount'
    }
    
    configs = [
        ("vkusvill", vkusvill_search_config),
        ("samokat", samokat_search_config),
        ("yandex_lavka", yandex_search_config),
        ("ozon_fresh", ozon_search_config)
    ]
    
    async for db in get_async_session():
        try:
            for lsd_name, config in configs:
                print(f"📋 Adding search config for {lsd_name}")
                
                # Находим ЛСД по имени
                result = await db.execute(
                    select(LSDConfig).where(LSDConfig.name == lsd_name)
                )
                lsd_config = result.scalar_one_or_none()
                
                if lsd_config:
                    # Обновляем конфигурацию поиска
                    await db.execute(
                        update(LSDConfig)
                        .where(LSDConfig.name == lsd_name)
                        .values(search_config_rpa=config)
                    )
                    print(f"✅ Updated search config for {lsd_config.display_name}")
                else:
                    print(f"⚠️ LSD config not found for {lsd_name}")
            
            await db.commit()
            print("✅ All search configs updated successfully!")
            
        except Exception as e:
            print(f"❌ Error updating search configs: {e}")
            await db.rollback()
        
        break

if __name__ == "__main__":
    print("🔧 Adding search configurations for LSDs...")
    asyncio.run(add_search_configs())
