#!/usr/bin/env python3
"""
Скрипт для замены мест досрочного выхода с сохранением кук
"""

import sys

def replace_early_returns(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    modifications = []
    
    # Место 1: Строка 908 (с учетом +1 строки от импорта)
    # Ищем: "return []  # Возвращаем пустой список результатов"
    # ПОСЛЕ: "logger.warning(f"⚠️ Skipping all searches for {lsd_config.display_name} due to block")"
    for i in range(len(lines)):
        if i >= 905 and i <= 915:
            if "Skipping all searches" in lines[i] and "due to block" in lines[i]:
                # Нашли! Следующая строка должна быть return []
                if i+1 < len(lines) and "return []" in lines[i+1]:
                    modifications.append(('block', i+1))
                    print(f"✅ Found BLOCK early return at line {i+2}")
                    break
    
    # Место 2: Строка ~1110 (с учетом +1 строки от импорта)
    # Ищем: "return []" ПОСЛЕ "Skipping delivery extraction"
    for i in range(len(lines)):
        if i >= 1105 and i <= 1115:
            if "Skipping delivery extraction" in lines[i]:
                # Проверяем следующие 5 строк на return []
                for j in range(i+1, min(i+6, len(lines))):
                    if "return []" in lines[j] and "# Возвращаем пустой список" not in lines[j]:
                        modifications.append(('delivery_unavailable', j))
                        print(f"✅ Found DELIVERY_UNAVAILABLE early return at line {j+1}")
                        break
                break
    
    # Место 3: Строки ~1334-1387 (основной блок сохранения кук)
    for i in range(len(lines)):
        if i >= 1330 and i <= 1340:
            if "Extracting and saving updated cookies before returning results" in lines[i]:
                # Нашли начало блока
                # Ищем конец блока (return results)
                for j in range(i, min(i+60, len(lines))):
                    if "return results" in lines[j]:
                        modifications.append(('main_save', i, j))
                        print(f"✅ Found main cookie save block at lines {i+1}-{j+1}")
                        break
                break
    
    if not modifications:
        print("❌ No modifications found!")
        return False
    
    print(f"\n📝 Making {len(modifications)} modifications...")
    
    # Применяем изменения в обратном порядке (чтобы индексы не сбились)
    modifications.reverse()
    
    for mod in modifications:
        if mod[0] == 'block':
            idx = mod[1]
            # Вставляем 3 строки ПЕРЕД return []
            indent = "                "
            lines[idx] = (
                f"{indent}# 💾 Сохраняем куки перед досрочным выходом (из-за блокировки)\n"
                f"{indent}logger.info(f\"💾 Saving cookies before early return due to BLOCK\")\n"
                f"{indent}await _save_cookies_before_return(cdp_manager, driver, telegram_id, lsd_config, [], save_user_cookies)\n"
                f"{indent}\n"
                + lines[idx]
            )
            print(f"✅ Modified BLOCK return at line {idx+1}")
            
        elif mod[0] == 'delivery_unavailable':
            idx = mod[1]
            # Вставляем 3 строки ПЕРЕД return []
            indent = "                        "
            lines[idx] = (
                f"{indent}# 💾 Сохраняем куки перед досрочным выходом (доставка недоступна)\n"
                f"{indent}logger.info(f\"💾 Saving cookies before early return due to DELIVERY_UNAVAILABLE\")\n"
                f"{indent}await _save_cookies_before_return(cdp_manager, driver, telegram_id, lsd_config, [], save_user_cookies)\n"
                f"{indent}\n"
                + lines[idx]
            )
            print(f"✅ Modified DELIVERY_UNAVAILABLE return at line {idx+1}")
            
        elif mod[0] == 'main_save':
            start_idx, end_idx = mod[1], mod[2]
            # Заменяем весь блок на вызов функции
            indent = "        "
            new_block = (
                f"{indent}# 💾 СОХРАНЯЕМ COOKIES ПЕРЕД ВОЗВРАТОМ РЕЗУЛЬТАТОВ\n"
                f"{indent}await _save_cookies_before_return(cdp_manager, driver, telegram_id, lsd_config, products, save_user_cookies)\n"
                f"{indent}\n"
                f"{indent}return results\n"
            )
            # Удаляем старые строки и вставляем новые
            del lines[start_idx:end_idx+1]
            lines.insert(start_idx, new_block)
            print(f"✅ Replaced main cookie save block at lines {start_idx+1}-{end_idx+1}")
    
    # Сохраняем обратно
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"\n✅ All modifications completed!")
    return True

if __name__ == '__main__':
    filepath = '/Users/ss/GenAI/korzinka/services/rpa-service/main.py'
    success = replace_early_returns(filepath)
    sys.exit(0 if success else 1)
