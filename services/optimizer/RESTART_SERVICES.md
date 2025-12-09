# 🔧 Инструкция по перезапуску сервисов после обновления

## Что было обновлено

✅ **order-service** теперь использует **NumPy оптимизатор** (75× быстрее!)

Изменения:
- `order_optimizer_handler.py` → использует `optimize_order_unified()` с auto-выбором движка
- Добавлено логирование движка (NUMPY/LEGACY) и производительности

---

## Как перезапустить сервисы

### 1. Найти процессы

```bash
# Найти все запущенные сервисы
ps aux | grep "services/" | grep -v grep

# Или конкретно order-service
ps aux | grep "order-service" | grep -v grep
```

### 2. Остановить сервисы

```bash
# Остановить order-service (замените PID)
kill <PID>

# Или если несколько процессов
pkill -f "order-service"
```

### 3. Запустить заново

```bash
# Перейти в корень проекта
cd /Users/ss/GenAI/korzinka

# Запустить order-service
nohup python3 services/order-service/main.py > logs/order-service.log 2>&1 &

# Проверить что запустился
ps aux | grep "order-service" | grep -v grep
```

### 4. Проверить логи

```bash
# Последние логи order-service
tail -f logs/order-service.log

# Логи NumPy оптимизатора
tail -f logs/optimizer_numpy.log

# Логи Legacy оптимизатора (если используется)
tail -f logs/optimizer.log
```

---

## Тестирование

### Вручную перевести заказ в оптимизацию

```bash
# Перевести заказ в статус ANALYSIS_COMPLETE
psql $DATABASE_URL -c "UPDATE orders SET status = 'ANALYSIS_COMPLETE' WHERE id = 25;"
```

### Проверить результаты

```bash
# Статус заказа
psql $DATABASE_URL -c "SELECT id, status FROM orders WHERE id = 25;"

# Результаты оптимизации
psql $DATABASE_URL -c "
SELECT 
    basket_rank,
    total_cost,
    total_loss_and_delivery,
    total_delivery_cost
FROM basket_analyses 
WHERE order_id = 25 
ORDER BY basket_rank;
"
```

### Посмотреть логи оптимизации

```bash
# В логах order-service должна быть строка:
#   Engine: NUMPY
tail -100 logs/order-service.log | grep -A 10 "OPTIMIZING → OPTIMIZED"
```

---

## Что смотреть в логах

### ✅ Успешная оптимизация с NumPy:

```
✅ Order 25: OPTIMIZING → OPTIMIZED
   Engine: NUMPY
   Completed at: 2025-10-06 12:03:14
   Total combinations analyzed: 1,679,616
   Prefiltered: 100,000
   Best basket: #18135
   Best cost: 2019.00₽
   Execution time: 1.10s
   Performance: 1,523,509 comb/sec
```

### ⚠️ Fallback на Legacy (если NumPy недоступен):

```
⚠ NumPy недоступен, используем Legacy оптимизатор
⚙️  Запуск Legacy оптимизатора для заказа #25
...
   Engine: LEGACY
```

### ❌ Ошибка импорта:

```
❌ NumPy оптимизатор завершился с ошибкой: No module named 'order_optimizer_numpy'
⤷ Переключаемся на Legacy оптимизатор...
```

**Решение:** Проверьте что файлы на месте:
```bash
ls -la services/optimizer/order_optimizer_numpy.py
ls -la services/optimizer/optimize.py
```

---

## Откат на старую версию (если нужно)

Если что-то пошло не так, можно вернуть старый импорт:

```python
# services/order-service/order_optimizer_handler.py

# Было (NumPy):
from services.optimizer.optimize import optimize_order_unified

# Вернуть (Legacy):
from services.optimizer.order_optimizer import optimize_order
```

И использовать:
```python
result = optimize_order(
    order_id=order_id,
    db_connection_string=db_url,
    top_n=10
)
```

Затем перезапустить сервис.

---

## Полезные команды

```bash
# Проверить что NumPy доступен
python3 -c "import numpy; print(f'NumPy: {numpy.__version__}')"

# Протестировать оптимизатор вручную
cd services/optimizer
python3 optimize.py 25 --engine numpy

# Посмотреть все логи оптимизации
ls -lh ../../logs/optimizer*.log

# Очистить старые логи
> logs/optimizer_numpy.log
> logs/order-service.log
```

---

## Мониторинг производительности

### Сравнить Legacy vs NumPy:

```bash
# Legacy (старый)
time python3 services/optimizer/optimize.py 25 --engine legacy

# NumPy (новый)
time python3 services/optimizer/optimize.py 25 --engine numpy
```

Ожидаемая разница: **~75× ускорение**

---

## Проблемы и решения

### Проблема: "No module named 'order_optimizer_numpy'"

**Причина:** Неправильные пути импорта

**Решение:**
1. Проверить что файл существует: `ls services/optimizer/order_optimizer_numpy.py`
2. Проверить что sys.path настроен правильно в `optimize.py`
3. Перезапустить сервис

### Проблема: NumPy не найден

**Причина:** NumPy не установлен в venv

**Решение:**
```bash
cd /Users/ss/GenAI/korzinka
./venv/bin/pip install numpy
```

### Проблема: Оптимизация слишком медленная

**Причина:** Используется Legacy вместо NumPy

**Решение:** Проверить логи - там должно быть `Engine: NUMPY`. Если `Engine: LEGACY`, то NumPy не работает или недоступен.

---

**После перезапуска всё должно работать с NumPy оптимизатором! 🚀**
