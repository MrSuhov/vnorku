#!/usr/bin/env python3
"""
Скрипт для обновления всех return statements в extract_delivery_ranges
Добавляет третий элемент is_delivery_available к каждому return
"""

import re

# Читаем файл
with open('selenium_product_search.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Находим функцию extract_delivery_ranges
func_start = content.find('async def extract_delivery_ranges(')
func_end = content.find('\nasync def ', func_start + 1)

if func_start == -1:
    print("❌ Function extract_delivery_ranges not found")
    exit(1)

# Извлекаем функцию
if func_end == -1:
    func_body = content[func_start:]
    after_func = ""
else:
    func_body = content[func_start:func_end]
    after_func = content[func_end:]

before_func = content[:func_start]

# Заменяем все return ranges_data, min_order_amount на return ranges_data, min_order_amount, is_delivery_available
# НО только внутри функции extract_delivery_ranges
updated_func_body = re.sub(
    r'return ranges_data, min_order_amount\b',
    'return ranges_data, min_order_amount, is_delivery_available',
    func_body
)

# Считаем сколько замен
original_returns = func_body.count('return ranges_data, min_order_amount')
print(f"✅ Found {original_returns} return statements to update")

# Собираем обратно
updated_content = before_func + updated_func_body + after_func

# Записываем
with open('selenium_product_search.py', 'w', encoding='utf-8') as f:
    f.write(updated_content)

print(f"✅ Updated all return statements in extract_delivery_ranges")
print(f"📝 Backup saved to selenium_product_search.py.backup_delivery_fix")
