"""
Форматирование результатов оптимизации корзин для отправки в Telegram
"""
import logging
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


async def format_basket_results_message(db: AsyncSession, order_id: int, top_n: int = 3, missing_mono_lsds: List[str] = None) -> str:
    """
    Формирование сообщения с результатами оптимизации для первых N корзин
    
    Args:
        db: Async сессия БД
        order_id: ID заказа
        top_n: Количество корзин для показа (по умолчанию 3)
        missing_mono_lsds: Список ЛСД, для которых не найдено моно-корзин
    
    Returns:
        Отформатированное HTML сообщение для Telegram
    """
    try:
        message_parts = []
        
        # Получаем данные для каждой корзины
        for rank in range(1, top_n + 1):
            basket_data = await _get_basket_data(db, order_id, rank)
            
            if not basket_data:
                logger.warning(f"⚠️ No basket data for order {order_id}, rank {rank}")
                continue
            
            # Форматируем корзину
            basket_message = _format_single_basket(basket_data, rank)
            message_parts.append(basket_message)
        
        if not message_parts:
            return "❌ Не найдено результатов оптимизации"
        
        # Объединяем все корзины
        full_message = "\n\n".join(message_parts)
        
        # Добавляем заголовок
        header = f"🛒 <b>Результаты оптимизации заказа #{order_id}</b>\n\n"
        
        # Добавляем предупреждение о недоступных моно-корзинах
        if missing_mono_lsds:
            warning = f"⚠️ <i>Для {', '.join(missing_mono_lsds)} не существует моно-корзины запрошенных продуктов</i>\n\n"
            full_message = warning + full_message
        
        return header + full_message
        
    except Exception as e:
        logger.error(f"❌ Error formatting basket results: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return "❌ Ошибка формирования результатов"


async def _get_basket_data(db: AsyncSession, order_id: int, rank: int) -> Dict[str, Any]:
    """
    Получение данных корзины через процедуру top_baskets
    
    Returns:
        Dict с ключами:
        - items: List[Dict] - товары корзины
        - delivery_details: List[Dict] - детализация доставки и топапов по ЛСД
        - summary: Dict - сводная информация
    """
    try:
        # Вызываем процедуру top_baskets
        result = await db.execute(
            text("SELECT * FROM top_baskets(:order_id, :rank)"),
            {"order_id": order_id, "rank": rank}
        )
        
        rows = result.fetchall()
        
        if not rows:
            return None
        
        # Разделяем на items, delivery_details и summary
        items = []
        delivery_details = []
        summary = None
        
        for row in rows:
            row_dict = dict(row._mapping)
            
            if row_dict['result_type'] == 'ITEMS':
                items.append({
                    'lsd_name': row_dict['lsd_name'],
                    'product_name': row_dict['product_name'],
                    'original_product_name': row_dict['original_product_name'],
                    'base_quantity': float(row_dict['base_quantity']) if row_dict['base_quantity'] else 0,
                    'base_unit': row_dict['base_unit'],
                    'price': float(row_dict['price']) if row_dict['price'] else 0,
                    'fprice': float(row_dict['fprice']) if row_dict['fprice'] else 0,
                    'loss': float(row_dict['loss']) if row_dict['loss'] else 0,
                    'order_item_ids_cost': float(row_dict['order_item_ids_cost']) if row_dict['order_item_ids_cost'] else 0,
                    'order_item_ids_quantity': int(row_dict['order_item_ids_quantity']) if row_dict['order_item_ids_quantity'] else 0,
                    'requested_quantity': float(row_dict['requested_quantity']) if row_dict['requested_quantity'] else 0,
                    'requested_unit': row_dict['requested_unit'],
                    'product_url': row_dict['product_url']
                })
            elif row_dict['result_type'] == 'DELIVERY_DETAILS':
                delivery_details.append({
                    'lsd_name': row_dict['lsd_name'],
                    'delivery_cost': float(row_dict['delivery_cost']) if row_dict['delivery_cost'] else 0,
                    'topup': float(row_dict['topup']) if row_dict['topup'] else 0
                })
            elif row_dict['result_type'] == 'SUMMARY':
                summary = {
                    'basket_id': int(row_dict['basket_id']) if row_dict['basket_id'] else 0,
                    'order_id': row_dict['order_id'],
                    'basket_rank': row_dict['basket_rank'],
                    'total_goods_cost': float(row_dict['total_goods_cost']) if row_dict['total_goods_cost'] else 0,
                    'total_delivery_cost': float(row_dict['total_delivery_cost']) if row_dict['total_delivery_cost'] else 0,
                    'total_loss': float(row_dict['total_loss']) if row_dict['total_loss'] else 0,
                    'total_cost': float(row_dict['total_cost']) if row_dict['total_cost'] else 0,
                    'total_loss_and_delivery': float(row_dict['total_loss_and_delivery']) if row_dict['total_loss_and_delivery'] else 0,
                    'diff_with_rank1': float(row_dict['diff_with_rank1']) if row_dict['diff_with_rank1'] else 0,
                    'delivery_topup': row_dict['delivery_topup']  # Добавляем delivery_topup JSON
                }
        
        return {
            'items': items,
            'delivery_details': delivery_details,
            'summary': summary
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting basket data for order {order_id}, rank {rank}: {e}")
        return None


def _format_single_basket(basket_data: Dict[str, Any], rank: int) -> str:
    """
    Форматирование одной корзины
    
    Args:
        basket_data: Данные корзины (items + delivery_details + summary)
        rank: Ранг корзины
    
    Returns:
        Отформатированное сообщение для одной корзины
    """
    items = basket_data['items']
    delivery_details = basket_data['delivery_details']
    summary = basket_data['summary']
    
    # Заголовок корзины
    rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")
    basket_id = summary['basket_id']
    
    if rank == 1:
        title = f"{rank_emoji} <b>{rank} место - корзина #{basket_id}</b>"
    else:
        diff = summary['diff_with_rank1']
        title = f"{rank_emoji} <b>{rank} место - корзина #{basket_id}</b> (переплата {diff:.0f}₽)"
    
    # Моноширинная таблица
    table_lines = []
    table_lines.append("Сервис   Товар         Loss Сумма Цена")
    table_lines.append("                            полка кг|л")
    table_lines.append("--------------------------------------")
    
    # Нумерация для ссылок
    link_number = 1
    links = []
    
    # Формируем строки таблицы
    for item in items:
        lsd_name = item['lsd_name'][:8].ljust(8)  # Обрезаем и выравниваем сервис
        
        # Товар (обрезаем до 13 символов)
        product_name = item['product_name']
        if len(product_name) > 13:
            product_display = product_name[:10] + "..."
        else:
            product_display = product_name[:13]
        product_display = product_display.ljust(13)
        
        # Loss (выравниваем вправо, 4 символа)
        loss = f"{item['loss']:.0f}"
        loss_display = loss.rjust(4)
        
        # Цена полка (выравниваем вправо, 5 символов)
        price_shelf = f"{item['order_item_ids_cost']:.0f}"
        price_shelf_display = price_shelf.rjust(5)
        
        # Цена кг|л (fprice, выравниваем вправо, 4 символа)
        fprice = f"{item['fprice']:.0f}"
        fprice_display = fprice.rjust(4)
        
        # Добавляем строку в таблицу
        table_lines.append(f"{lsd_name} {product_display} {loss_display} {price_shelf_display} {fprice_display}")
        
        # Сохраняем ссылку
        if item['product_url']:
            # Используем одинарные кавычки в HTML-теге для корректного парсинга
            links.append(f"{link_number}. <a href='{item['product_url']}'>{item['product_name']}</a>")
        else:
            links.append(f"{link_number}. {item['product_name']}")
        link_number += 1
    
    # Пустая строка перед итогами
    table_lines.append("")
    
    # Итоги
    goods_cost = summary['total_goods_cost']
    total_delivery_cost = summary['total_delivery_cost']
    total_loss = summary['total_loss']
    total_cost = summary['total_cost']
    
    # Извлекаем delivery_topup из JSON
    delivery_topup_dict = summary.get('delivery_topup', {})
    if isinstance(delivery_topup_dict, str):
        import json
        delivery_topup_dict = json.loads(delivery_topup_dict)
    
    # Считаем общий топап
    total_topup = sum(float(v) for v in delivery_topup_dict.values() if v)
    
    # Считаем чистую доставку (без топапа)
    pure_delivery_cost = sum(dd['delivery_cost'] for dd in delivery_details)
    
    # Ширина таблицы = 38 символов (без учета разделителей)
    table_width = 38
    # Ширина для итоговых строк = 36 символов (на 2 меньше)
    totals_width = 36
    
    # Форматируем итоговые строки с динамическими точками
    def format_total_line(label: str, value: float) -> str:
        value_str = f"{value:.0f}"
        # Количество точек = ширина для итогов - длина текста - длина числа
        dots_count = totals_width - len(label) - len(value_str)
        dots = '.' * max(1, dots_count)  # Минимум 1 точка
        return f"{label} {dots} {value_str}"
    
    # Строка: итого продукты
    table_lines.append(format_total_line("итого продукты", goods_cost))
    
    # Строка: итого топап (сервисы через запятую)
    if total_topup > 0:
        topup_lsds = [dd['lsd_name'] for dd in delivery_details if dd['topup'] > 0]
        topup_label = f"итого топап ({', '.join(topup_lsds)})" if topup_lsds else "итого топап"
        table_lines.append(format_total_line(topup_label, total_topup))
    
    # Строка: итого доставка (сервисы через запятую)
    if pure_delivery_cost > 0:
        delivery_lsds = [dd['lsd_name'] for dd in delivery_details if dd['delivery_cost'] > 0]
        delivery_label = f"итого доставка ({', '.join(delivery_lsds)})" if delivery_lsds else "итого доставка"
        table_lines.append(format_total_line(delivery_label, pure_delivery_cost))
    
    # Визуальный разделитель перед итогом
    table_lines.append("─" * table_width)
    
    # Строка: итого
    table_lines.append(format_total_line("итого", total_cost))
    
    # Пустая строка для визуального разделения
    table_lines.append("")
    
    # Строка: итого потерь и доставки (используем значение из БД)
    total_loss_and_delivery = summary['total_loss_and_delivery']
    table_lines.append(format_total_line("итого потерь и доставки", total_loss_and_delivery))
    
    # Собираем сообщение
    message_parts = [title, ""]
    message_parts.append("<pre>" + "\n".join(table_lines) + "</pre>")
    message_parts.append("")  # Пустая строка
    
    # CRITICAL FIX: Telegram не обрабатывает HTML сразу после </pre>
    # Нужно добавить текстовый разделитель
    if links:
        message_parts.append("<b>Товары:</b>")  # Текстовый заголовок перед ссылками
        message_parts.extend(links)
    
    return "\n".join(message_parts)

