import asyncio
import sys
import os

# Добавляем корневую папку проекта в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from config.settings import settings
from shared.utils.unified_logging import setup_service_logging
from shared.utils.text_normalizer import normalize_product_name
from shared.utils.egg_categories import get_egg_category_coefficient
from shared.utils.alternatives_parser import parse_alternatives, normalize_alternatives_for_search
from shared.database import get_async_session
from shared.database.models import (
    Order as DBOrder, 
    User as DBUser, 
    OrderItem as DBOrderItem,
    LSDStock as DBLSDStock,
    LSDConfig as DBLSDConfig,
    UserSession as DBUserSession
)
from shared.models.base import OrderStatus, APIResponse, NormalizedOrder
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uvicorn
from sqlalchemy import select, and_
from sqlalchemy import text
from datetime import datetime
import logging
import httpx
import asyncio
from decimal import Decimal
from datetime import timedelta
from order_optimizer_handler import handle_analysis_complete, format_optimization_results
from basket_formatter import format_basket_results_message, _get_basket_data, _format_single_basket

setup_service_logging('order-service', level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальный набор заказов в обработке (защита от дублирования)
processing_order_ids: set[int] = set()

app = FastAPI(
    title="Korzinka Order Service",
    description="Сервис управления заказами",
    version="1.0.0"
)


# Модели запросов
class CreateOrderRequest(BaseModel):
    user_id: int  # DB ID пользователя, не telegram_id
    telegram_message_id: Optional[int] = None
    tg_group: Optional[str] = None  # ID группы Telegram
    original_list: str
    normalized_list: Dict[str, Any]  # NormalizedOrder as dict


class OrderResponse(BaseModel):
    id: int
    user_id: int
    status: str
    original_list: str
    normalized_list: Optional[Dict[str, Any]] = None
    total_cost: Optional[float] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@app.post("/orders/create")
async def create_order(
    request: CreateOrderRequest,
    db: AsyncSession = Depends(get_async_session)
):
    """Создание нового заказа с order_items"""
    try:
        logger.info(f"📝 Creating order for user {request.user_id}")
        
        # Проверяем, что пользователь существует по DB ID
        user_result = await db.execute(
            select(DBUser).where(DBUser.id == request.user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=404,
                detail="Пользователь не найден"
            )
        
        # Парсим normalized_list
        try:
            normalized_order = NormalizedOrder(**request.normalized_list)
        except Exception as e:
            logger.error(f"❌ Error parsing normalized_list: {e}")
            raise HTTPException(
                status_code=400,
                detail="Неверный формат нормализованного списка"
            )
        
        # Создаем новый заказ
        new_order = DBOrder(
            user_id=user.id,
            telegram_message_id=request.telegram_message_id,
            tg_group=request.tg_group,  # Добавлено: сохраняем ID группы
            original_list=request.original_list,
            normalized_list=request.normalized_list,
            status=OrderStatus.NEW,
            over_order_percent=user.over_order_percent,  # Наследуем от пользователя
            under_order_percent=user.under_order_percent  # Наследуем от пользователя
        )
        
        db.add(new_order)
        await db.flush()  # Получаем ID заказа
        
        # Создаем order_items для каждого продукта
        order_items = []
        for i, product in enumerate(normalized_order.products):
            # Парсим альтернативы (если есть слеш)
            alternatives_data = parse_alternatives(product.name)
            
            # ИСПРАВЛЕНО: Используем данные напрямую из parse_alternatives
            # main содержит полное название с общими словами
            main_name = alternatives_data['main']
            
            # alternatives уже содержат полные названия с общими словами
            alternatives_list = alternatives_data['alternatives'] if alternatives_data['alternatives'] else []
            
            order_item = DBOrderItem(
                order_id=new_order.id,
                original_text=product.original_text,
                product_name=main_name,
                requested_quantity=product.quantity,
                requested_unit=product.unit,
                normalized_name=main_name.lower().strip(),
                processing_status="pending",
                # Поддержка альтернатив
                alternatives=alternatives_list if alternatives_list else None,
                is_alternative_group=len(alternatives_list) > 0,
                selected_alternative=None
            )
            db.add(order_item)
            order_items.append(order_item)
            
            if alternatives_list:
                logger.info(f"  🔄 Product with alternatives: '{main_name}' | alternatives: {alternatives_list}")
        
        await db.commit()
        await db.refresh(new_order)
        
        logger.info(f"✅ Created order {new_order.id} with {len(order_items)} items for user {user.telegram_id}")
        
        return APIResponse(
            success=True,
            data={
                "id": new_order.id,
                "status": new_order.status.value,
                "user_id": user.telegram_id,  # Возвращаем telegram_id для совместимости
                "products_count": len(normalized_order.products),
                "order_items_created": len(order_items)
            },
            message="Заказ создан успешно"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating order: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Ошибка создания заказа"
        )


@app.get("/orders/{order_id}")
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_async_session)
):
    """Получение информации о заказе"""
    try:
        result = await db.execute(
            select(DBOrder).where(DBOrder.id == order_id)
        )
        order = result.scalar_one_or_none()
        
        if not order:
            raise HTTPException(
                status_code=404,
                detail="Заказ не найден"
            )
        
        # Получаем order_items
        items_result = await db.execute(
            select(DBOrderItem).where(DBOrderItem.order_id == order_id)
        )
        order_items = items_result.scalars().all()
        
        return APIResponse(
            success=True,
            data={
                "id": order.id,
                "user_id": order.user_id,
                "original_list": order.original_list,
                "normalized_list": order.normalized_list,
                "status": order.status.value,
                "total_cost": float(order.total_cost) if order.total_cost else None,
                "order_items": [
                    {
                        "id": item.id,
                        "product_name": item.product_name,
                        "requested_quantity": float(item.requested_quantity),
                        "requested_unit": item.requested_unit,
                        "processing_status": item.processing_status
                    }
                    for item in order_items
                ],
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "updated_at": order.updated_at.isoformat() if order.updated_at else None
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting order {order_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Ошибка получения заказа"
        )


@app.patch("/orders/{order_id}/confirm")
async def confirm_order(
    order_id: int,
    db: AsyncSession = Depends(get_async_session)
):
    """Подтверждение заказа пользователем"""
    try:
        logger.info(f"✅ Confirming order {order_id}")
        
        # Находим заказ
        result = await db.execute(
            select(DBOrder).where(DBOrder.id == order_id)
        )
        order = result.scalar_one_or_none()
        
        if not order:
            raise HTTPException(
                status_code=404,
                detail="Заказ не найден"
            )
        
        # Проверяем текущий статус
        if order.status != OrderStatus.NEW:
            raise HTTPException(
                status_code=400,
                detail=f"Заказ не может быть подтвержден в статусе {order.status.value}"
            )
        
        # Обновляем статус и время подтверждения
        order.status = OrderStatus.CONFIRMED
        order.user_confirmation_at = datetime.now()
        
        await db.commit()
        
        logger.info(f"✅ Order {order_id} confirmed successfully")
        
        return APIResponse(
            success=True,
            data={
                "id": order.id,
                "status": order.status.value,
                "confirmed_at": order.user_confirmation_at.isoformat()
            },
            message="Заказ подтвержден"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error confirming order {order_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Ошибка подтверждения заказа"
        )


@app.patch("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    db: AsyncSession = Depends(get_async_session)
):
    """Отмена заказа"""
    try:
        logger.info(f"❌ Cancelling order {order_id}")
        
        # Находим заказ
        result = await db.execute(
            select(DBOrder).where(DBOrder.id == order_id)
        )
        order = result.scalar_one_or_none()
        
        if not order:
            raise HTTPException(
                status_code=404,
                detail="Заказ не найден"
            )
        
        # Проверяем, что заказ можно отменить
        if order.status in [OrderStatus.COMPLETED, OrderStatus.CANCELLED]:
            raise HTTPException(
                status_code=400,
                detail=f"Заказ нельзя отменить в статусе {order.status.value}"
            )
        
        # Обновляем статус
        order.status = OrderStatus.CANCELLED
        
        await db.commit()
        
        logger.info(f"❌ Order {order_id} cancelled successfully")
        
        return APIResponse(
            success=True,
            data={
                "id": order.id,
                "status": order.status.value
            },
            message="Заказ отменен"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error cancelling order {order_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Ошибка отмены заказа"
        )


@app.post("/orders/force-retry/{order_id}")
async def force_retry_order(
    order_id: int,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Принудительный перезапуск анализа с очисткой старых результатов
    Используется для ручного перезапуска зависших или проблемных заказов
    """
    try:
        logger.info(f"🔄 Force retry requested for order {order_id}")

        # КРИТИЧНО: Проверяем что заказ не обрабатывается прямо сейчас
        if order_id in processing_order_ids:
            logger.warning(f"⚠️ Order {order_id} is already being processed, rejecting force-retry")
            raise HTTPException(
                status_code=409,
                detail=f"Заказ {order_id} уже обрабатывается. Дождитесь завершения текущего анализа."
            )

        # Находим заказ
        result = await db.execute(
            select(DBOrder).where(DBOrder.id == order_id)
        )
        order = result.scalar_one_or_none()

        if not order:
            raise HTTPException(
                status_code=404,
                detail="Заказ не найден"
            )
        
        # Проверяем, что заказ можно перезапустить
        if order.status in [OrderStatus.COMPLETED, OrderStatus.CANCELLED]:
            raise HTTPException(
                status_code=400,
                detail=f"Нельзя перезапустить заказ в статусе {order.status.value}"
            )
        
        # Очищаем старые результаты поиска по order_id
        from sqlalchemy import delete
        deleted_result = await db.execute(
            delete(DBLSDStock).where(DBLSDStock.order_id == order_id)
        )
        deleted_count = deleted_result.rowcount
        await db.commit()
        
        logger.info(f"🧹 Deleted {deleted_count} old lsd_stocks records for order {order_id}")
        
        # Обновляем статус
        order.status = OrderStatus.ANALYZING
        order.analysis_started_at = datetime.now()
        order.retry_count = (order.retry_count or 0) + 1
        order.last_retry_reason = "manual_force_retry"
        order.results_sent_at = None  # Обнуляем для повторной отправки результатов
        
        await db.commit()
        
        logger.info(f"🔄 Reset results_sent_at for order {order_id} to allow re-sending")
        
        logger.info(f"✅ Order {order_id} status updated to ANALYZING")
        
        # Запускаем анализ в фоне
        asyncio.create_task(restart_order_analysis(order_id))
        
        logger.info(f"🚀 Analysis restarted for order {order_id}")
        
        return APIResponse(
            success=True,
            data={
                "id": order.id,
                "status": order.status.value,
                "retry_count": order.retry_count,
                "analysis_started_at": order.analysis_started_at.isoformat(),
                "results_sent_at": None,  # Обнулено для повторной отправки
                "deleted_stocks_count": deleted_count
            },
            message=f"Заказ {order_id} перезапущен"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error force retrying order {order_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка перезапуска заказа: {str(e)}"
        )


@app.post("/orders/{order_id}/analyze")
async def analyze_order(
    order_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session)
):
    """Запуск анализа заказа (поиск товаров в ЛСД)"""
    try:
        logger.info(f"🔍 Starting analysis for order {order_id}")
        
        # Находим заказ
        result = await db.execute(
            select(DBOrder).where(DBOrder.id == order_id)
        )
        order = result.scalar_one_or_none()
        
        if not order:
            raise HTTPException(
                status_code=404,
                detail="Заказ не найден"
            )
        
        # Проверяем статус
        if order.status == OrderStatus.ANALYZING:
            # Заказ уже анализируется
            logger.warning(f"⚠️ Order {order_id} is already being analyzed")
            return APIResponse(
                success=True,
                data={
                    "id": order.id,
                    "status": order.status.value,
                    "analysis_started_at": order.analysis_started_at.isoformat() if order.analysis_started_at else None,
                    "message": "Анализ уже выполняется"
                },
                message="Анализ заказа уже запущен"
            )
        
        if order.status != OrderStatus.CONFIRMED:
            raise HTTPException(
                status_code=400,
                detail=f"Анализ доступен только для подтвержденных заказов. Текущий статус: {order.status.value}"
            )
        
        # Обновляем статус на ANALYZING
        order.status = OrderStatus.ANALYZING
        order.analysis_started_at = datetime.now()
        
        await db.commit()
        
        # Запускаем анализ в фоне
        background_tasks.add_task(perform_order_analysis, order_id)
        
        logger.info(f"🔍 Order {order_id} analysis started")
        
        return APIResponse(
            success=True,
            data={
                "id": order.id,
                "status": order.status.value,
                "analysis_started_at": order.analysis_started_at.isoformat()
            },
            message="Анализ заказа запущен"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error starting analysis for order {order_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Ошибка запуска анализа заказа"
        )


@app.get("/orders")
async def list_orders(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_async_session)
):
    """Получение списка заказов"""
    try:
        query = select(DBOrder)
        
        if user_id:
            query = query.where(DBOrder.user_id == user_id)
        if status:
            query = query.where(DBOrder.status == status)
            
        query = query.limit(limit).offset(offset).order_by(DBOrder.created_at.desc())
        
        result = await db.execute(query)
        orders = result.scalars().all()
        
        return APIResponse(
            success=True,
            data=[
                {
                    "id": order.id,
                    "user_id": order.user_id,
                    "status": order.status.value,
                    "created_at": order.created_at.isoformat() if order.created_at else None,
                    "products_count": len(order.normalized_list.get("products", [])) if order.normalized_list else 0
                }
                for order in orders
            ]
        )
        
    except Exception as e:
        logger.error(f"❌ Error listing orders: {e}")
        raise HTTPException(
            status_code=500,
            detail="Ошибка получения списка заказов"
        )


@app.get("/orders/{order_id}/analysis")
async def get_order_analysis(
    order_id: int,
    db: AsyncSession = Depends(get_async_session)
):
    """Получение результатов анализа заказа"""
    try:
        # Находим заказ
        result = await db.execute(
            select(DBOrder).where(DBOrder.id == order_id)
        )
        order = result.scalar_one_or_none()
        
        if not order:
            raise HTTPException(
                status_code=404,
                detail="Заказ не найден"
            )
        
        # Получаем lsd_stocks для этого заказа
        stocks_result = await db.execute(
            select(
                DBLSDStock,
                DBOrderItem,
                DBLSDConfig.id,
                DBLSDConfig.name,
                DBLSDConfig.display_name
            ).join(
                DBOrderItem, DBLSDStock.order_item_id == DBOrderItem.id
            ).join(
                DBLSDConfig, DBLSDStock.lsd_config_id == DBLSDConfig.id
            ).where(
                DBOrderItem.order_id == order_id
            ).order_by(DBOrderItem.id, DBLSDStock.lsd_config_id)
        )
        
        stocks_data = stocks_result.all()
        
        # Группируем по order_items
        analysis_by_items = {}
        total_stocks = 0
        
        for stock, order_item, lsd_id, lsd_name, lsd_display_name in stocks_data:
            item_id = order_item.id
            if item_id not in analysis_by_items:
                analysis_by_items[item_id] = {
                    "order_item": {
                        "id": order_item.id,
                        "product_name": order_item.product_name,
                        "requested_quantity": float(order_item.requested_quantity),
                        "requested_unit": order_item.requested_unit
                    },
                    "lsd_stocks": []
                }
            
            analysis_by_items[item_id]["lsd_stocks"].append({
                "id": stock.id,
                "lsd_config": {
                    "id": lsd_id,
                    "name": lsd_name,
                    "display_name": lsd_display_name
                },
                "found_name": stock.found_name,
                "found_unit": stock.found_unit,
                "found_quantity": float(stock.found_quantity),
                "price": float(stock.price),
                "fprice": float(stock.fprice),
                "tprice": float(stock.tprice) if stock.tprice else None,
                "available_stock": stock.available_stock,
                "product_url": stock.product_url,
                "product_id_in_lsd": stock.product_id_in_lsd,
                "search_query": stock.search_query,
                "search_result_position": stock.search_result_position,
                "is_exact_match": stock.is_exact_match,
                "match_score": float(stock.match_score) if stock.match_score else None,
                "created_at": stock.created_at.isoformat() if stock.created_at else None,
                "updated_at": stock.updated_at.isoformat() if stock.updated_at else None
            })
            total_stocks += 1
        
        return APIResponse(
            success=True,
            data={
                "order_id": order_id,
                "status": order.status.value,
                "analysis_result": order.analysis_result,
                "analysis_started_at": order.analysis_started_at.isoformat() if order.analysis_started_at else None,
                "analysis_completed_at": order.analysis_completed_at.isoformat() if order.analysis_completed_at else None,
                "total_stocks_found": total_stocks,
                "items_analysis": list(analysis_by_items.values())
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting order analysis {order_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Ошибка получения анализа заказа"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "order-service", "version": "1.0.0"}


async def perform_order_analysis(order_id: int):
    """Выполнение анализа заказа в фоновом режиме с параллельным поиском"""
    # Добавляем в набор обрабатываемых заказов
    processing_order_ids.add(order_id)
    
    try:
        logger.info(f"🔍 Starting background analysis for order {order_id}")
        
        async for db in get_async_session():
            # Получаем заказ с order_items
            order_result = await db.execute(
                select(DBOrder).where(DBOrder.id == order_id)
            )
            order = order_result.scalar_one_or_none()
            
            if not order:
                logger.error(f"❌ Order {order_id} not found for analysis")
                return
            
            # Получаем order_items
            items_result = await db.execute(
                select(DBOrderItem).where(DBOrderItem.order_id == order_id)
            )
            order_items = items_result.scalars().all()
            
            if not order_items:
                logger.error(f"❌ No order items found for order {order_id}")
                await _update_order_status_with_error(db, order, "Нет элементов заказа")
                return
            
            # Получаем пользователя
            user_result = await db.execute(
                select(DBUser).where(DBUser.id == order.user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                logger.error(f"❌ User not found for order {order_id}")
                await _update_order_status_with_error(db, order, "Пользователь не найден")
                return
            
            # ВАЖНО: Сохраняем telegram_id в переменную, чтобы избежать expired атрибутов
            user_telegram_id = user.telegram_id
            
            # Получаем активные ЛСД с сохраненными куками
            active_lsds = await _get_user_active_lsds(db, user_telegram_id)
            
            if not active_lsds:
                logger.warning(f"⚠️ No active LSDs with cookies for user {user_telegram_id}")
                await _update_order_status_with_error(db, order, "Нет доступных служб доставки")
                return
            
            logger.info(f"📊 Found {len(order_items)} items to search in {len(active_lsds)} LSDs")
            
            # ПАРАЛЛЕЛЬНЫЙ ПОИСК В БАТЧАХ
            total_stocks_found = await _search_products_in_batches(
                order_items=order_items,
                active_lsds=active_lsds,
                user_telegram_id=user_telegram_id
            )
            
            logger.info(f"✅ Parallel search completed: {total_stocks_found} stocks found")
            
            # Обновляем статус заказа
            order.status = OrderStatus.ANALYSIS_COMPLETE
            order.analysis_completed_at = datetime.now()
            order.analysis_result = {
                "total_stocks_found": total_stocks_found,
                "lsds_searched": len(active_lsds),
                "items_processed": len(order_items),
                "analysis_completed_at": datetime.now().isoformat()
            }
            
            await db.commit()
            
            logger.info(f"✅ Order {order_id} analysis completed: {total_stocks_found} stocks found")
            
            # Уведомляем пользователя о завершении анализа
            await _notify_user_analysis_complete(user_telegram_id, order_id, total_stocks_found)
            
            break  # Выходим из async for
            
    except Exception as e:
        logger.error(f"❌ Error in order analysis {order_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Обновляем статус на FAILED - используем новую сессию
        try:
            async for db_error in get_async_session():
                # Загружаем заказ заново в новой сессии
                order_result = await db_error.execute(
                    select(DBOrder).where(DBOrder.id == order_id)
                )
                order_to_update = order_result.scalar_one_or_none()
                
                if order_to_update:
                    # Напрямую обновляем статус без вызова функции
                    order_to_update.status = OrderStatus.FAILED
                    order_to_update.error_details = {
                        "error_message": str(e),
                        "failed_at": datetime.now().isoformat()
                    }
                    await db_error.commit()
                    logger.info(f"❌ Order {order_id} marked as FAILED: {str(e)}")
                break
        except Exception as update_error:
            logger.error(f"❌ Error updating order status: {update_error}")
    
    finally:
        # Удаляем из набора обрабатываемых заказов
        processing_order_ids.discard(order_id)


async def _search_products_in_batches(
    order_items: List[DBOrderItem],
    active_lsds: List[Dict[str, Any]],
    user_telegram_id: int
) -> int:
    """
    Параллельный поиск товаров через пул (semaphore-based pool)
    Возвращает общее количество найденных stocks
    """
    max_concurrent = settings.max_concurrent_browsers
    
    logger.info(f"🚀 Starting pool-based parallel search: {len(active_lsds)} LSDs, pool size={max_concurrent}")
    logger.info(f"💡 Using semaphore pool: slots will be reused as they become available")
    
    # Создаем семафор для управления пулом браузеров
    semaphore = asyncio.Semaphore(max_concurrent)
    
    # Создаем задачи для всех ЛСД сразу
    tasks = []
    for lsd_num, lsd in enumerate(active_lsds, 1):
        task = _lsd_worker(
            semaphore=semaphore,
            lsd=lsd,
            lsd_num=lsd_num,
            total_lsds=len(active_lsds),
            order_items=order_items,
            user_telegram_id=user_telegram_id
        )
        tasks.append(task)
    
    logger.info(f"📋 Created {len(tasks)} worker tasks, starting parallel execution...")
    
    # Запускаем все задачи параллельно (семафор ограничит одновременное выполнение)
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Подсчитываем результаты
    total_stocks_found = 0
    successful_lsds = 0
    failed_lsds = 0
    
    for lsd, result in zip(active_lsds, results):
        if isinstance(result, Exception):
            logger.error(f"❌ {lsd['display_name']}: error - {result}")
            failed_lsds += 1
        else:
            stocks_count = result
            if stocks_count > 0:
                total_stocks_found += stocks_count
                successful_lsds += 1
                logger.info(f"✅ {lsd['display_name']}: {stocks_count} stocks found")
            else:
                logger.warning(f"⚠️ {lsd['display_name']}: no stocks found")
    
    logger.info(f"\n🎉 Pool-based search completed:")
    logger.info(f"   Total stocks found: {total_stocks_found}")
    logger.info(f"   Successful LSDs: {successful_lsds}/{len(active_lsds)}")
    logger.info(f"   Failed LSDs: {failed_lsds}/{len(active_lsds)}")
    
    return total_stocks_found


async def _lsd_worker(
    semaphore: asyncio.Semaphore,
    lsd: Dict[str, Any],
    lsd_num: int,
    total_lsds: int,
    order_items: List[DBOrderItem],
    user_telegram_id: int
) -> int:
    """
    Воркер для обработки одного ЛСД через пул
    Захватывает слот из семафора, выполняет поиск, освобождает слот
    Возвращает количество найденных stocks
    """
    lsd_name = lsd.get('display_name', 'Unknown')
    
    # Ждем доступный слот в пуле
    logger.info(f"🔄 [{lsd_num}/{total_lsds}] {lsd_name}: waiting for available slot...")
    
    async with semaphore:
        # Слот получен!
        acquired_value = semaphore._value  # Количество свободных слотов
        logger.info(f"✅ [{lsd_num}/{total_lsds}] {lsd_name}: acquired slot (free slots: {acquired_value}/{settings.max_concurrent_browsers})")
        
        try:
            # Выполняем поиск
            stocks_found = await _search_products_in_lsd_isolated(
                order_items=order_items,
                lsd=lsd,
                user_telegram_id=user_telegram_id
            )

            # ОБНОВЛЕНИЕ: Задержка больше не нужна - семафор теперь в RPA-service
            # RPA-service сам контролирует количество браузеров через browser_semaphore
            logger.info(f"🔓 [{lsd_num}/{total_lsds}] {lsd_name}: releasing slot (found {stocks_found} stocks)")
            return stocks_found
            
        except Exception as e:
            logger.error(f"❌ [{lsd_num}/{total_lsds}] {lsd_name}: error in worker - {e}")
            logger.info(f"🔓 [{lsd_num}/{total_lsds}] {lsd_name}: releasing slot (error)")
            raise  # Пробрасываем исключение для gather
        
    # Семафор автоматически освобождается при выходе из async with


async def _search_products_in_lsd_isolated(
    order_items: List[DBOrderItem],
    lsd: Dict[str, Any],
    user_telegram_id: int
) -> int:
    """
    Поиск товаров в одном ЛСД (изолированная сессия БД)
    Возвращает количество найденных stocks
    """
    try:
        # ВАЖНО: Используем собственную сессию БД для каждого ЛСД
        async for db in get_async_session():
            stocks_found = await _search_products_in_lsd(
                db, order_items, lsd, user_telegram_id
            )
            await db.commit()  # Коммитим результаты этого ЛСД
            return stocks_found
    except Exception as e:
        logger.error(f"❌ Error in isolated search for {lsd.get('display_name', 'Unknown')}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0  # При ошибке возвращаем 0


async def _get_user_active_lsds(db: AsyncSession, telegram_id: int) -> List[Dict[str, Any]]:
    """Получение активных ЛСД пользователя с сохраненными куками (только MVP)"""
    try:
        # Загружаем только нужные поля из обеих таблиц
        result = await db.execute(
            select(
                DBUserSession.data,
                DBLSDConfig.id,
                DBLSDConfig.name,
                DBLSDConfig.display_name,
                DBLSDConfig.base_url
            ).join(
                DBLSDConfig, DBUserSession.lsd_config_id == DBLSDConfig.id
            ).where(
                DBUserSession.telegram_id == telegram_id
            ).where(
                DBUserSession.data.isnot(None)
            ).where(
                DBLSDConfig.is_active == True
            ).where(
                DBLSDConfig.is_mvp == True
            )
        )
        
        sessions = result.all()
        active_lsds = []
        
        for session_data, lsd_id, lsd_name, lsd_display_name, lsd_base_url in sessions:
            # Проверяем наличие ссылки на файл с cookies (новый формат) или cookies напрямую (старый формат)
            if session_data and (session_data.get('cookie_file') or session_data.get('cookies')):
                # Для нового формата берем count из метаданных, для старого считаем длину массива
                cookies_count = session_data.get('cookie_count') if session_data.get('cookie_file') else len(session_data.get('cookies', []))
                
                active_lsds.append({
                    'lsd_config_id': lsd_id,
                    'name': lsd_name,
                    'display_name': lsd_display_name,
                    'base_url': lsd_base_url,
                    'cookies_count': cookies_count
                })
        
        return active_lsds
        
    except Exception as e:
        logger.error(f"❌ Error getting user active LSDs: {e}")
        # При ошибке делаем rollback, чтобы транзакция не осталась в failed состоянии
        await db.rollback()
        return []


async def _search_products_in_lsd(
    db: AsyncSession, 
    order_items: List[DBOrderItem], 
    lsd: Dict[str, Any],
    telegram_id: int
) -> int:
    """
    Поиск товаров в конкретном ЛСД через RPA Service
    Возвращает количество найденных stocks
    """
    stocks_found = 0
    
    try:
        logger.info(f"🔍 Starting real RPA search in {lsd['display_name']} for {len(order_items)} products")
        
        # Подготавливаем данные для RPA поиска
        products_to_search = []
        for item in order_items:
            product_data = {
                "order_item_id": item.id,
                "product_name": item.product_name,  # Используем product_name для поиска
                "original_text": item.original_text,  # Сохраняем для логов
                "requested_quantity": float(item.requested_quantity),
                "requested_unit": item.requested_unit,
                "normalized_name": item.normalized_name,
                # Поддержка альтернатив
                "is_alternative_group": item.is_alternative_group,
                "alternatives": item.alternatives if item.alternatives else []
            }
            products_to_search.append(product_data)
        
        # Вызываем RPA Service для поиска
        # RPA-сервис сам сохраняет результаты в БД в lsd_stocks
        rpa_response = await _call_rpa_search(
            telegram_id=telegram_id,
            lsd_name=lsd['name'],
            products=products_to_search
        )
        
        # RPA-сервис уже сохранил результаты в БД
        if rpa_response:
            stocks_found = rpa_response.get('results_saved', 0)
            
            if stocks_found > 0:
                logger.info(f"✅ RPA Service saved {stocks_found} search results for {lsd['display_name']}")
            else:
                logger.warning(f"⚠️ No stocks found in {lsd['display_name']}")
        else:
            logger.warning(f"⚠️ No response from RPA for {lsd['display_name']}")
        
    except Exception as e:
        logger.error(f"❌ Error searching products in {lsd['display_name']}: {e}")
    
    return stocks_found


async def _call_rpa_search(telegram_id: int, lsd_name: str, products: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Вызов RPA Service для поиска товаров (возвращает полный ответ)"""
    try:
        logger.info(f"🤖 Calling RPA Service for {lsd_name} search with {len(products)} products")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://localhost:{settings.rpa_service_port}/search/products",
                json={
                    "telegram_id": telegram_id,
                    "lsd_name": lsd_name,
                    "products": products
                },
                timeout=300.0  # 5 минут на поиск
            )
            
            if response.status_code == 200:
                rpa_response = response.json()
                if rpa_response.get('success'):
                    data = rpa_response.get('data', {})
                    logger.info(f"✅ RPA Service completed: {data.get('results_saved', 0)} results saved")
                    return data  # Возвращаем data с results_saved, results_found и др.
                else:
                    logger.error(f"❌ RPA Service returned error: {rpa_response}")
                    return {}
            else:
                logger.error(f"❌ RPA Service request failed: {response.status_code} - {response.text}")
                return {}
                
    except httpx.TimeoutException:
        logger.error(f"⏰ RPA Service search timeout for {lsd_name}")
        return {}
    except Exception as e:
        logger.error(f"❌ Error calling RPA Service for {lsd_name}: {e}")
        return {}


def _calculate_fprice(price: Decimal, unit: str, quantity: Decimal, product_name: str = None) -> Decimal:
    """
    Расчет fprice - цены за базовую единицу (кг, л или шт)
    Для яиц приводит к категории СВ (80г)
    
    Примеры:
    - "250 г" за 160₽ -> fprice = 160 / 0.25 = 640₽/кг
    - "930 мл" за 105₽ -> fprice = 105 / 0.93 = 112.9₽/л
    - "10 шт Яйцо С0" за 119₽ -> fprice = 119 / 10 / 0.875 = 13.6₽/шт(СВ)
    - "10 шт Яйцо С3" за 50₽ -> fprice = 50 / 10 / 0.5 = 10₽/шт(СВ)
    """
    try:
        import re
        unit_only = re.sub(r'[\d\s,\.]+', '', unit).strip().lower()
        
        # Вес: переводим в кг и делим цену
        if unit_only in ['кг', 'kg']:
            return price / quantity if quantity > 0 else price
        elif unit_only in ['г', 'g', 'гр', 'грамм']:
            return price * 1000 / quantity if quantity > 0 else price
        elif unit_only in ['т', 't', 'тонна']:
            return price / (quantity * 1000) if quantity > 0 else price
        
        # Объем: переводим в л и делим цену
        elif unit_only in ['л', 'l', 'литр']:
            return price / quantity if quantity > 0 else price
        elif unit_only in ['мл', 'ml', 'миллилитр']:
            return price * 1000 / quantity if quantity > 0 else price
        
        # Штуки: цена за штуку (с учетом категории яиц)
        elif unit_only in ['шт', 'шт.', 'pcs', 'pc', 'штук', 'штука', 'упак', 'упак.', 'pack', 'упаковка']:
            price_per_item = price / quantity if quantity > 0 else price
            
            # Для яиц применяем коэффициент категории (делим!)
            # С3 (40г, коэф=0.5): 5₽/шт → 5 / 0.5 = 10₽ эквивалента О
            # О (80г, коэф=1.0): 10₽/шт → 10 / 1.0 = 10₽ эквивалента О
            if product_name:
                egg_coefficient = get_egg_category_coefficient(product_name)
                if egg_coefficient > 0:  # Защита от деления на ноль
                    price_per_item = price_per_item / Decimal(str(egg_coefficient))
            
            return price_per_item
        
        # По умолчанию
        return price
    except Exception:
        return price


def _normalize_unit_to_base(found_unit: str, found_quantity: Decimal) -> tuple[str, Decimal]:
    """
    Нормализация единицы измерения к базовой
    Возвращает: (base_unit, base_quantity)
    
    Логика:
    - Вес приводится к кг: base_unit='кг', base_quantity в кг
    - Объем приводится к л: base_unit='л', base_quantity в л  
    - Штуки остаются: base_unit='шт', base_quantity=количество штук
    """
    try:
        # Извлекаем только единицу измерения, убирая числа
        import re
        unit_only = re.sub(r'[\d\s,\.]+', '', found_unit).strip()
        unit_lower = unit_only.lower().strip()
        
        # Вес
        if unit_lower in ['кг', 'kg']:
            return ('кг', found_quantity)
        elif unit_lower in ['г', 'g', 'гр', 'грамм']:
            return ('кг', found_quantity / 1000)
        elif unit_lower in ['т', 't', 'тонна']:
            return ('кг', found_quantity * 1000)
        
        # Объем
        elif unit_lower in ['л', 'l', 'литр']:
            return ('л', found_quantity)
        elif unit_lower in ['мл', 'ml', 'миллилитр']:
            return ('л', found_quantity / 1000)
        
        # Штуки, упаковки
        elif unit_lower in ['шт', 'шт.', 'pcs', 'pc', 'штук', 'штука']:
            return ('шт', found_quantity)
        elif unit_lower in ['упак', 'упак.', 'pack', 'упаковка']:
            return ('шт', found_quantity)
        
        # По умолчанию - штуки
        else:
            logger.warning(f"⚠️ Unknown unit '{found_unit}', defaulting to 'шт' with quantity={found_quantity}")
            return ('шт', found_quantity)
    except Exception as e:
        logger.error(f"❌ Error normalizing unit '{found_unit}': {e}")
        return ('шт', found_quantity)


async def _update_order_status_with_error(db: AsyncSession, order: DBOrder, error_message: str):
    """Обновление статуса заказа при ошибке"""
    try:
        order.status = OrderStatus.FAILED
        order.error_details = {
            "error_message": error_message,
            "failed_at": datetime.now().isoformat()
        }
        await db.commit()
        logger.info(f"❌ Order {order.id} marked as FAILED: {error_message}")
    except Exception as e:
        logger.error(f"❌ Error updating order status: {e}")


async def _notify_user_analysis_complete(telegram_id: int, order_id: int, stocks_found: int):
    """Уведомление пользователя о завершении анализа"""
    try:
        # Пока просто логируем
        # В будущем здесь будет отправка уведомления в Telegram
        logger.info(f"📢 Analysis complete for order {order_id}: {stocks_found} products found")
        
        # TODO: Отправка сообщения в Telegram о завершении анализа
        
    except Exception as e:
        logger.error(f"❌ Error notifying user: {e}")


# ============================================================================
# МОНИТОРИНГ ЗАВИСШИХ ЗАКАЗОВ
# ============================================================================

async def monitor_analyzing_orders():
    """
    Мониторинг заказов в ANALYZING и ANALYSIS_COMPLETE каждые 10 секунд
    Двойная защита: in-memory set + DB lock
    """
    logger.info("🔄 Starting order monitoring loop (every 10 seconds)...")
    
    while True:
        try:
            await asyncio.sleep(10)
            
            # 1. Обрабатываем завершенные анализы (ANALYSIS_COMPLETE → OPTIMIZING → OPTIMIZED)
            await process_analysis_complete_orders()
            
            # 2. Обрабатываем оптимизированные заказы (OPTIMIZED → RESULTS_SENT)
            await process_optimized_orders()
            
            # 3. Обрабатываем FAILED заказы (отправка уведомлений)
            await process_failed_orders()
            
            async for db in get_async_session():
                # Быстрый SELECT только нужных полей
                result = await db.execute(
                    select(DBOrder.id, DBOrder.analysis_started_at, DBOrder.retry_count)
                    .where(DBOrder.status == OrderStatus.ANALYZING)
                )
                orders_data = result.all()
                
                if not orders_data:
                    break  # Нет заказов в ANALYZING
                
                for order_id, started_at, retry_count in orders_data:
                    # Первая защита - in-memory
                    if order_id in processing_order_ids:
                        continue
                    
                    # Проверяем timeout
                    if started_at:
                        from datetime import timezone
                        now = datetime.now(timezone.utc)
                        elapsed = (now - started_at).total_seconds()
                        if elapsed < 1800:  # Меньше 30 минут - все ок
                            continue
                    
                    # Вторая защита - проверяем в БД с блокировкой
                    order_result = await db.execute(
                        select(DBOrder)
                        .where(DBOrder.id == order_id)
                        .with_for_update(skip_locked=True)
                    )
                    order = order_result.scalar_one_or_none()
                    
                    if not order or order.status != OrderStatus.ANALYZING:
                        continue  # Уже обработан другим процессом
                    
                    # Обновляем и перезапускаем
                    retry_count = (retry_count or 0) + 1
                    
                    if retry_count > 3:
                        order.status = OrderStatus.FAILED
                        order.error_details = {
                            "error_message": "Analysis timeout - max retries exceeded",
                            "failed_at": datetime.now().isoformat()
                        }
                        await db.commit()
                        logger.error(f"❌ Order {order_id} failed after {retry_count} retries")
                    else:
                        order.analysis_started_at = datetime.now()
                        order.retry_count = retry_count
                        order.last_retry_reason = "timeout_recovery"
                        await db.commit()
                        
                        logger.warning(f"🔄 Restarting order {order_id} analysis (retry {retry_count}/3)")
                        asyncio.create_task(restart_order_analysis(order_id))
                
                break
                
        except Exception as e:
            logger.error(f"❌ Error in monitor_analyzing_orders: {e}")
            await asyncio.sleep(30)  # Пауза при ошибке


async def restart_order_analysis(order_id: int):
    """Перезапуск анализа с защитой от дублирования и очисткой старых результатов"""
    if order_id in processing_order_ids:
        logger.warning(f"⚠️ Order {order_id} already processing, skipping restart")
        return
    
    try:
        processing_order_ids.add(order_id)
        
        # Очищаем старые результаты поиска перед перезапуском
        logger.info(f"🧹 Cleaning old search results for order {order_id}")
        async for db in get_async_session():
            # Удаляем все записи lsd_stocks для этого заказа
            from sqlalchemy import delete
            await db.execute(
                delete(DBLSDStock).where(
                    DBLSDStock.order_item_id.in_(
                        select(DBOrderItem.id).where(DBOrderItem.order_id == order_id)
                    )
                )
            )
            await db.commit()
            logger.info(f"✅ Cleaned old search results for order {order_id}")
            break
        
        # Теперь запускаем анализ заново
        await perform_order_analysis(order_id)
    finally:
        processing_order_ids.discard(order_id)


async def send_telegram_message(
    chat_id: str,
    text: str,
    reply_to_message_id: Optional[int] = None,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
    order_id: Optional[int] = None
) -> bool:
    """
    Отправка сообщения в Telegram через telegram-bot API с автоматическим логированием.

    Все сообщения отправляются через централизованный telegram-bot сервис,
    который автоматически логирует их в user_messages таблицу.
    """
    try:
        logger.info(f"📤 Sending message via telegram-bot API to {chat_id}, length: {len(text)} chars")

        async with httpx.AsyncClient() as client:
            # Формируем payload, исключая None значения
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": disable_web_page_preview
            }

            # Добавляем необязательные параметры только если они не None
            if order_id is not None:
                payload["order_id"] = order_id
            if reply_to_message_id is not None:
                payload["reply_to_message_id"] = reply_to_message_id

            response = await client.post(
                "http://localhost:8001/api/send-message",
                json=payload,
                timeout=60.0  # Увеличен до 60 секунд для telegram-bot API
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    logger.info(f"✅ Message sent successfully to {chat_id} (telegram_message_id={result.get('telegram_message_id')})")
                    return True
                else:
                    logger.error(f"❌ telegram-bot API returned error: {result.get('error')}")
                    return False
            else:
                logger.error(f"❌ telegram-bot API request failed: {response.status_code} - {response.text}")
                return False

    except httpx.TimeoutException as e:
        logger.error(f"❌ Timeout calling telegram-bot API for {chat_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error calling telegram-bot API for {chat_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def process_analysis_complete_orders():
    """
    Обработка заказов в статусе ANALYSIS_COMPLETE.
    Переводит в OPTIMIZING и запускает оптимизатор.
    """
    try:
        async for db in get_async_session():
            # Получаем заказы в ANALYSIS_COMPLETE
            result = await db.execute(
                select(DBOrder).where(DBOrder.status == OrderStatus.ANALYSIS_COMPLETE)
            )
            orders = result.scalars().all()
            
            if not orders:
                break
            
            logger.info(f"📋 Found {len(orders)} orders in ANALYSIS_COMPLETE status")
            
            for order in orders:
                # ===================================================================
                # ЗАПУСК ОПТИМИЗАЦИИ: ANALYSIS_COMPLETE → OPTIMIZING → OPTIMIZED
                # ===================================================================
                logger.info(f"🎯 Starting optimization for order {order.id}...")
                
                optimization_result = await handle_analysis_complete(order.id, db)
                
                if not optimization_result.get('success'):
                    logger.error(f"❌ Optimization failed for order {order.id}")
                    logger.error(f"   Error: {optimization_result.get('error')}")
                    # Статус уже установлен в FAILED внутри handle_analysis_complete
                    
                    # Если есть сообщение для пользователя - отправляем
                    user_message = optimization_result.get('user_message')
                    if user_message and order.tg_group:
                        logger.info(f"📤 Sending failure notification to user for order {order.id}")
                        await send_telegram_message(
                            chat_id=order.tg_group,
                            text=user_message,
                            reply_to_message_id=order.telegram_message_id,
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                            order_id=order.id
                        )
                    
                    continue
                
                # Логируем успешную оптимизацию
                logger.info(format_optimization_results(order.id, optimization_result))
            
            break
            
    except Exception as e:
        logger.error(f"❌ Error in process_analysis_complete_orders: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def process_optimized_orders():
    """
    Обработка заказов в статусе OPTIMIZED.
    Отправка топ-1 корзины + PDF-отчета пользователю и перевод в RESULTS_SENT.
    """
    from pdf_generator import OrderReportGenerator
    from telegram_document_sender import send_telegram_document
    
    try:
        async for db in get_async_session():
            # Получаем заказы в OPTIMIZED с FOR UPDATE SKIP LOCKED
            # Чтобы избежать параллельной обработки
            result = await db.execute(
                select(DBOrder)
                .where(
                    and_(
                        DBOrder.status == OrderStatus.OPTIMIZED,
                        DBOrder.results_sent_at.is_(None)  # Еще не отправляли
                    )
                )
                .with_for_update(skip_locked=True)
            )
            orders = result.scalars().all()
            
            if not orders:
                break
            
            logger.info(f"📋 Found {len(orders)} orders in OPTIMIZED status")
            
            for order in orders:
                # ВАЖНО: Сохраняем order_id сразу, пока сессия активна
                order_id = order.id
                order_tg_group = order.tg_group
                order_telegram_message_id = order.telegram_message_id
                
                try:
                    logger.info(f"📤 Preparing results for order {order_id}...")
                    
                    # Извлекаем missing_mono_lsds из analysis_result
                    missing_mono_lsds = []
                    if order.analysis_result and isinstance(order.analysis_result, dict):
                        missing_mono_lsds = order.analysis_result.get('missing_mono_lsds', [])
                    
                    # 1. Генерация текстового сообщения (топ-1 корзина)
                    msg1 = await format_basket_results_message(
                        db, order_id, top_n=1, missing_mono_lsds=missing_mono_lsds
                    )
                    
                    if msg1.startswith("❌"):
                        logger.warning(f"⚠️ No optimization data for order {order_id}")
                        order.status = OrderStatus.FAILED
                        order.error_details = {
                            "error_type": "no_optimization_data",
                            "message": "Не найдено товаров для оптимизации",
                            "failed_at": datetime.now().isoformat()
                        }
                        await db.commit()
                        continue
                    
                    logger.info(f"📊 Formatted message: {len(msg1)} chars")
                    
                    # 2. Генерация PDF-отчета
                    logger.info(f"📄 Generating PDF report for order {order_id}...")
                    
                    pdf_bytes = None
                    try:
                        generator = OrderReportGenerator(order_id, db)
                        pdf_bytes = await generator.generate_report()
                    except Exception as pdf_error:
                        logger.error(f"❌ PDF generation error for order {order_id}: {pdf_error}")
                        import traceback
                        logger.error(traceback.format_exc())
                        
                        # При ошибке PDF - делаем rollback и продолжаем
                        await db.rollback()

                        # Отправляем хотя бы текстовое сообщение
                        success = await send_telegram_message(
                            chat_id=order_tg_group,
                            text=msg1,
                            reply_to_message_id=order_telegram_message_id,
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                            order_id=order_id
                        )

                        if success:
                            # Начинаем новую транзакцию для обновления статуса
                            order.status = OrderStatus.RESULTS_SENT
                            order.results_sent_at = datetime.now()
                            await db.commit()
                        continue
                    
                    if not pdf_bytes:
                        logger.error(f"❌ Failed to generate PDF for order {order_id}")
                        # Отправляем хотя бы текстовое сообщение
                        success = await send_telegram_message(
                            chat_id=order_tg_group,
                            text=msg1,
                            reply_to_message_id=order_telegram_message_id,
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                            order_id=order_id
                        )

                        if success:
                            order.status = OrderStatus.RESULTS_SENT
                            order.results_sent_at = datetime.now()
                            await db.commit()
                        continue
                    
                    logger.info(f"✅ PDF generated: {len(pdf_bytes)} bytes")

                    # КРИТИЧНО: Коммитим транзакцию ПЕРЕД отправкой в Telegram
                    # чтобы не держать транзакцию открытой во время 30-секундной отправки
                    logger.info(f"🔄 Committing transaction BEFORE sending to Telegram")
                    await db.commit()
                    logger.info(f"✅ Transaction committed, database locks released")

                    # 3. Отправка текстового сообщения
                    success1 = await send_telegram_message(
                        chat_id=order_tg_group,
                        text=msg1,
                        reply_to_message_id=order_telegram_message_id,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                        order_id=order_id
                    )
                    
                    if not success1:
                        logger.error(f"❌ Failed to send message for order {order_id}")
                        continue  # Оставляем в OPTIMIZED для повторной попытки
                    
                    # Пауза между сообщениями
                    await asyncio.sleep(1)
                    
                    # 4. Отправка PDF-документа
                    success2 = await send_telegram_document(
                        chat_id=order_tg_group,
                        document=pdf_bytes,
                        filename=f"order_{order_id}_report.pdf",
                        caption="📊 Подробный отчет по заказу",
                        reply_to_message_id=order_telegram_message_id,
                        order_id=order_id,
                        telegram_bot_token=settings.telegram_bot_token
                    )

                    # ВАЖНО: Обновляем статус если хотя бы текстовое сообщение отправлено
                    # PDF - это бонус, но не критично для завершения заказа
                    if success1:
                        if success2:
                            logger.info(f"✅ Both message and PDF sent for order {order_id}")
                        else:
                            logger.warning(f"⚠️ Message sent but PDF failed for order {order_id} - marking as RESULTS_SENT anyway")

                        # Обновляем статус: OPTIMIZED → RESULTS_SENT
                        # После commit выше order стал detached, нужно снова получить из БД
                        async for db_update in get_async_session():
                            order_to_update = await db_update.execute(
                                select(DBOrder).where(DBOrder.id == order_id)
                            )
                            order_obj = order_to_update.scalar_one_or_none()
                            if order_obj:
                                order_obj.status = OrderStatus.RESULTS_SENT
                                order_obj.results_sent_at = datetime.now()
                                await db_update.commit()
                                logger.info(f"✅ Order {order_id}: OPTIMIZED → RESULTS_SENT")
                                logger.info(f"   Sent at: {order_obj.results_sent_at.strftime('%Y-%m-%d %H:%M:%S')}")
                            break
                    else:
                        logger.error(f"❌ Failed to send message for order {order_id}")
                        # Оставляем в OPTIMIZED для повторной попытки
                    
                except Exception as e:
                    # order_id уже сохранен в начале цикла
                    logger.error(f"❌ Error processing order {order_id}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    continue
            
            break
            
    except Exception as e:
        logger.error(f"❌ Error in process_optimized_orders: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def process_failed_orders():
    """
    Обработка заказов в статусе FAILED.
    Отправляет уведомления пользователям и обновляет статус.
    """
    try:
        async for db in get_async_session():
            # Получаем FAILED заказы, для которых еще не отправлено уведомление
            result = await db.execute(
                select(DBOrder).where(
                    DBOrder.status == OrderStatus.FAILED
                ).where(
                    DBOrder.results_sent_at.is_(None)  # Еще не отправляли уведомление
                )
            )
            failed_orders = result.scalars().all()
            
            if not failed_orders:
                break
            
            logger.info(f"📋 Found {len(failed_orders)} FAILED orders without notification")
            
            for order in failed_orders:
                try:
                    # Проверяем наличие error_details с user_message
                    if not order.error_details or not isinstance(order.error_details, dict):
                        logger.warning(f"⚠️ Order {order.id}: no error_details, skipping notification")
                        continue
                    
                    user_message = order.error_details.get('user_message')
                    error_type = order.error_details.get('error_type')
                    
                    if not user_message:
                        logger.warning(f"⚠️ Order {order.id}: no user_message in error_details, skipping")
                        continue
                    
                    if not order.tg_group:
                        logger.warning(f"⚠️ Order {order.id}: no tg_group, cannot send notification")
                        # Отмечаем как отправленное чтобы не пытаться снова
                        order.results_sent_at = datetime.now()
                        await db.commit()
                        continue
                    
                    logger.info(f"📤 Sending FAILED notification for order {order.id} (error_type={error_type})")

                    success = await send_telegram_message(
                        chat_id=order.tg_group,
                        text=user_message,
                        reply_to_message_id=order.telegram_message_id,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                        order_id=order.id
                    )
                    
                    if success:
                        logger.info(f"✅ FAILED notification sent successfully for order {order.id}")
                        order.results_sent_at = datetime.now()
                        await db.commit()
                    else:
                        logger.error(f"❌ Failed to send notification for order {order.id}")
                        # Оставляем results_sent_at = None для повторной попытки
                
                except Exception as e:
                    logger.error(f"❌ Error processing FAILED order {order.id}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    continue
            
            break
    
    except Exception as e:
        logger.error(f"❌ Error in process_failed_orders: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def check_stuck_orders_on_startup():
    """Проверка зависших заказов при старте сервиса"""
    logger.info("🔍 Checking for stuck orders on startup...")
    
    try:
        async for db in get_async_session():
            result = await db.execute(
                select(DBOrder).where(DBOrder.status == OrderStatus.ANALYZING)
            )
            stuck_orders = result.scalars().all()
            
            if not stuck_orders:
                logger.info("✅ No stuck orders found on startup")
                break
            
            logger.warning(f"⚠️ Found {len(stuck_orders)} stuck orders on startup")
            
            for order in stuck_orders:
                if order.analysis_started_at:
                    from datetime import timezone
                    now = datetime.now(timezone.utc)
                    elapsed = (now - order.analysis_started_at).total_seconds()
                    if elapsed > 1800:  # Больше 30 минут
                        logger.warning(f"🔄 Restarting stuck order {order.id} (elapsed: {elapsed:.0f}s)")
                        asyncio.create_task(restart_order_analysis(order.id))
                else:
                    # Заказ без времени старта - перезапускаем
                    logger.warning(f"🔄 Restarting order {order.id} without start time")
                    asyncio.create_task(restart_order_analysis(order.id))
            
            break
            
    except Exception as e:
        logger.error(f"❌ Error checking stuck orders: {e}")


async def run_service():
    """Запуск Order Service"""
    logger.info(f"🚀 Starting Order Service on port {settings.order_service_port}")
    
    # Проверяем зависшие заказы при старте
    await check_stuck_orders_on_startup()
    
    # Запускаем мониторинг в фоне
    asyncio.create_task(monitor_analyzing_orders())
    
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=settings.order_service_port,
        log_config=None,
        access_log=settings.debug
    )
    
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(run_service())
