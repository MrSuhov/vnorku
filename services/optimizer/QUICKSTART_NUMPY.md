# 🚀 Quick Start: NumPy Optimizer

**Ускорение оптимизации в ~75 раз!**

## Быстрый старт

```bash
# Оптимизация заказа (автоматический выбор движка)
./services/optimizer/optimize_order_py.sh 25

# Или через Python напрямую
python3 services/optimizer/optimize.py 25
```

## Результаты

- **Время:** ~1 секунда для 1.68M комбинаций
- **Производительность:** ~1,500,000 комбинаций/секунду
- **Ускорение:** 75× относительно старой версии

## Параметры

```bash
# Принудительно NumPy, топ-5 корзин
./optimize_order_py.sh 25 --engine numpy --top-n 5

# Уменьшить предфильтрацию для ускорения
./optimize_order_py.sh 25 --top-k-prefilter 50000

# Использовать старую версию
./optimize_order_py.sh 25 --engine legacy
```

## Просмотр результатов

```bash
# Лучшие корзины
psql $DATABASE_URL -c "
SELECT basket_rank, total_cost, total_loss_and_delivery 
FROM basket_analyses 
WHERE order_id = 25 
ORDER BY basket_rank;
"

# Логи
tail -f ../../logs/optimizer_numpy.log
```

## Документация

Полная документация: [NUMPY_INTEGRATION.md](./NUMPY_INTEGRATION.md)

## Требования

- Python 3.8+
- NumPy (устанавливается автоматически из requirements.txt)
- PostgreSQL 13+

## Установка

```bash
# Если NumPy не установлен
pip install numpy

# Или через requirements.txt
pip install -r requirements.txt
```

---

**Больше информации:** См. [NUMPY_INTEGRATION.md](./NUMPY_INTEGRATION.md)
