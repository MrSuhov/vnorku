"""
Модуль оптимизации корзин заказов
Подбор оптимального распределения товаров по сервисам доставки
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from shared.database.models import (
    Order as DBOrder,
    OrderItem as DBOrderItem,
    LSDStock as DBLSDStock,
    LSDConfig as DBLSDConfig,
    OrderBasket as DBOrderBasket,
    OrderBasketItem as DBOrderBasketItem
)

logger = logging.getLogger(__name__)


class DeliveryCalculator:
    """Калькулятор стоимости доставки"""
    
    @staticmethod
    def calculate_delivery_fee(cart_amount: Decimal, delivery_model: Dict[str, Any], min_order_amount: Decimal = Decimal('0')) -> Tuple[Decimal, str]:
        """
        Расчет стоимости доставки
        
        Args:
            cart_amount: Сумма корзины
            delivery_model: Модель доставки с диапазонами
            min_order_amount: Минимальная сумма заказа
            
        Returns:
            (delivery_fee, label) - стоимость доставки и метка диапазона
        """
        # Если есть минималка и сумма меньше - возвращаем доплату до минималки
        if min_order_amount > 0 and cart_amount < min_order_amount:
            return (min_order_amount - cart_amount, "D1")
        
        # Если модель доставки не задана - бесплатная доставка
        if not delivery_model or 'delivery_cost' not in delivery_model:
            return (Decimal('0'), "FREE")
        
        # Ищем подходящий диапазон
        for range_item in delivery_model['delivery_cost']:
            min_val = Decimal(str(range_item.get('min', 0)))
            max_val = Decimal(str(range_item['max'])) if range_item.get('max') is not None else None
            fee = Decimal(str(range_item.get('fee', 0)))
            label = range_item.get('label', 'D')
            
            # Проверяем вхождение в диапазон
            if max_val is None:
                # Открытый диапазон сверху
                if cart_amount >= min_val:
                    return (fee, label)
            else:
                # Закрытый диапазон
                if min_val <= cart_amount < max_val:
                    return (fee, label)
        
        # Если не нашли диапазон - бесплатная доставка
        return (Decimal('0'), "UNKNOWN")


class BasketOptimizer:
    """Оптимизатор корзин с учетом стоимости доставки"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.delivery_calc = DeliveryCalculator()
    
    async def optimize_order_baskets(self, order_id: int) -> Dict[str, Any]:
        """
        Оптимизация корзин заказа
        
        Args:
            order_id: ID заказа
            
        Returns:
            Результаты оптимизации с распределением товаров по DS
        """
        logger.info(f"🎯 Starting basket optimization for order {order_id}")
        
        # Получаем все lsd_stocks для заказа
        stocks_result = await self.db.execute(
            select(
                DBLSDStock,
                DBOrderItem,
                DBLSDConfig.id,
                DBLSDConfig.name,
                DBLSDConfig.display_name
            )
            .join(DBOrderItem, DBLSDStock.order_item_id == DBOrderItem.id)
            .join(DBLSDConfig, DBLSDStock.lsd_config_id == DBLSDConfig.id)
            .where(DBLSDStock.order_id == order_id)
            .order_by(DBOrderItem.id, DBLSDStock.fprice)  # Сортируем по fprice для каждого товара
        )
        
        stocks_data = stocks_result.all()
        
        if not stocks_data:
            logger.warning(f"⚠️ No stocks found for order {order_id}")
            return {"success": False, "error": "No stocks found"}
        
        # Группируем по order_item_id
        items_stocks = {}
        for stock, order_item, lsd_id, lsd_name, lsd_display_name in stocks_data:
            if order_item.id not in items_stocks:
                items_stocks[order_item.id] = {
                    "order_item": order_item,
                    "stocks": []
                }
            
            # Создаём объект-заглушку для lsd_config
            lsd_config_dict = {
                "id": lsd_id,
                "name": lsd_name,
                "display_name": lsd_display_name
            }
            
            items_stocks[order_item.id]["stocks"].append({
                "stock": stock,
                "lsd": lsd_config_dict
            })
        
        logger.info(f"📊 Found {len(items_stocks)} items with stocks from multiple DS")
        
        # Применяем жадный алгоритм с учетом доставки
        optimal_baskets = await self._greedy_optimization(items_stocks)
        
        # Сохраняем результаты в БД
        await self._save_optimized_baskets(order_id, optimal_baskets)
        
        return {
            "success": True,
            "order_id": order_id,
            "baskets": optimal_baskets,
            "total_cost": sum(b["total_with_delivery"] for b in optimal_baskets.values())
        }
    
    async def _greedy_optimization(self, items_stocks: Dict[int, Dict]) -> Dict[int, Dict]:
        """
        Жадный алгоритм оптимизации с учетом доставки
        
        Логика:
        1. Для каждого товара выбираем самый дешевый вариант по fprice
        2. Группируем товары по DS
        3. Рассчитываем стоимость доставки для каждой корзины
        4. Пересчитываем с учетом доставки и перераспределяем при необходимости
        """
        baskets = {}  # {lsd_config_id: {"items": [...], "subtotal": Decimal, "delivery": Decimal}}
        
        # Шаг 1: Жадный выбор - берем самый дешевый вариант для каждого товара
        for item_id, item_data in items_stocks.items():
            order_item = item_data["order_item"]
            stocks = item_data["stocks"]
            
            if not stocks:
                logger.warning(f"⚠️ No stocks for item {item_id}")
                continue
            
            # Берем первый (самый дешевый по fprice из-за сортировки)
            best_option = stocks[0]
            stock = best_option["stock"]
            lsd = best_option["lsd"]
            
            # Рассчитываем стоимость товара
            # Количество = requested_quantity из order_item
            quantity_to_order = order_item.requested_quantity
            item_total = stock.fprice * quantity_to_order
            
            # Добавляем в корзину
            lsd_id = lsd["id"]
            if lsd_id not in baskets:
                baskets[lsd_id] = {
                    "lsd": lsd,
                    "items": [],
                    "subtotal": Decimal('0'),
                    "delivery_model": stock.delivery_cost_model or {},
                    "min_order_amount": stock.min_order_amount or Decimal('0')
                }
            
            baskets[lsd_id]["items"].append({
                "stock": stock,
                "order_item": order_item,
                "quantity": quantity_to_order,
                "item_total": item_total
            })
            baskets[lsd_id]["subtotal"] += item_total
        
        # Шаг 2: Рассчитываем доставку для каждой корзины
        for lsd_id, basket in baskets.items():
            delivery_fee, delivery_label = self.delivery_calc.calculate_delivery_fee(
                cart_amount=basket["subtotal"],
                delivery_model=basket["delivery_model"],
                min_order_amount=basket["min_order_amount"]
            )
            
            basket["delivery_fee"] = delivery_fee
            basket["delivery_label"] = delivery_label
            basket["total_with_delivery"] = basket["subtotal"] + delivery_fee
            
            logger.info(
                f"🛒 Basket for {basket['lsd']['display_name']}: "
                f"subtotal={basket['subtotal']:.2f}, "
                f"delivery={delivery_fee:.2f} ({delivery_label}), "
                f"total={basket['total_with_delivery']:.2f}"
            )
        
        # TODO: Шаг 3 (будущее улучшение) - пересмотр распределения
        # Если добавление товара в другую корзину уменьшает общую стоимость доставки
        
        return baskets
    
    async def _save_optimized_baskets(self, order_id: int, optimal_baskets: Dict[int, Dict]):
        """Сохранение оптимизированных корзин в БД"""
        logger.info(f"💾 Saving {len(optimal_baskets)} optimized baskets for order {order_id}")
        
        # Удаляем старые корзины если есть
        existing_baskets = await self.db.execute(
            select(DBOrderBasket).where(DBOrderBasket.order_id == order_id)
        )
        for old_basket in existing_baskets.scalars().all():
            await self.db.delete(old_basket)
        
        await self.db.flush()
        
        # Создаем новые корзины
        for lsd_id, basket_data in optimal_baskets.items():
            lsd = basket_data["lsd"]
            
            # Создаем OrderBasket
            order_basket = DBOrderBasket(
                order_id=order_id,
                lsd_config_id=lsd_id,
                subtotal=basket_data["subtotal"],
                delivery_cost=basket_data["delivery_fee"],
                min_order_amount=basket_data.get("min_order_amount"),
                total_before_promo=basket_data["total_with_delivery"],
                total_after_promo=basket_data["total_with_delivery"],  # Пока без промо
                status='optimized'
            )
            
            self.db.add(order_basket)
            await self.db.flush()  # Получаем ID корзины
            
            # Создаем OrderBasketItem для каждого товара
            for item in basket_data["items"]:
                basket_item = DBOrderBasketItem(
                    order_basket_id=order_basket.id,
                    lsd_stock_id=item["stock"].id,
                    quantity_to_order=item["quantity"],
                    unit_price=item["stock"].fprice,
                    total_price=item["item_total"]
                )
                self.db.add(basket_item)
            
            logger.info(
                f"  ✅ Saved basket for {lsd['display_name']}: "
                f"{len(basket_data['items'])} items, total={basket_data['total_with_delivery']:.2f}"
            )
        
        await self.db.commit()
        logger.info(f"✅ All baskets saved for order {order_id}")


async def optimize_order_baskets(order_id: int, db: AsyncSession) -> Dict[str, Any]:
    """
    Основная функция оптимизации корзин заказа
    
    Args:
        order_id: ID заказа
        db: Сессия базы данных
        
    Returns:
        Результаты оптимизации
    """
    optimizer = BasketOptimizer(db)
    return await optimizer.optimize_order_baskets(order_id)
