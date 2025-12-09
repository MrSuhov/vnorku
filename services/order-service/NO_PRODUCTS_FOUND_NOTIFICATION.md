# Уведомление "Подходящих товаров не нашлось"

## Описание функционала

Когда для заказа не найдено подходящих товаров (нет данных в `fprice_optimizer`), пользователю автоматически отправляется уведомление в Telegram.

## Изменения в коде

### 1. `order_optimizer_handler.py`

**Что изменилось:**
- Добавлена обработка специфичного статуса `"no_data"` из оптимизатора
- При отсутствии товаров заказ переводится в `FAILED` с понятным описанием
- В `error_details` сохраняется:
  - `error_type`: `"no_products_found"`
  - `message`: `"Подходящих товаров не нашлось"`
  - `user_message`: `"❌ Подходящих товаров не нашлось"`
  - `failed_at`: timestamp

**Функция:** `handle_analysis_complete()`

```python
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
    
    return {
        "success": False,
        "error": "no_products_found",
        "user_message": "❌ Подходящих товаров не нашлось"
    }
```

### 2. `main.py`

#### 2.1. Функция `process_analysis_complete_orders()`

**Что изменилось:**
- После неудачной оптимизации проверяется наличие `user_message` в результате
- Если `user_message` есть, отправляется уведомление пользователю через Telegram

```python
if not optimization_result.get('success'):
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
```

#### 2.2. Новая функция `process_failed_orders()`

**Назначение:**
- Обработка FAILED заказов с отправкой уведомлений
- Резервный механизм для гарантированной отправки (если что-то пошло не так в `process_analysis_complete_orders`)

**Логика:**
1. Ищет FAILED заказы, для которых `results_sent_at == None`
2. Проверяет наличие `user_message` в `error_details`
3. Отправляет уведомление в Telegram
4. Обновляет `results_sent_at` после успешной отправки

```python
async def process_failed_orders():
    """
    Обработка заказов в статусе FAILED.
    Отправляет уведомления пользователям и обновляет статус.
    """
    # Получаем FAILED заказы без уведомлений
    result = await db.execute(
        select(DBOrder).where(
            DBOrder.status == OrderStatus.FAILED
        ).where(
            DBOrder.results_sent_at.is_(None)
        )
    )
    failed_orders = result.scalars().all()
    
    for order in failed_orders:
        user_message = order.error_details.get('user_message')
        if user_message and order.tg_group:
            success = await send_telegram_message(
                chat_id=order.tg_group,
                text=user_message,
                reply_to_message_id=order.telegram_message_id,
                order_id=order.id
            )
            
            if success:
                order.results_sent_at = datetime.now()
                await db.commit()
```

#### 2.3. Функция `monitor_analyzing_orders()`

**Что изменилось:**
- Добавлен вызов `process_failed_orders()` в цикл мониторинга (каждые 10 секунд)

```python
async def monitor_analyzing_orders():
    while True:
        await asyncio.sleep(10)
        
        # 1. Обрабатываем завершенные анализы
        await process_analysis_complete_orders()
        
        # 2. Обрабатываем оптимизированные заказы
        await process_optimized_orders()
        
        # 3. Обрабатываем FAILED заказы (отправка уведомлений)
        await process_failed_orders()  # <-- НОВОЕ
        
        # ... остальная логика
```

## Флоу работы

```
1. Optimizer: fprice_optimizer пуста
   ↓
2. order_optimizer.py возвращает {"status": "no_data"}
   ↓
3. order_optimizer_handler.py:
   - Устанавливает FAILED
   - Сохраняет user_message в error_details
   - Возвращает {success: False, user_message: "..."}
   ↓
4. main.py (process_analysis_complete_orders):
   - Обнаруживает неудачу оптимизации
   - Отправляет user_message в Telegram
   ↓
5. (Резервный) main.py (process_failed_orders):
   - Проверяет FAILED заказы без results_sent_at
   - Отправляет уведомление если не было отправлено
   - Обновляет results_sent_at
```

## Логирование

### Успешный сценарий:
```
⚠️ Order 30: No products found in fprice_optimizer
❌ Order 30: OPTIMIZING → FAILED (no products found)
❌ Optimization failed for order 30
   Error: no_products_found
📤 Sending failure notification to user for order 30
✅ Telegram message sent to -1001234567890
💾 Logged message to DB (message_id=123, order_id=30)
```

### Резервный сценарий (если первая отправка не сработала):
```
📋 Found 1 FAILED orders without notification
📤 Sending FAILED notification for order 30 (error_type=no_products_found)
✅ FAILED notification sent successfully for order 30
```

## Тестирование

Для тестирования создайте заказ, для которого поиск не найдет товаров в ЛСД. Убедитесь что:

1. В логах появляется `WARNING Нет данных в fprice_optimizer`
2. Заказ переводится в статус `FAILED`
3. Пользователю отправляется сообщение "❌ Подходящих товаров не нашлось"
4. Сообщение логируется в таблицу `user_messages`
5. Поле `results_sent_at` обновляется после успешной отправки

## Дополнительные заметки

- Уведомление отправляется в ту же группу (`tg_group`) с ответом на исходное сообщение (`reply_to_message_id`)
- Все сообщения логируются в таблицу `user_messages` для аудита
- Механизм устойчив к сбоям: если отправка не удалась сразу, повторная попытка произойдет при следующей итерации мониторинга
- Используется поле `results_sent_at` для предотвращения дублирования уведомлений
