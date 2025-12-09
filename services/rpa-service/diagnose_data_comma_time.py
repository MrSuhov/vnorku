#!/usr/bin/env python3
"""
Диагностика: Измерение времени на data:, навигацию
"""

import time
import sys
sys.path.insert(0, '/Users/ss/GenAI/korzinka/services/rpa-service')

from cdp_cookie_manager import CDPCookieManager
from selenium import webdriver

print("\n" + "="*60)
print("⏱️ Measuring data:, navigation time")
print("="*60 + "\n")

# Создаём CDP менеджер
cdp_manager = CDPCookieManager()

# Запускаем браузер
print("🚀 Starting browser...")
start_browser = time.time()
driver = cdp_manager.setup_browser_with_cdp(headless=False, block_media=True)
browser_time = time.time() - start_browser
print(f"✅ Browser started in {browser_time:.2f}s\n")

# Измеряем время на data:, навигацию
print("📍 Navigating to data:,...")
start_nav = time.time()
driver.get("data:,")
nav_time = time.time() - start_nav
print(f"✅ Navigation complete in {nav_time:.2f}s\n")

# Проверяем URL
current_url = driver.current_url
print(f"📄 Current URL: {current_url}\n")

# Измеряем время инъекции кук
print("🍪 Injecting 10 test cookies...")
test_cookies = [
    {'name': f'test_{i}', 'value': f'value_{i}', 'domain': '.example.com', 'path': '/'}
    for i in range(10)
]

start_inject = time.time()
for cookie in test_cookies:
    try:
        cdp_cookie = {
            'name': cookie['name'],
            'value': cookie['value'],
            'domain': cookie['domain'],
            'path': cookie['path']
        }
        driver.execute_cdp_cmd('Network.setCookie', cdp_cookie)
    except Exception as e:
        print(f"⚠️ Failed: {e}")

inject_time = time.time() - start_inject
print(f"✅ Injection complete in {inject_time:.2f}s\n")

# Итоговая статистика
print("="*60)
print("📊 TIMING BREAKDOWN:")
print(f"   Browser startup: {browser_time:.2f}s")
print(f"   data:, navigation: {nav_time:.2f}s")
print(f"   Cookie injection (10): {inject_time:.2f}s")
print(f"   TOTAL: {browser_time + nav_time + inject_time:.2f}s")
print("="*60 + "\n")

print("⏳ Browser will stay open for 10 seconds...")
time.sleep(10)

driver.quit()
print("✅ Done!\n")
