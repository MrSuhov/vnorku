"""
Модуль для расчета order_item_ids_quantity и order_item_ids_cost
"""

import logging
from typing import Tuple, Optional
from decimal import Decimal
import math

logger = logging.getLogger(__name__)

def calculate_order_quantity(
    requested_quantity: float,
    requested_unit: str,
    base_quantity: float,
    price: float,
    over_order_percent: int = 50
) -> Tuple[Optional[int], Optional[float]]:
    """
    Рассчитывает количество товаров для заказа и их стоимость
    
    Args:
        requested_quantity: Запрошенное количество товара
        requested_unit: Единица измерения запроса (г, кг, л, мл, шт и т.д.)
        base_quantity: Количество в базовых единицах для одной штуки товара
        price: Цена за единицу товара
        over_order_percent: Допустимое превышение заказа в процентах
    
    Returns:
        Tuple[order_item_ids_quantity, order_item_ids_cost]
        Если order_item_ids_quantity = -1, значит минимальная упаковка превышает допустимый максимум
    """
    
    try:
        # Проверяем входные данные
        if not requested_quantity or not base_quantity or base_quantity <= 0:
            logger.warning(f"Invalid input data: requested_quantity={requested_quantity}, base_quantity={base_quantity}")
            return None, None
        
        # Определяем, является ли единица измерения весовой/объемной
        weight_volume_units = {'л', 'мл', 'г', 'кг'}
        
        # Если единица НЕ весовая/объемная - используем requested_quantity напрямую
        if requested_unit not in weight_volume_units:
            order_quantity = int(requested_quantity)
            order_cost = round(order_quantity * price, 2)
            
            logger.info(f"📦 Non-weight unit '{requested_unit}': quantity={order_quantity}, cost={order_cost}")
            return order_quantity, order_cost
        
        # Для весовых/объемных единиц рассчитываем диапазон
        # Максимум: с учетом over_order_percent
        over_requested_quantity = requested_quantity * (1 + over_order_percent / 100)
        
        # Проверяем, не превышает ли минимальная упаковка (1 штука) максимально допустимое количество
        if base_quantity > over_requested_quantity:
            # Минимальная упаковка уже больше чем нужно с учетом over_order_percent
            logger.warning(f"⚠️ Single package ({base_quantity}) exceeds max allowed ({over_requested_quantity:.2f})")
            logger.warning(f"⚠️ Setting order_item_ids_quantity = -1 to indicate oversized package")
            return -1, None  # -1 как индикатор превышения
        
        # Минимум: сколько штук нужно чтобы получить requested_quantity
        min_pieces = requested_quantity / base_quantity
        max_pieces = over_requested_quantity / base_quantity
        
        logger.debug(f"📊 Calculation: requested={requested_quantity}{requested_unit}, base={base_quantity}, over={over_order_percent}%")
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
