"""
Модуль для расчета order_item_ids_quantity и order_item_ids_cost
ИСПРАВЛЕННАЯ ВЕРСИЯ
"""

import logging
from typing import Tuple, Optional
from decimal import Decimal
import math

logger = logging.getLogger(__name__)

def normalize_to_base_unit(quantity: float, unit: str) -> float:
    """
    Приводит количество к базовым единицам (кг для веса, л для объема)
    
    Args:
        quantity: Количество
        unit: Единица измерения
    
    Returns:
        Количество в базовых единицах
    """
    # Преобразование в базовые единицы
    if unit == 'г':
        return quantity / 1000  # граммы в килограммы
    elif unit == 'мл':
        return quantity / 1000  # миллилитры в литры
    elif unit in ['кг', 'л', 'шт']:
        return quantity  # уже в базовых единицах
    else:
        return quantity  # для неизвестных единиц

def calculate_order_quantity(
    requested_quantity: float,
    requested_unit: str,
    base_quantity: float,
    base_unit: str,
    price: float,
    over_order_percent: int = 50,
    under_order_percent: int = 10
) -> Tuple[Optional[int], Optional[float]]:
    """
    Рассчитывает количество товаров для заказа и их стоимость
    
    Args:
        requested_quantity: Запрошенное количество товара
        requested_unit: Единица измерения запроса (г, кг, л, мл, шт и т.д.)
        base_quantity: Количество в базовых единицах для одной штуки товара
        base_unit: Единица измерения base_quantity (кг, л, шт)
        price: Цена за единицу товара
        over_order_percent: Допустимое превышение заказа в процентах (default: 50)
        under_order_percent: Допустимое недополучение заказа в процентах (default: 10)
    
    Returns:
        Tuple[order_item_ids_quantity, order_item_ids_cost]
        - order_item_ids_quantity = -1: минимальная упаковка превышает over_order_percent
        - order_item_ids_quantity = 1: одна упаковка в пределах under_order_percent от запрошенного
        - order_item_ids_quantity >= 1: расчет по ceiling с проверкой max_pieces
    """
    
    try:
        # Проверяем входные данные
        if not requested_quantity or not base_quantity or base_quantity <= 0:
            logger.warning(f"Invalid input data: requested_quantity={requested_quantity}, base_quantity={base_quantity}")
            return None, None
        
        # Определяем, является ли единица измерения весовой/объемной или штучной
        weight_volume_units = {'л', 'мл', 'г', 'кг'}
        piece_units = {'шт', 'штука', 'штук', 'пач', 'пачка', 'упак', 'упаковка'}
        
        # Если единица штучная - используем requested_quantity напрямую
        if requested_unit in piece_units:
            order_quantity = int(requested_quantity)
            order_cost = round(order_quantity * price, 2)
            
            logger.info(f"📦 Piece unit '{requested_unit}': quantity={order_quantity}, cost={order_cost}")
            return order_quantity, order_cost
        
        # Для весовых/объемных единиц приводим к базовым единицам
        requested_in_base = normalize_to_base_unit(requested_quantity, requested_unit)
        
        logger.debug(f"📊 Normalized: {requested_quantity}{requested_unit} → {requested_in_base}{base_unit}")
        
        # НОВАЯ ПРОВЕРКА: Если одна упаковка немного меньше запрошенного (в пределах under_order_percent)
        min_acceptable_quantity = requested_in_base * (1 - under_order_percent / 100)
        
        if base_quantity < requested_in_base and base_quantity >= min_acceptable_quantity:
            # Одна штука меньше, но в пределах допустимого недополучения
            order_cost = round(price, 2)
            logger.info(
                f"✅ Single package ({base_quantity}{base_unit}) is within -{under_order_percent}% "
                f"tolerance of requested ({requested_in_base}{base_unit}), using 1 piece"
            )
            return 1, order_cost
        
        # Рассчитываем диапазон с учетом over_order_percent
        over_requested_quantity = requested_in_base * (1 + over_order_percent / 100)
        
        # Проверяем, не превышает ли минимальная упаковка (1 штука) максимально допустимое количество
        if base_quantity > over_requested_quantity:
            # Минимальная упаковка уже больше чем нужно с учетом over_order_percent
            logger.warning(f"⚠️ Single package ({base_quantity}{base_unit}) exceeds max allowed ({over_requested_quantity:.2f}{base_unit})")
            logger.warning(f"⚠️ Setting order_item_ids_quantity = -1 to indicate oversized package")
            return -1, None  # -1 как индикатор превышения
        
        # Минимум: сколько штук нужно чтобы получить requested_quantity
        min_pieces = requested_in_base / base_quantity
        max_pieces = over_requested_quantity / base_quantity
        
        logger.debug(f"📊 Calculation: requested={requested_in_base}{base_unit}, base={base_quantity}{base_unit}, over={over_order_percent}%")
        logger.debug(f"📊 Range: min_pieces={min_pieces:.2f}, max_pieces={max_pieces:.2f}")
        
        # Берем минимальное целое число >= min_pieces и <= max_pieces
        # Но не меньше 1
        order_quantity = math.ceil(min_pieces)
        
        # Проверяем, что не превышаем максимум
        if order_quantity > max_pieces:
            order_quantity = math.floor(max_pieces)
            
        # Минимум 1 штука
        if order_quantity < 1:
            order_quantity = 1
            
        # Рассчитываем стоимость
        order_cost = round(order_quantity * price, 2)
        
        logger.info(f"✅ Calculated for {requested_quantity}{requested_unit}: "
                   f"order_quantity={order_quantity} pcs (range: {min_pieces:.1f}-{max_pieces:.1f}), "
                   f"cost={order_cost}₽")
        
        return order_quantity, order_cost
        
    except Exception as e:
        logger.error(f"❌ Error calculating order quantity: {e}")
        return None, None

# Тест для проверки
if __name__ == "__main__":
    print("=" * 80)
    print("ТЕСТИРОВАНИЕ calculate_order_quantity")
    print("=" * 80)
    
    # Тест 1: Основной кейс - 900 мл вместо 1 л (within -10%)
    print("\nТест 1: 900мл вместо 1л (в пределах -10%)")
    result = calculate_order_quantity(
        requested_quantity=1,
        requested_unit='л',
        base_quantity=0.9,
        base_unit='л',
        price=100,
        under_order_percent=10
    )
    print(f"Результат: quantity={result[0]}, cost={result[1]}")
    print(f"Ожидаем: quantity=1, cost=100.0 ✓" if result == (1, 100.0) else f"ОЖИДАЛИ (1, 100.0) ✗")
    
    # Тест 2: Граница -10% (ровно 900г вместо 1000г)
    print("\nТест 2: 900г вместо 1000г (граница -10%)")
    result = calculate_order_quantity(
        requested_quantity=1000,
        requested_unit='г',
        base_quantity=0.9,
        base_unit='кг',
        price=200,
        under_order_percent=10
    )
    print(f"Результат: quantity={result[0]}, cost={result[1]}")
    print(f"Ожидаем: quantity=1, cost=200.0 ✓" if result == (1, 200.0) else f"ОЖИДАЛИ (1, 200.0) ✗")
    
    # Тест 3: Меньше -10% (850 мл вместо 1 л)
    # Примечание: 2 штуки по 0.85л = 1.7л, что превышает over_order_percent (1.5л),
    # поэтому берется floor(max_pieces) = 1 штука
    print("\nТест 3: 850мл вместо 1л (меньше -10%, но 2 шт превышают +50%)")
    result = calculate_order_quantity(
        requested_quantity=1,
        requested_unit='л',
        base_quantity=0.85,
        base_unit='л',
        price=100,
        under_order_percent=10
    )
    print(f"Результат: quantity={result[0]}, cost={result[1]}")
    print(f"Ожидаем: quantity=1, cost=100.0 ✓" if result == (1, 100.0) else f"ОЖИДАЛИ (1, 100.0) ✗")
    
    # Тест 4: Больше запрошенного (не затрагивается under_order_percent)
    print("\nТест 4: 1.05л вместо 1л (больше запрошенного)")
    result = calculate_order_quantity(
        requested_quantity=1,
        requested_unit='л',
        base_quantity=1.05,
        base_unit='л',
        price=100,
        under_order_percent=10
    )
    print(f"Результат: quantity={result[0]}, cost={result[1]}")
    print(f"Ожидаем: quantity=1, cost=100.0 ✓" if result == (1, 100.0) else f"ОЖИДАЛИ (1, 100.0) ✗")
    
    # Тест 5: Колбаса 300г (старый тест)
    print("\nТест 5: Колбаса 300г (точное совпадение)")
    result = calculate_order_quantity(
        requested_quantity=300,
        requested_unit='г',
        base_quantity=0.3,  # 300г = 0.3кг
        base_unit='кг',
        price=379,
        over_order_percent=50
    )
    print(f"Результат: quantity={result[0]}, cost={result[1]}")
    print(f"Ожидаем: quantity=1, cost=379.0 ✓" if result == (1, 379.0) else f"ОЖИДАЛИ (1, 379.0) ✗")
    
    # Тест 6: Правильный кейс для ceiling - 700мл вместо 1л
    # 700мл < 900мл (-10% порог), 2 шт * 0.7л = 1.4л <= 1.5л (+50%)
    print("\nТест 6: 700мл вместо 1л (меньше -10%, 2 шт в пределах +50%)")
    result = calculate_order_quantity(
        requested_quantity=1,
        requested_unit='л',
        base_quantity=0.7,
        base_unit='л',
        price=100,
        under_order_percent=10
    )
    print(f"Результат: quantity={result[0]}, cost={result[1]}")
    print(f"Ожидаем: quantity=2, cost=200.0 ✓" if result == (2, 200.0) else f"ОЖИДАЛИ (2, 200.0) ✗")
    
    print("\n" + "=" * 80)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 80)
