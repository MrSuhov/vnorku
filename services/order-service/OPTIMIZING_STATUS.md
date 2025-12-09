# Добавление статусов OPTIMIZING и RESULTS_SENT

## Что сделано

### 1. Добавлены новые статусы в Enum
**Файл**: `shared/models/base.py`

```python
class OrderStatus(str, Enum):
    NEW = "new"
    ANALYZING = "analyzing"
    ANALYSIS_COMPLETE = "analysis_complete"
    OPTIMIZING = "optimizing"          # НОВЫЙ
    OPTIMIZED = "optimized"
    RESULTS_SENT = "results_sent"      # НОВЫЙ
    CONFIRMED = "confirmed"
    ...
```

### 2. Добавлены timestamp поля в БД
**Таблица**: `orders`

Новые колонки:
- `optimization_started_at` - когда началась оптимизация
- `optimization_completed_at` - когда завершилась оптимизация
- `results_sent_at` - когда результаты отправлены пользователю

Созданы индексы для быстрого поиска.

### 3. Разделена логика обработки

#### Функция `process_analysis_complete_orders()`
**Задача**: ANALYSIS_COMPLETE → OPTIMIZING → OPTIMIZED

**Алгоритм**:
1. Находит заказы в `ANALYSIS_COMPLETE`
2. Переводит в `OPTIMIZING` (+ `optimization_started_at`)
3. Запускает оптимизатор
4. При успехе → `OPTIMIZED` (+ `optimization_completed_at`)
5. При ошибке → `FAILED`

#### Функция `process_optimized_orders()` (НОВАЯ)
**Задача**: OPTIMIZED → отправка результатов → RESULTS_SENT

**Алгоритм**:
1. Находит заказы в `OPTIMIZED`
2. Читает результаты из `basket_analyses` и `basket_combinations`
3. Формирует сообщение для Telegram
4. Отправляет пользователю
5. При успехе → `RESULTS_SENT` (+ `results_sent_at`)
6. При ошибке → остаётся `OPTIMIZED` (можно повторить)

### 4. Обновлён обработчик оптимизации
**Файл**: `services/order-service/order_optimizer_handler.py`

Функция `handle_analysis_complete()` теперь:
- Принимает `AsyncSession` для работы с БД
- Управляет переходами статусов
- Записывает timestamps
- Обрабатывает ошибки с откатом статуса

### 5. Обновлён мониторинг
**Файл**: `services/order-service/main.py`
**Функция**: `monitor_analyzing_orders()`

Теперь каждые 10 секунд:
1. Обрабатывает `ANALYSIS_COMPLETE` → запуск оптимизатора
2. Обрабатывает `OPTIMIZED` → отправка результатов
3. Проверяет зависшие `ANALYZING` заказы (существующий код)

---

## Жизненный цикл заказа

```
NEW
  ↓
CONFIRMED (пользователь подтвердил)
  ↓
ANALYZING (RPA поиск товаров, ~2-5 мин)
  ↓
ANALYSIS_COMPLETE (поиск завершён)
  ↓
OPTIMIZING (запуск оптимизатора, ~15-30 сек)
  ↓
OPTIMIZED (оптимизация завершена, результаты готовы)
  ↓
RESULTS_SENT (результаты отправлены пользователю)
  ↓
... дальнейшая обработка ...
```

---

## Логи

### Успешный цикл:

```
📋 Found 1 order in ANALYSIS_COMPLETE status
🎯 Starting optimization for order #16...
  🎯 Order 16: ANALYSIS_COMPLETE → OPTIMIZING
     Started at: 2025-09-29 14:30:00

[Оптимизатор работает...]

  ✅ Order 16: OPTIMIZING → OPTIMIZED
     Completed at: 2025-09-29 14:30:15
✅ Order 16 optimized successfully:
   • Analyzed: 472,392 combinations
   • Best basket: #1
   • Best cost: 1234.56₽
   • Time: 15.67s

📋 Found 1 order in OPTIMIZED status
📤 Preparing results for order #16...
📊 Found 6 optimized items for order 16
💬 Sending results to Telegram group...
✅ Results sent successfully for order 16
✅ Order 16: OPTIMIZED → RESULTS_SENT
   Sent at: 2025-09-29 14:30:20
```

### При ошибке оптимизации:

```
🎯 Starting optimization for order #16...
  🎯 Order 16: ANALYSIS_COMPLETE → OPTIMIZING
❌ Order 16: OPTIMIZING → FAILED
   Error: DATABASE_URL not configured
```

### При ошибке отправки:

```
📤 Preparing results for order #16...
💬 Sending results to Telegram group...
❌ Failed to send results for order 16
(Заказ остаётся в OPTIMIZED для повторной попытки)
```

---

## Преимущества новой схемы

✅ **Разделение ответственности**: оптимизация и отправка - разные этапы  
✅ **Прозрачность**: всегда понятно на каком этапе заказ  
✅ **Надёжность**: можно отследить где зависло  
✅ **Переиспользование**: результаты можно отправить повторно без пересчёта  
✅ **Масштабируемость**: легко добавить промежуточные этапы  

---

## Файлы изменены

1. ✅ `shared/models/base.py` - добавлены статусы `OPTIMIZING` и `RESULTS_SENT`
2. ✅ `orders` таблица - добавлены timestamp поля
3. ✅ `services/order-service/order_optimizer_handler.py` - обновлён обработчик
4. ✅ `services/order-service/main.py` - разделена логика на две функции
5. ✅ Миграция создана: `migrations/versions/2025_09_29_add_optimization_timestamps.py`

---

## Тестирование

### Полный цикл:
```bash
# 1. Переведите заказ в ANALYSIS_COMPLETE
psql postgresql://korzinka_user:korzinka_pass@localhost:5432/korzinka -c "UPDATE orders SET status = 'analysis_complete' WHERE id = 16"

# 2. Смотрите логи Order-service
tail -f logs/order-service.log

# Через ~10 секунд:
# - Запустится оптимизация (ANALYSIS_COMPLETE → OPTIMIZING → OPTIMIZED)
# - Отправятся результаты (OPTIMIZED → RESULTS_SENT)
```

### Проверка timestamps:
```sql
SELECT 
    id, 
    status, 
    analysis_completed_at,
    optimization_started_at,
    optimization_completed_at,
    results_sent_at
FROM orders 
WHERE id = 16;
```

---

## TODO (опционально)

- [ ] Добавить защиту от зависания в `OPTIMIZING` (timeout 5 минут)
- [ ] Улучшить форматирование сообщения (читать из `basket_analyses` вместо view)
- [ ] Добавить retry логику для отправки результатов
- [ ] Логировать детали отправки в `order.error_details` при ошибках
