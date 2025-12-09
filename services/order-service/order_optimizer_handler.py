"""
Обработчик оптимизации заказов в Order-service.
Интегрирует order_optimizer с жизненным циклом заказа.
"""

import logging
from typing import Dict, Any, Optional
import sys
import os
from datetime import datetime
import httpx

# Добавляем путь к services для импорта оптимизатора
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.optimizer.optimize import optimize_order_unified
from config.settings import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from shared.database.models import Order as DBOrder, User as DBUser
from shared.models.base import OrderStatus

logger = logging.getLogger(__name__)


async def get_user_exclusions(telegram_id: int) -> Optional[Dict[str, Any]]:
    """
    Получение исключений пользователя из user-service.

    Args:
        telegram_id: Telegram ID пользователя

    Returns:
        Dict с keywords и products для фильтрации, или None при ошибке
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:{settings.user_service_port}/users/{telegram_id}/exclusions/keywords",
                timeout=10.0
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    exclusions = data.get('data', {})
                    keywords = exclusions.get('keywords', [])
                    products = exclusions.get('products', [])

                    if keywords or products:
                        logger.info(f"🚫 User {telegram_id} exclusions: {len(keywords)} keywords, {len(products)} products")
                        return {
                            'keywords': keywords,
                            'products': products
                        }
                    else:
                        logger.debug(f"User {telegram_id} has no exclusions")
                        return None
            elif response.status_code == 404:
                logger.debug(f"No exclusions found for user {telegram_id}")
                return None
            else:
                logger.warning(f"⚠️ Failed to get exclusions for user {telegram_id}: {response.status_code}")
                return None

    except httpx.TimeoutException:
        logger.warning(f"⚠️ Timeout getting exclusions for user {telegram_id}")
        return None
    except Exception as e:
        logger.error(f"❌ Error getting exclusions for user {telegram_id}: {e}")
        return None


async def handle_analysis_complete(order_id: int, db: AsyncSession) -> Dict[str, Any]:
    """
    Обработка заказа после завершения анализа (поиска товаров).
    
    Переводит заказ: ANALYSIS_COMPLETE → OPTIMIZING → OPTIMIZED
    
    Args:
        order_id: ID заказа
        db: AsyncSession для работы с БД
        
    Returns:
        Dict с результатами оптимизации
    """
    try:
        # Загружаем заказ
        order = await db.get(DBOrder, order_id)
        if not order:
            logger.error(f"❌ Order {order_id} not found")
            return {"success": False, "error": "Order not found"}

        # Получаем пользователя для telegram_id
        user = await db.get(DBUser, order.user_id)
        if not user:
            logger.error(f"❌ User not found for order {order_id}")
            return {"success": False, "error": "User not found"}

        telegram_id = user.telegram_id

        # Переводим в OPTIMIZING
        order.status = OrderStatus.OPTIMIZING
        order.optimization_started_at = datetime.now()
        await db.commit()

        logger.info(f"🎯 Order {order_id}: ANALYSIS_COMPLETE → OPTIMIZING")
        logger.info(f"   Started at: {order.optimization_started_at.strftime('%Y-%m-%d %H:%M:%S')}")

        # Получаем DATABASE_URL из настроек
        db_url = settings.database_url

        if not db_url:
            logger.error("❌ DATABASE_URL not configured")

            # Откат статуса при ошибке
            order.status = OrderStatus.FAILED
            order.error_details = {
                "error_type": "configuration_error",
                "message": "DATABASE_URL not configured",
                "failed_at": datetime.now().isoformat()
            }
            await db.commit()

            return {"success": False, "error": "DATABASE_URL not configured"}

        # Получаем исключения пользователя (diet_type, категории, черный список)
        exclusions = await get_user_exclusions(telegram_id)

        # Запускаем оптимизатор (топ-10 корзин)
        # Используем unified интерфейс с автовыбором движка (NumPy если доступен)
        result = optimize_order_unified(
            order_id=order_id,
            db_connection_string=db_url,
            engine="auto",  # Автоматический выбор: NumPy если доступен, иначе Legacy
            top_n=10,
            exclusions=exclusions  # Передаём исключения пользователя
        )
        
        # Проверяем статус оптимизации
        opt_status = result.get('status')
        
        if opt_status == 'no_data':
            # Нет данных в fprice_optimizer - товары не найдены
            logger.warning(f"⚠️ Order {order_id}: No products found in fprice_optimizer")
            
            order.status = OrderStatus.FAILED
            order.error_details = {
                "error_type": "no_products_found",
                "message": "Подходящих товаров не нашлось",
                "user_message": "❌ Подходящих товаров не нашлось",
                "failed_at": datetime.now().isoformat()
            }
            await db.commit()
            
            logger.info(f"❌ Order {order_id}: OPTIMIZING → FAILED (no products found)")
            
            return {
                "success": False,
                "error": "no_products_found",
                "user_message": "❌ Подходящих товаров не нашлось"
            }
        
        if opt_status == 'success':
            # Успех - переводим в OPTIMIZED
            order.status = OrderStatus.OPTIMIZED
            order.optimization_completed_at = datetime.now()
            
            # Сохраняем missing_mono_lsds в analysis_result (если есть)
            if result.get('missing_mono_lsds'):
                if not order.analysis_result:
                    order.analysis_result = {}
                order.analysis_result['missing_mono_lsds'] = result['missing_mono_lsds']
            
            await db.commit()
            
            # Определяем движок
            engine = result.get('engine', 'unknown').upper()
            logger.info(f"✅ Order {order_id}: OPTIMIZING → OPTIMIZED")
            logger.info(f"   Engine: {engine}")
            logger.info(f"   Completed at: {order.optimization_completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"   Total combinations analyzed: {result['total_combinations']:,}")
            logger.info(f"   Best basket: #{result['best_basket_id']}")
            logger.info(f"   Best cost: {result['best_total_cost']:.2f}₽")
            logger.info(f"   Execution time: {result['elapsed_time']:.2f}s")
            if result.get('performance_comb_per_sec'):
                logger.info(f"   Performance: {result['performance_comb_per_sec']:,} comb/sec")
            if result.get('missing_mono_lsds'):
                logger.info(f"   Missing mono-baskets: {', '.join(result['missing_mono_lsds'])}")
            
            return {
                "success": True,
                "data": result
            }
        else:
            # Ошибка оптимизации
            logger.error(f"❌ Order {order_id}: OPTIMIZING → FAILED")
            logger.error(f"   Optimization returned non-success status: {result}")
            
            order.status = OrderStatus.FAILED
            order.error_details = {
                "error_type": "optimization_failed",
                "message": "Optimization returned non-success status",
                "details": result,
                "failed_at": datetime.now().isoformat()
            }
            await db.commit()
            
            return {
                "success": False,
                "error": "Optimization returned non-success status",
                "details": result
            }
        
    except Exception as e:
        logger.error(f"❌ Error optimizing order {order_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Откат при неожиданной ошибке
        try:
            order = await db.get(DBOrder, order_id)
            if order:
                order.status = OrderStatus.FAILED
                order.error_details = {
                    "error_type": "unexpected_error",
                    "message": str(e),
                    "failed_at": datetime.now().isoformat()
                }
                await db.commit()
        except Exception as rollback_error:
            logger.error(f"❌ Error during rollback: {rollback_error}")
        
        return {
            "success": False,
            "error": str(e)
        }


def format_optimization_results(order_id: int, result: Dict[str, Any]) -> str:
    """
    Форматирование результатов оптимизации для логов.
    
    Args:
        order_id: ID заказа
        result: Результат из handle_analysis_complete
        
    Returns:
        Отформатированная строка для логов
    """
    if not result.get('success'):
        return f"❌ Optimization failed for order {order_id}: {result.get('error', 'Unknown error')}"
    
    data = result.get('data', {})
    
    engine = data.get('engine', 'unknown').upper()
    msg = f"✅ Order {order_id} optimized successfully (engine: {engine}):\n"
    msg += f"   • Analyzed: {data.get('total_combinations', 0):,} combinations\n"
    msg += f"   • Saved: top-{data.get('saved_baskets', 0)} baskets\n"
    msg += f"   • Best basket: #{data.get('best_basket_id')}\n"
    msg += f"   • Best cost: {data.get('best_total_cost', 0):.2f}₽\n"
    msg += f"   • Loss + Delivery: {data.get('best_loss_and_delivery', 0):.2f}₽\n"
    msg += f"   • Time: {data.get('elapsed_time', 0):.2f}s"
    if data.get('performance_comb_per_sec'):
        msg += f"\n   • Performance: {data.get('performance_comb_per_sec', 0):,} comb/sec"
    
    return msg
