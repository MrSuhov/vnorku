#!/usr/bin/env python3
"""
Скрипт для инициализации конфигурации ЛСД из CSV файла
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import csv
import asyncio
from decimal import Decimal
from sqlalchemy.orm import sessionmaker
from shared.database.connection import sync_engine
from shared.database.models import LSDConfig
from shared.utils.logging import setup_logging, get_logger

logger = setup_logging()


def normalize_lsd_name(display_name: str) -> str:
    """Конвертирует отображаемое имя в системное имя ЛСД"""
    mapping = {
        "Самокат": "samokat",
        "Яндекс Лавка": "yandex_lavka", 
        "Ozon Fresh": "ozon_fresh",
        "ВкусВилл": "vkusvill",
        "Утконос Онлайн": "utkonos",
        "Перекрёсток Онлайн / Vprok.ru": "perekrestok",
        "Пятёрочка Доставка": "pyaterochka",
        "Магнит Доставка": "magnit",
        "Лента Онлайн": "lenta",
        "Ашан Доставка": "auchan",
        "METRO Online": "metro",
        "Азбука Вкуса": "azbuka_vkusa",
        "Глобус Онлайн": "globus"
    }
    return mapping.get(display_name, display_name.lower().replace(" ", "_"))


def get_default_config(name: str) -> dict:
    """Получает дефолтную конфигурацию для ЛСД"""
    
    # RPA селекторы для авторизации и взаимодействия
    rpa_selectors = {
        "samokat": {
            "phone_input": "input[type='tel']",
            "sms_input": "input[placeholder*='код']",
            "login_button": "button[type='submit']",
            "cart_button": "[data-testid='cart-button']",
            "add_to_cart": "[data-testid='add-to-cart']",
            "checkout": "[data-testid='checkout-button']"
        },
        "yandex_lavka": {
            "phone_input": "input[name='login']", 
            "sms_input": "input[name='passwd']",
            "login_button": "button[type='submit']",
            "cart_selector": ".cart",
            "add_to_cart": ".add-button",
            "checkout": ".checkout-button"
        }
    }
    
    # API endpoints для каждого ЛСД (если есть публичные API)
    api_endpoints = {
        "samokat": {
            "search": "/api/v1/search",
            "product": "/api/v1/products/{product_id}",
            "cart": "/api/v1/cart",
            "checkout": "/api/v1/checkout"
        }
    }
    
    # Конфигурация авторизации (без секретов!)
    auth_configs = {
        "samokat": {
            "auth_method": "sms",
            "phone_required": True,
            "supports_session": True,
            "session_duration": 86400  # 24 часа
        },
        "yandex_lavka": {
            "auth_method": "yandex_id",
            "phone_required": True, 
            "supports_session": True,
            "session_duration": 86400
        }
    }
    
    # Стоимость доставки и условия
    delivery_configs = {
        "samokat": {
            "min_order_amount": Decimal("0"),
            "delivery_fee": Decimal("199"),
            "free_delivery_threshold": Decimal("1000"),
            "regions": ["moscow", "spb"]
        },
        "yandex_lavka": {
            "min_order_amount": Decimal("0"),
            "delivery_fee": Decimal("0"),
            "free_delivery_threshold": None,
            "regions": ["moscow", "spb"] 
        },
        "ozon_fresh": {
            "min_order_amount": Decimal("3000"),
            "delivery_fee": Decimal("0"),
            "free_delivery_threshold": None,
            "regions": ["moscow"]
        }
    }
    
    # Получаем конфигурацию для конкретного ЛСД
    delivery = delivery_configs.get(name, {
        "min_order_amount": Decimal("0"),
        "delivery_fee": Decimal("299"),
        "free_delivery_threshold": Decimal("1500"),
        "regions": ["moscow"]
    })
    
    return {
        "rpa_config": rpa_selectors.get(name, {}),
        "api_endpoints": api_endpoints.get(name, {}),
        "auth_config": auth_configs.get(name, {"auth_method": "unknown"}),
        **delivery
    }


def init_lsd_from_csv(csv_file_path: str):
    """Инициализация ЛСД из CSV файла"""
    
    Session = sessionmaker(bind=sync_engine)
    session = Session()
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                display_name = row['Сервис'].strip()
                base_url = row['Web-адрес'].strip()
                name = normalize_lsd_name(display_name)
                
                # Проверяем, не существует ли уже такой ЛСД
                existing = session.query(LSDConfig).filter_by(name=name).first()
                if existing:
                    logger.info(f"LSD {name} уже существует, пропускаем")
                    continue
                
                # Получаем дефолтную конфигурацию
                config = get_default_config(name)
                
                # Создаем новый ЛСД
                lsd_config = LSDConfig(
                    name=name,
                    display_name=display_name,
                    base_url=base_url,
                    api_endpoints=config["api_endpoints"],
                    auth_config=config["auth_config"], 
                    rpa_config=config["rpa_config"],
                    is_active=False,  # По умолчанию отключены
                    is_mvp=(name == "samokat"),  # Только Самокат активен в MVP
                    min_order_amount=config["min_order_amount"],
                    delivery_fee=config["delivery_fee"],
                    free_delivery_threshold=config.get("free_delivery_threshold"),
                    regions=config["regions"]
                )
                
                session.add(lsd_config)
                logger.info(f"Добавлен ЛСД: {display_name} ({name})")
        
        session.commit()
        logger.info("Инициализация ЛСД завершена успешно!")
        
        # Активируем Самокат для MVP
        samokat = session.query(LSDConfig).filter_by(name="samokat").first()
        if samokat:
            samokat.is_active = True
            samokat.is_mvp = True
            session.commit()
            logger.info("Самокат активирован для MVP")
        
    except Exception as e:
        logger.error(f"Ошибка при инициализации ЛСД: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    csv_file = "data/egrocery_moscow.csv"
    
    if not os.path.exists(csv_file):
        logger.error(f"CSV файл не найден: {csv_file}")
        sys.exit(1)
    
    init_lsd_from_csv(csv_file)
    
    # Показываем результат
    Session = sessionmaker(bind=sync_engine)
    session = Session()
    try:
        lsd_configs = session.query(LSDConfig).all()
        print(f"\n📊 Всего ЛСД в системе: {len(lsd_configs)}")
        print("📋 Список ЛСД:")
        for lsd in lsd_configs:
            status = "🟢 Активен" if lsd.is_active else "🔴 Отключен"
            mvp = " [MVP]" if lsd.is_mvp else ""
            print(f"  • {lsd.display_name} ({lsd.name}) - {status}{mvp}")
    finally:
        session.close()
