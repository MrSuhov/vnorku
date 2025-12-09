# Оптимизатор корзин заказов

## Описание
Система оптимизации заказов для выбора наиболее выгодного распределения товаров по ЛСД с учетом цен и доставки.

## Установка

### Быстрая установка
```bash
cd /Users/ss/GenAI/korzinka/services/optimizer
psql postgresql://korzinka_user:korzinka_pass@localhost:5432/korzinka -f install.sql
```

Это создаст:
- Таблицы: `order_combinations`, `valid_baskets`, `basket_analyses`
- Функцию: `calculate_delivery_fee()`
- Процедуры: `generate_order_combinations()`, `generate_valid_baskets()`, `calculate_optimized_baskets()`

## Быстрый старт

### 1. Оптимизировать заказ (полный пайплайн)
```bash
cd /Users/ss/GenAI/korzinka/services/optimizer
./optimize_order_fast.sh <order_id> [top_n]
```

**Пример:**
```bash
./optimize_order_fast.sh 1        # Топ-3 корзины для заказа #1
./optimize_order_fast.sh 1 5      # Топ-5 корзин для заказа #1
```

### 2. Посмотреть результаты
```bash
./show_results.sh <order_id>
```

## Пошаговое выполнение (для отладки)

### Шаг 1: Генерация комбинаций
```sql
CALL generate_order_combinations(1);

-- Проверка результата
SELECT COUNT(*) FROM order_combinations WHERE order_id = 1;
SELECT * FROM order_combinations WHERE order_id = 1 LIMIT 10;
```

### Шаг 2: Генерация валидных корзин
```sql
CALL generate_valid_baskets(1);

-- Проверка результата
SELECT COUNT(*) FROM valid_baskets WHERE order_id = 1;
SELECT * FROM valid_baskets WHERE order_id = 1 ORDER BY total_loss LIMIT 10;
```

### Шаг 3: Расчет доставки и оптимизация
```sql
CALL calculate_optimized_baskets(1, 3);

-- Проверка результата
SELECT * FROM basket_analyses WHERE order_id = 1;
```

## Структура данных

### Таблица: order_combinations
Все возможные комбинации (lsd, order_item, pieces)
- `combination_id` - уникальный ID комбинации
- `order_id` - ID заказа
- `order_item_id` - ID товара в заказе
- `product_name` - название товара
- `lsd_name` - название ЛСД
- `pieces` - количество единиц товара
- `price` - цена за единицу
- `loss` - потери относительно минимальной цены

### Таблица: valid_baskets
Валидные корзины (после фильтрации)
- `basket_id` - уникальный ID корзины
- `order_id` - ID заказа
- `item_id_1..4` - ID товаров
- `lsd_1..4` - ЛСД для каждого товара
- `pieces_1..4` - количество единиц
- `price_1..4` - цены
- `total_goods_cost` - стоимость товаров
- `total_loss` - общие потери

### Таблица: basket_analyses
Результаты оптимизации с доставкой
- `id` - ID записи
- `order_id` - ID заказа
- `lsd_breakdown` - JSON с распределением по ЛСД
- `total_cost` - итоговая стоимость
- `total_savings` - экономия (total_loss)
- `delivery_costs` - JSON с доставкой по ЛСД
- `applied_promotions` - примененные промокоды (пока не используется)

## Функции и процедуры

### calculate_delivery_fee(lsd_config_id, order_amount)
Рассчитывает доставку для ЛСД
```sql
SELECT * FROM calculate_delivery_fee(1, 300);
-- Возвращает: delivery_fee, delivery_topup, applied_rule
```

### generate_order_combinations(order_id)
Генерирует все комбинации товаров
```sql
CALL generate_order_combinations(1);
```

### generate_valid_baskets(order_id)
Генерирует и фильтрует валидные корзины
```sql
CALL generate_valid_baskets(1);
```

### calculate_optimized_baskets(order_id, top_n)
Рассчитывает доставку и сохраняет топ-N корзин
```sql
CALL calculate_optimized_baskets(1, 3);
```

## Примеры запросов

### Статистика по комбинациям
```sql
SELECT 
    order_id,
    COUNT(*) as total_combinations,
    COUNT(DISTINCT order_item_id) as products,
    COUNT(DISTINCT lsd_name) as lsd_count
FROM order_combinations
WHERE order_id = 1
GROUP BY order_id;
```

### Топ товары по loss
```sql
SELECT 
    product_name,
    lsd_name,
    price,
    loss,
    pieces
FROM order_combinations
WHERE order_id = 1
ORDER BY loss DESC
LIMIT 10;
```

### Корзины с минимальной доставкой
```sql
SELECT 
    ROW_NUMBER() OVER (ORDER BY 
        (SELECT SUM((v.value->>'fee')::numeric + (v.value->>'topup')::numeric) 
         FROM jsonb_each(delivery_costs::jsonb) v)
    ) as rank,
    total_cost,
    total_savings,
    delivery_costs
FROM basket_analyses
WHERE order_id = 1
ORDER BY rank
LIMIT 5;
```

## Производительность

### Текущие метрики (заказ с 4 товарами)
- Генерация комбинаций: ~30ms (~150-200 комбинаций)
- Генерация валидных корзин: ~13сек (~650k корзин)
- Расчет доставки (топ-3): ~25ms
- **Итого: ~13 секунд**

### Оптимизация производительности
Для заказов с большим количеством товаров:
1. Уменьшить `over_requested_quantity` в view `fprice_optimizer`
2. Добавить ограничение на количество комбинаций
3. Использовать материализованные view для кеширования

## Файлы проекта

```
services/optimizer/
├── optimizer_tables.sql              # Создание таблиц
├── optimizer_procedures.sql          # Процедуры генерации
├── delivery_calculator.sql           # Функция расчета доставки
├── calculate_optimized_baskets.sql   # Процедура оптимизации
├── optimize_order_fast.sh            # Скрипт быстрой оптимизации
└── show_results.sh                   # Скрипт вывода результатов
```

## Известные ограничения

1. **Захардкожено 4 товара** - процедура `generate_valid_baskets` работает только для заказов с 4 товарами
2. **Промокоды не учитываются** - пока используются заглушки
3. **Детали товаров не сохраняются** - в `basket_analyses` только subtotal по ЛСД
4. **Производительность** - для >5 товаров время генерации может превышать минуту

## TODO
- [ ] Динамическая генерация корзин (любое количество товаров)
- [ ] Сохранение деталей товаров в lsd_breakdown
- [ ] Интеграция промокодов
- [ ] Оптимизация производительности (индексы, партиционирование)
- [ ] Кеширование результатов
- [ ] API для интеграции с Telegram-ботом
