"""
Парсер для обработки альтернативных товаров (через слеш)
С поддержкой согласования прилагательных по роду
"""
import re
from typing import List, Dict, Optional

try:
    from shared.utils.gender_agreement import apply_gender_agreement, get_product_gender
except ImportError:
    # Заглушка если модуль недоступен
    def apply_gender_agreement(product_name: str, common_suffix: str, source_gender=None) -> str:
        return common_suffix
    
    def get_product_gender(product_name: str) -> str:
        return 'unknown'


def parse_alternatives(product_text: str) -> Dict[str, any]:
    """
    Парсит строку товара на предмет альтернатив (разделитель /)
    С автоматическим согласованием прилагательных по роду
    
    Примеры:
        "форель / семга 500г" -> {
            "main": "форель 500г",
            "alternatives": ["семга 500г"],
            "has_alternatives": True
        }
        
        "форель / семга / лосось слабосоленая русское море" -> {
            "main": "форель слабосоленая русское море",
            "alternatives": [
                "семга слабосоленая русское море",  # ж.р., не меняется
                "лосось слабосоленый русское море"  # м.р., согласовано!
            ],
            "has_alternatives": True
        }
    
    Args:
        product_text: Строка с описанием товара
        
    Returns:
        Словарь с распарсенными данными
    """
    if not product_text or not product_text.strip():
        return {
            "main": "",
            "alternatives": [],
            "has_alternatives": False,
            "full_text": product_text
        }
    
    text = product_text.strip()
    
    # Разделяем на части по слешу
    parts = [part.strip() for part in text.split('/')]
    
    if len(parts) == 1:
        # Нет альтернатив
        return {
            "main": text,
            "alternatives": [],
            "has_alternatives": False,
            "full_text": text
        }
    
    # Есть альтернативы
    # Определяем общие слова (суффикс)
    last_part = parts[-1].strip()
    last_part_words = last_part.split()
    
    common_suffix = ""
    alternatives_only = parts.copy()
    
    if len(last_part_words) > 1:
        first_word_of_last = last_part_words[0]
        
        # Проверяем, есть ли это слово в других частях
        found_in_others = False
        for part in parts[:-1]:
            if first_word_of_last.lower() in part.lower():
                found_in_others = True
                break
        
        # Если первое слово последней части НЕ найдено в других,
        # значит всё после первого слова - общие слова
        if not found_in_others:
            alternatives_only[-1] = first_word_of_last
            common_suffix = ' '.join(last_part_words[1:])
    
    # НОВОЕ: Формируем основной товар и альтернативы С СОГЛАСОВАНИЕМ ПО РОДУ
    main_product_name = alternatives_only[0].strip()
    
    # Определяем род основного продукта (для отладки)
    main_gender = get_product_gender(main_product_name)
    
    # Основной товар - просто добавляем суффикс
    if common_suffix:
        main_product = f"{main_product_name} {common_suffix}"
    else:
        main_product = main_product_name
    
    # Альтернативы - согласуем прилагательные с родом каждого продукта
    alternatives = []
    for alt in alternatives_only[1:]:
        alt_clean = alt.strip()
        if alt_clean:
            if common_suffix:
                # КЛЮЧЕВОЙ МОМЕНТ: согласуем суффикс с родом альтернативы
                agreed_suffix = apply_gender_agreement(alt_clean, common_suffix, main_gender)
                alternatives.append(f"{alt_clean} {agreed_suffix}")
            else:
                alternatives.append(alt_clean)
    
    return {
        "main": main_product,
        "alternatives": alternatives,
        "has_alternatives": len(alternatives) > 0,
        "full_text": text,
        "all_options": [main_product] + alternatives,
        "common_suffix": common_suffix,  # Для отладки
        "main_gender": main_gender  # Для отладки
    }


def extract_product_name_from_alternative(alternative_text: str, quantity_unit: str = None) -> str:
    """
    Извлекает чистое название товара из альтернативы, удаляя количество и единицы
    
    Args:
        alternative_text: Текст альтернативы (может содержать количество)
        quantity_unit: Известное количество с единицей ("500г", "1кг"), если есть
        
    Returns:
        Чистое название товара
    """
    if quantity_unit:
        text = alternative_text.replace(quantity_unit, '').strip()
    else:
        text = alternative_text.strip()
    
    # Удаляем типичные паттерны количества
    text = re.sub(r'\d+[\.,]?\d*\s*(г|кг|л|мл|шт|упак)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def normalize_alternatives_for_search(alternatives_data: Dict) -> List[str]:
    """
    Нормализует список альтернатив для поиска
    Возвращает список чистых названий товаров без количества
    
    Args:
        alternatives_data: Результат parse_alternatives()
        
    Returns:
        Список нормализованных названий для поиска
    """
    if not alternatives_data["has_alternatives"]:
        return [alternatives_data["main"]]
    
    search_names = []
    main = alternatives_data["main"]
    
    # Находим количество в основном товаре
    quantity_match = re.search(r'\d+[\.,]?\d*\s*(г|кг|л|мл|шт|упак)', main, flags=re.IGNORECASE)
    quantity_unit = quantity_match.group(0) if quantity_match else None
    
    # Добавляем основной товар (очищенный)
    main_clean = extract_product_name_from_alternative(main, quantity_unit)
    if main_clean:
        search_names.append(main_clean)
    
    # Добавляем альтернативы (очищенные)
    for alt in alternatives_data["alternatives"]:
        alt_clean = extract_product_name_from_alternative(alt, quantity_unit)
        if alt_clean and alt_clean not in search_names:
            search_names.append(alt_clean)
    
    return search_names


def test_alternatives_parser():
    """Тестирование парсера альтернатив с согласованием по роду"""
    test_cases = [
        # Тест 1: Простые альтернативы без общих слов
        {
            "input": "форель / семга 500г",
            "expected_main": "форель 500г",
            "expected_alternatives": ["семга 500г"]
        },
        
        # Тест 2: Альтернативы с согласованием (ключевой тест!)
        {
            "input": "форель / семга / лосось слабосоленая русское море",
            "expected_main": "форель слабосоленая русское море",
            "expected_alternatives": [
                "семга слабосоленая русское море",  # ж.р., не меняется
                "лосось слабосоленый русское море"  # м.р., ДОЛЖНО ИЗМЕНИТЬСЯ!
            ]
        },
        
        # Тест 3: Средний род -> мужской
        {
            "input": "молоко / кефир цельное 3.2%",
            "expected_main": "молоко цельное 3.2%",
            "expected_alternatives": ["кефир цельный 3.2%"]
        },
        
        # Тест 4: Без альтернатив
        {
            "input": "молоко 3.2% 1л",
            "expected_main": "молоко 3.2% 1л",
            "expected_alternatives": []
        },
    ]
    
    print("🧪 Testing alternatives parser with gender agreement:")
    print("=" * 80)
    
    all_passed = True
    
    for i, test in enumerate(test_cases, 1):
        parsed = parse_alternatives(test["input"])
        
        main_match = parsed["main"] == test["expected_main"]
        alt_match = parsed["alternatives"] == test["expected_alternatives"]
        
        passed = main_match and alt_match
        all_passed = all_passed and passed
        
        status = "✅ PASS" if passed else "❌ FAIL"
        
        print(f"\nTest {i}: {status}")
        print(f"  Input: '{test['input']}'")
        print(f"  Main: '{parsed['main']}'")
        if not main_match:
            print(f"    ❌ Expected: '{test['expected_main']}'")
        print(f"  Alternatives: {parsed['alternatives']}")
        if not alt_match:
            print(f"    ❌ Expected: {test['expected_alternatives']}")
        
        if 'main_gender' in parsed:
            print(f"  Main gender: {parsed['main_gender']}")
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ All tests PASSED!")
    else:
        print("❌ Some tests FAILED")
    print("=" * 80)


if __name__ == "__main__":
    test_alternatives_parser()
