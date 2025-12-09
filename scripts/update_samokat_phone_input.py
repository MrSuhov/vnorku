#!/usr/bin/env python3
"""
Скрипт для обновления RPA конфига Samokat - ввод телефона посимвольно без +7
"""
import json
import psycopg2
from psycopg2.extras import RealDictCursor

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

def update_samokat_rpa_config():
    """Обновление RPA конфига для Samokat - посимвольный ввод телефона без +7"""
    return {
        "type": "sms_auth_flow",
        "sms_required": True,
        "auth_url": "https://samokat.ru",
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
                "id": "clear_phone_field",
                "action": "clear",
                "selectors": [
                    "input#phone",
                    "input[name='phone']"
                ],
                "wait_after": 500
            },
            {
                "id": "enter_phone_digit_by_digit",
                "action": "type_digit_by_digit",
                "selectors": [
                    "input#phone",
                    "input[name='phone']"
                ],
                "text": "{phone_no_prefix}",
                "wait_between_digits": 100,
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

def update_samokat_config():
    """Обновление конфигурации Samokat в базе данных"""
    env_vars = load_env()
    database_url = env_vars.get('DATABASE_URL', 'postgresql://korzinka_user:korzinka_pass@localhost:5432/korzinka')
    
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Обновляем RPA конфиг для samokat
        cursor.execute("""
            UPDATE lsd_configs 
            SET 
                rpa_config = %s,
                updated_at = NOW()
            WHERE name = %s
        """, (
            json.dumps(update_samokat_rpa_config()),
            'samokat'
        ))
        
        if cursor.rowcount > 0:
            print("✅ RPA конфиг Samokat обновлен - теперь телефон вводится посимвольно без +7!")
        else:
            print("❌ Конфиг Samokat не найден в базе данных")
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка при работе с базой данных: {e}")
        if conn:
            conn.rollback()
            conn.close()

if __name__ == "__main__":
    update_samokat_config()
