"""
Модуль для работы с единицами измерения
"""

import logging

logger = logging.getLogger(__name__)

# Список упаковочных единиц для яиц и других штучных товаров
PACKAGE_UNITS = ['шт', 'уп', 'упак', 'упаковка', 'пач', 'пачка']


def get_base_unit(unit: str, egg_category: str = None) -> str:
    """
    Определение базовой единицы измерения для категории
    
    Args:
        unit: Единица измерения
        egg_category: Категория яиц (опционально) - если передана, яйца в упаковочных единицах будут преобразованы в кг
        
    Returns:
        Базовая единица (кг, л или шт)
    """
    
    # Проверка на None
    if unit is None:
        return 'шт'  # Дефолтное значение для None
    
    unit = unit.lower().strip()
    
    # СПЕЦИАЛЬНАЯ ОБРАБОТКА ЯИЦ: яйца в любых упаковочных единицах должны быть в килограммах
    if egg_category and unit in PACKAGE_UNITS:
        logger.info(f"🥚 Egg category '{egg_category}' detected with unit='{unit}' -> base_unit='кг'")
        return 'кг'
    
    # Весовые единицы -> кг
    if unit in ['г', 'гр', 'грамм', 'кг']:
        return 'кг'
    
    # Объемные единицы -> л
    if unit in ['мл', 'л', 'литр']:
        return 'л'
    
    # Все остальное -> шт
    return 'шт'


def convert_to_base_unit(quantity: float, unit: str, base_unit: str, egg_category: str = None) -> float:
    """
    Конвертация количества в базовую единицу измерения
    
    Args:
        quantity: Количество
        unit: Исходная единица
        base_unit: Целевая базовая единица
        egg_category: Категория яиц (опционально) - для конвертации упаковочных единиц яиц в килограммы
        
    Returns:
        Количество в базовых единицах
    """
    
    # Проверка на None
    if unit is None:
        return quantity  # Возвращаем как есть
    
    unit = unit.lower().strip()
    
    # СПЕЦИАЛЬНАЯ ОБРАБОТКА ЯИЦ В УПАКОВОЧНЫХ ЕДИНИЦАХ -> КИЛОГРАММЫ
    if egg_category and unit in PACKAGE_UNITS and base_unit == 'кг':
        from shared.utils.egg_categories import get_egg_weight_kg
        egg_weight_kg = get_egg_weight_kg(egg_category)
        result = quantity * egg_weight_kg
        logger.info(f"🥚 Converting eggs to kg: {quantity} {unit} * {egg_weight_kg} kg/pc = {result} kg (category: {egg_category})")
        return result
    
    if base_unit == 'кг':
        if unit == 'г':
            return quantity / 1000.0
        elif unit == 'кг':
            return quantity
        else:
            return quantity  # Неизвестная единица, оставляем как есть
    
    elif base_unit == 'л':
        if unit == 'мл':
            return quantity / 1000.0
        elif unit == 'л':
            return quantity
        else:
            return quantity
    
    # Для штук базовая единица = исходная
    return quantity


def detect_weight_unit_from_price(found_name: str, price: float, found_unit: str) -> tuple[str, float]:
    """
    Определяет реальную единицу измерения для весовых товаров без явной единицы.
    
    Логика:
    - Проверяет наличие ключевых слов ("вес", "весовой", "весовая") в названии
    - Проверяет что found_unit == "шт" (неинформативная единица)
    - На основе порогового значения цены определяет:
      - price <= 300₽ → base_unit="г", base_quantity=100 (цена за 100г)
      - price > 300₽ → base_unit="г", base_quantity=1000 (цена за кг)
    
    Args:
        found_name: Название товара (проверяем на ключевые слова)
        price: Цена товара
        found_unit: Распознанная единица измерения из парсинга
        
    Returns:
        tuple[base_unit, base_quantity]: 
            - Если это весовой товар БЕЗ единицы → определяем из цены
            - Иначе возвращаем (None, None) для использования стандартной логики
    
    Examples:
        >>> detect_weight_unit_from_price("Конфеты Мишки в лесу, вес", 69.9, "шт")
        ("г", 100)
        
        >>> detect_weight_unit_from_price("Говядина вырезка, вес", 890, "шт")
        ("г", 1000)
        
        >>> detect_weight_unit_from_price("Молоко 1л", 85, "л")
        (None, None)  # не весовой, используем стандартную логику
    """
    
    # Импортируем settings для получения параметров
    from config.settings import settings
    
    threshold = settings.weight_unit_price_threshold
    keywords = settings.weight_keywords_list
    
    # Проверка на None
    if found_name is None or found_unit is None:
        return None, None
    
    # Приводим название к нижнему регистру для проверки
    name_lower = found_name.lower()
    
    # Проверка 1: Есть ли ключевые слова в названии?
    has_weight_keyword = any(keyword.lower() in name_lower for keyword in keywords)
    
    # Проверка 2: Единица измерения неинформативная ("шт")?
    is_uninformative_unit = found_unit and found_unit.lower().strip() == 'шт'
    
    # Если оба условия выполнены - это весовой товар без единицы
    if has_weight_keyword and is_uninformative_unit:
        logger.info(f"🔍 Weight product detected: '{found_name}' (price={price}₽, threshold={threshold}₽)")
        
        if price <= threshold:
            # Цена за 100г
            base_unit = "г"
            base_quantity = 100.0
            logger.info(f"✅ Price <= {threshold}₽ → base_unit='г', base_quantity=100 (price per 100g)")
        else:
            # Цена за кг
            base_unit = "г"
            base_quantity = 1000.0
            logger.info(f"✅ Price > {threshold}₽ → base_unit='г', base_quantity=1000 (price per kg)")
        
        return base_unit, base_quantity
    
    # Не весовой товар или есть явная единица - используем стандартную логику
    return None, None
