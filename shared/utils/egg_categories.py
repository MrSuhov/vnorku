"""
Утилиты для работы с категориями яиц
"""

import re
from typing import Optional, Tuple

# Категории яиц и их вес относительно категории СВ (80г = 100%)
EGG_CATEGORIES = {
    'СВ': 1.0,        # 80г - базовая категория (высшая)
    'СО': 0.875,      # 70г (87.5% от СВ)
    'С0': 0.875,      # альтернативное написание
    'С1': 0.75,       # 60г (75% от СВ)
    'С2': 0.625,      # 50г (62.5% от СВ)
    'С3': 0.5,        # 40г (50% от СВ)
    'ПЕРЕПЕЛИНОЕ': 0.1375,  # 11г (13.75% от СВ)
}

# Вес одного яйца для каждой категории (в килограммах)
EGG_WEIGHTS_KG = {
    'СВ': 0.080,       # 80г
    'СО': 0.070,       # 70г
    'С0': 0.070,       # альтернативное написание
    'С1': 0.060,       # 60г
    'С2': 0.050,       # 50г
    'С3': 0.040,       # 40г
    'ПЕРЕПЕЛИНОЕ': 0.011,  # 11г
}


def extract_egg_count_from_name(product_name: str) -> int:
    """
    Извлечение количества яиц из названия товара
    
    Args:
        product_name: Название товара
        
    Returns:
        Количество яиц или дефолтное значение
    
    Примеры:
    - "Яйцо перепелиное 20шт" -> 20
    - "Яйцо куриное 10 шт" -> 10
    - "Яйцо С0" -> 10 (по умолчанию для куриных)
    - "Яйцо перепелиное" -> 20 (по умолчанию для перепелиных)
    """
    if not product_name:
        return 10
    
    # Убираем невидимые символы
    clean_name = re.sub(r'[\u00AD\u200B-\u200D\uFEFF]', '', product_name)
    
    # Паттерны для поиска количества штук
    patterns = [
        r'(\d+)\s*шт',     # "20шт", "10 шт"
        r'(\d+)\s*шт\.',   # "20шт."
        r'(\d+)\s*штук',   # "20 штук"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, clean_name, re.IGNORECASE)
        if match:
            try:
                count = int(match.group(1))
                if 1 <= count <= 100:  # Разумный диапазон
                    return count
            except ValueError:
                continue
    
    # По умолчанию: 20 для перепелиных, 10 для куриных
    return 20 if 'перепел' in clean_name.lower() else 10


def extract_egg_category(product_name: str) -> Optional[str]:
    """
    Извлечение категории яиц из названия товара
    
    Args:
        product_name: Название товара
        
    Returns:
        Категория яиц ('СВ', 'С0', 'С1', 'С2', 'С3', 'ПЕРЕПЕЛИНОЕ') или None
    """
    if not product_name:
        return None
    
    # Убираем невидимые символы (мягкие переносы и т.д.)
    clean_name = re.sub(r'[\u00AD\u200B-\u200D\uFEFF]', '', product_name)
    
    # Проверяем что это яйца
    name_lower = clean_name.lower()
    if 'яйц' not in name_lower and 'яйк' not in name_lower:
        return None
    
    # ПРИОРИТЕТ 1: Проверяем перепелиные яйца
    if 'перепел' in name_lower:
        return 'ПЕРЕПЕЛИНОЕ'
    
    # ПРИОРИТЕТ 2: Ищем категорию куриных яиц
    # Паттерны: "С0", "С1", "СО", "СВ", "Высшая" (кириллица и латиница)
    patterns = [
        # Кириллические паттерны
        r'\bС0\b',
        r'\bСО\b', 
        r'\bС1\b',
        r'\bС2\b',
        r'\bС3\b',
        r'\bСВ\b',
        r'высш',
        # Латинские паттерны (часто встречаются в названиях)
        r'\bC0\b',  # латинская C
        r'\bCO\b',  # латинская C и O
        r'\bC1\b',
        r'\bC2\b',
        r'\bC3\b',
        r'\bCB\b',  # CB - латинский аналог СВ
    ]
    
    for pattern in patterns:
        match = re.search(pattern, clean_name, re.IGNORECASE)
        if match:
            category = match.group(0).upper()
            # Нормализуем варианты написания
            if category in ['ВЫСШ', 'ВЫСШАЯ', 'ВЫСШЕЙ']:
                return 'СВ'
            # Нормализуем латинские буквы в кириллические
            if category in ['C0', 'CO', 'C1', 'C2', 'C3', 'CB']:
                # Заменяем латинскую C на кириллическую С
                category = category.replace('C', 'С')
                # CB -> СВ
                if category == 'СB':
                    category = 'СВ'
                # CO -> СО
                if category == 'СO':
                    category = 'СО'
            return category
    
    return None


def get_egg_category_coefficient(product_name: str) -> float:
    """
    Получить коэффициент для пересчета цены яиц к категории СВ
    
    Args:
        product_name: Название товара
        
    Returns:
        Коэффициент пересчета (1.0 для не-яиц или СВ категории)
    """
    category = extract_egg_category(product_name)
    
    if not category:
        return 1.0  # Не яйца или категория не определена
    
    return EGG_CATEGORIES.get(category, 1.0)


def get_egg_weight_kg(category: str) -> float:
    """
    Получить вес одного яйца в килограммах
    
    Args:
        category: Категория яиц
        
    Returns:
        Вес одного яйца в кг
    """
    return EGG_WEIGHTS_KG.get(category, 0.070)  # дефолт 70г (СО)

def is_quail_egg(product_name: str) -> bool:
    """
    Проверка, является ли товар перепелиными яйцами
    
    Args:
        product_name: Название товара
        
    Returns:
        True если перепелиные яйца
    """
    if not product_name:
        return False
    name_lower = product_name.lower()
    return 'перепел' in name_lower

def normalize_egg_price(
    product_name: str, 
    price_per_item: float
) -> Tuple[float, Optional[str]]:
    """
    Нормализация цены яиц к базовой категории СВ
    
    Args:
        product_name: Название товара
        price_per_item: Цена за штуку
        
    Returns:
        (normalized_price, category) - нормализованная цена и категория
    
    Примеры:
    - С3 (40г, коэф=0.5) 5₽/шт -> normalized = 5 / 0.5 = 10₽ эквивалента СВ
    - СВ (80г, коэф=1.0) 10₽/шт -> normalized = 10 / 1.0 = 10₽ эквивалента СВ
    """
    category = extract_egg_category(product_name)
    
    if not category:
        return price_per_item, None
    
    coefficient = EGG_CATEGORIES.get(category, 1.0)
    
    # Пересчитываем: делим на коэффициент
    if coefficient > 0:
        normalized_price = price_per_item / coefficient
    else:
        normalized_price = price_per_item
    
    return normalized_price, category
