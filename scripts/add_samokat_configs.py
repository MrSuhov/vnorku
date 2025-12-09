#!/usr/bin/env python3
"""
Скрипт для добавления конфигураций Samokat в базу данных
"""
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import sys

# Добавим текущую директорию в path для импорта настроек
sys.path.append('/Users/ss/GenAI/korzinka')

def load_env():
    """Загрузка переменных окружения из .env файла"""
    env_path = '/Users/ss/GenAI/korzinka/.env'
    env_vars = {}
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key] = value
    return env_vars

def create_samokat_rpa_config():
    """Создание RPA конфига для авторизации в Samokat"""
    return {
        "type": "sms_auth_flow",
        "sms_required": True,
        "auth_url": "https://samokat.ru",
        "browser_profile": "samokat_antibot_profile",
        "success_indicators": [
            {
                "selector": "//div[contains(@class, 'ProfileButton_content')]//span[text()='Войти']",
                "expected": "not_found"
            },
            {
                "selector": "//button[contains(@class, 'ProfileButton')]//span[not(text()='Войти')]"
            }
        ],
        "steps": [
            {
                "id": "open_page",
                "action": "navigate",
                "url": "https://samokat.ru",
                "wait_for": {
                    "selectors": [
                        "//span[text()='Войти']"
                    ]
                },
                "timeout": 15000
            },
            {
                "id": "click_login",
                "action": "click",
                "selectors": [
                    "//span[text()='Войти']"
                ],
                "wait_for": {
                    "selectors": [
                        "//span[text()='Войти по номеру телефона']"
                    ]
                },
                "timeout": 10000,
                "wait_after": 2000
            },
            {
                "id": "click_phone_login",
                "action": "click",
                "selectors": [
                    "//span[text()='Войти по номеру телефона']"
                ],
                "wait_for": {
                    "selectors": [
                        "input#phone",
                        "input[name='phone']"
                    ]
                },
                "timeout": 10000,
                "wait_after": 2000
            },
            {
                "id": "enter_phone",
                "action": "type",
                "selectors": [
                    "input#phone",
                    "input[name='phone']"
                ],
                "text": "{phone}",
                "clear_first": True,
                "wait_after": 1000
            },
            {
                "id": "click_get_code",
                "action": "click",
                "selectors": [
                    "//span[text()='Получить код']"
                ],
                "wait_for": {
                    "selectors": [
                        "input[type='text'][inputmode='numeric'][autocomplete='one-time-code']"
                    ]
                },
                "timeout": 10000,
                "wait_after": 2000
            },
            {
                "id": "enter_sms_code",
                "action": "type_sms_code",
                "selectors": [
                    "input[type='text'][inputmode='numeric'][autocomplete='one-time-code'][pattern='\\d{1}']"
                ],
                "code_length": 6,
                "individual_inputs": True,
                "wait_after": 2000
            }
        ]
    }

def create_samokat_search_config():
    """Создание конфига для поиска в Samokat"""
    return {
        "search_method": "url",
        "search_url_pattern": "https://samokat.ru/search?value={query}",
        "result_container_selector": ".ProductsList_productList__jjQpU",
        "result_item_selector": ".ProductsList_productList__jjQpU > div",
        "name_selector": ".ProductCard_name__2VDcL span.Text_text__7SbT7",
        "price_selector": [
            ".ProductCardActions_text__3Uohy span.Text_text__7SbT7 span:not(.ProductCardActions_oldPrice__d7vDY)",
            ".ProductCardActions_text__3Uohy span span:last-child"
        ],
        "old_price_selector": ".ProductCardActions_oldPrice__d7vDY",
        "unit_selector": ".ProductCard_specification__Y0xA6 span.Text_text__7SbT7:first-child",
        "url_selector": "a[href*='/product/']",
        "availability_selector": "button:not([disabled])",
        "min_order_selector": ".CheckoutButton_control__jb0tH span.Text_text__7SbT7",
        "image_selector": "img",
        "require_availability": True,
        "max_results_to_process": 24,
        "wait_for_results": 3000,
        "encoding": "utf-8",
        "url_attribute": "href",
        "url_base": "https://samokat.ru",
        "price_regex": r"(\d+(?:\s*\d+)*)\s*₽",
        "unit_regex": r"(\d+(?:\.\d+)?)\s*(мл|л|г|кг|шт)",
        "min_order_regex": r"Заказ от\s+(\d+)\s*₽"
    }

def insert_samokat_config():
    """Вставка конфигурации Samokat в базу данных"""
    env_vars = load_env()
    database_url = env_vars.get('DATABASE_URL', 'postgresql://korzinka_user:korzinka_pass@localhost:5432/korzinka')
    
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Проверяем, существует ли уже конфиг для samokat
        cursor.execute("SELECT id FROM lsd_configs WHERE name = %s", ('samokat',))
        existing = cursor.fetchone()
        
        if existing:
            print("Конфиг для Samokat уже существует, обновляем...")
            cursor.execute("""
                UPDATE lsd_configs 
                SET 
                    rpa_config = %s,
                    search_config_rpa = %s,
                    updated_at = NOW()
                WHERE name = %s
            """, (
                json.dumps(create_samokat_rpa_config()),
                json.dumps(create_samokat_search_config()),
                'samokat'
            ))
            print("Конфиг Samokat обновлен!")
        else:
            # Создаем новую запись
            cursor.execute("""
                INSERT INTO lsd_configs (
                    name, 
                    display_name, 
                    base_url, 
                    auth_url,
                    rpa_config, 
                    search_config_rpa,
                    is_active, 
                    is_mvp,
                    min_order_amount,
                    delivery_fee,
                    regions
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                'samokat',
                'Самокат',
                'https://samokat.ru',
                'https://samokat.ru',
                json.dumps(create_samokat_rpa_config()),
                json.dumps(create_samokat_search_config()),
                True,
                True,
                460.00,  # минимальный заказ по умолчанию
                0.00,    # доставка бесплатная обычно
                json.dumps(['moscow', 'spb'])
            ))
            print("Конфиг Samokat создан!")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Операция завершена успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка при работе с базой данных: {e}")
        if conn:
            conn.rollback()
            conn.close()

if __name__ == "__main__":
    insert_samokat_config()
