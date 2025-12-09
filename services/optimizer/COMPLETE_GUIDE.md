# Итоговая инструкция для пользователя

## ✅ Что реализовано

### 1. Debug Mode для Optimizer (основная задача)
Создана полная инфраструктура для отладки оптимизатора с сохранением всех промежуточных данных:

**Файлы:**
- `utils/csv_exporter.py` - экспорт в CSV
- `sql/debug_tables.sql` - временные таблицы
- `order_optimizer_debug.py` - расширенный оптимизатор
- `debug_optimize.sh` - bash-скрипт для запуска
- `DEBUG_MODE.md`, `QUICKSTART_DEBUG.md` - документация

**Возможности:**
- Сохранение всех комбинаций в CSV (logs/optimizer/debug/)
- Загрузка всех данных во временные таблицы БД (_basket_*)
- Сохранение топ-10 в основные таблицы (как обычно)

### 2. Добавлено поле fprice_optimizer_id (дополнительная задача)
Улучшена трейсабилити данных:

**Файлы:**
- `sql/add_fprice_optimizer_id.sql` - миграция БД
- Обновлены: `order_optimizer.py`, `order_optimizer_debug.py`, `utils/csv_exporter.py`
- `MIGRATION_fprice_optimizer_id.md` - инструкции

**Что даёт:**
- Прямая ссылка basket_combinations → fprice_optimizer
- Возможность делать JOIN для анализа
- Полная история откуда пришли данные

---

## 🚀 Быстрый старт

### Шаг 1: Применить миграцию БД
```bash
cd /Users/ss/GenAI/korzinka
psql $DATABASE_URL -f services/optimizer/sql/add_fprice_optimizer_id.sql
```

### Шаг 2: Сделать скрипт исполняемым
```bash
chmod +x services/optimizer/debug_optimize.sh
```

### Шаг 3: Запустить debug-оптимизацию
```bash
./services/optimizer/debug_optimize.sh 16
```

Где `16` - это ID заказа для тестирования.

---

## 📊 Результаты работы

### CSV файлы (для анализа в Excel/Pandas):
```
logs/optimizer/debug/
├── order_16_basket_combinations_20250929_143022.csv
├── order_16_basket_delivery_costs_20250929_143022.csv
└── order_16_basket_analyses_20250929_143022.csv
```

### Временные таблицы в БД (для SQL-анализа):
- `_basket_combinations` - все комбинации товаров
- `_basket_delivery_costs` - стоимость доставки
- `_basket_analyses` - полный анализ с рейтингом

### Основные таблицы (продакшн):
- `basket_combinations` - топ-10 лучших корзин
- `basket_delivery_costs` - доставка для топ-10
- `basket_analyses` - анализ топ-10

---

## 🔍 Примеры SQL запросов

### Топ-10 корзин из временной таблицы:
```sql
SELECT basket_rank, basket_id, total_cost, total_loss_and_delivery
FROM _basket_analyses
ORDER BY basket_rank
LIMIT 10;
```

### Состав лучшей корзины с трейсабилити:
```sql
SELECT 
    bc.basket_id,
    bc.product_name,
    bc.lsd_name,
    bc.price,
    bc.loss,
    fpo.requested_quantity,
    fpo.base_unit
FROM _basket_combinations bc
JOIN fprice_optimizer fpo ON bc.fprice_optimizer_id = fpo.id
WHERE bc.basket_id = (
    SELECT basket_id FROM _basket_analyses 
    ORDER BY basket_rank LIMIT 1
);
```

### Анализ: сколько раз каждый вариант использовался:
```sql
SELECT 
    fpo.product_name,
    fpo.lsd_name,
    fpo.fprice,
    COUNT(DISTINCT bc.basket_id) as used_in_baskets
FROM fprice_optimizer fpo
LEFT JOIN _basket_combinations bc ON fpo.id = bc.fprice_optimizer_id
WHERE fpo.order_id = 16
GROUP BY fpo.product_name, fpo.lsd_name, fpo.fprice
ORDER BY used_in_baskets DESC;
```

---

## 📚 Документация

### Полная документация:
- `services/optimizer/DEBUG_MODE.md` - детальное описание debug-режима
- `services/optimizer/QUICKSTART_DEBUG.md` - быстрый старт
- `services/optimizer/MIGRATION_fprice_optimizer_id.md` - миграция БД
- `services/optimizer/IMPLEMENTATION_SUMMARY.md` - техническая документация

### Структура кода:
```
services/optimizer/
├── utils/
│   └── csv_exporter.py          # Экспорт в CSV
├── sql/
│   ├── debug_tables.sql         # Временные таблицы
│   └── add_fprice_optimizer_id.sql  # Миграция
├── order_optimizer.py           # Базовый (без изменений логики)
├── order_optimizer_debug.py     # С debug-режимом
└── debug_optimize.sh            # Bash-скрипт
```

---

## ⚠️ Важные замечания

1. **Временные таблицы очищаются** при каждом запуске debug-оптимизации
2. **CSV файлы накапливаются** - нужна периодическая очистка
3. **Debug-режим медленнее** обычного из-за записи данных
4. **Базовый оптимизатор не изменён** - работает как раньше
5. **Поле fprice_optimizer_id** заполняется автоматически при новых расчётах

---

## 🧪 Тестирование

### 1. Проверить что миграция применилась:
```bash
psql $DATABASE_URL -c "\d basket_combinations" | grep fprice_optimizer_id
```

### 2. Запустить debug-оптимизацию:
```bash
./services/optimizer/debug_optimize.sh 16
```

### 3. Проверить CSV файлы:
```bash
ls -lh logs/optimizer/debug/
```

### 4. Проверить временные таблицы:
```sql
SELECT COUNT(*) FROM _basket_combinations;
SELECT COUNT(*) FROM _basket_delivery_costs;
SELECT COUNT(*) FROM _basket_analyses;
```

### 5. Проверить fprice_optimizer_id:
```sql
SELECT 
    COUNT(*) as total,
    COUNT(fprice_optimizer_id) as with_id
FROM basket_combinations
WHERE order_id = 16;
```

---

## 🆘 Troubleshooting

### "permission denied" при запуске .sh
```bash
chmod +x services/optimizer/debug_optimize.sh
```

### "DATABASE_URL не найден"
Проверьте что `.env` файл находится в корневой директории проекта.

### "Таблица _basket_combinations не существует"
Временные таблицы создаются автоматически при первом запуске debug-оптимизации.

### "duplicate key value violates unique constraint"
Очистите старые данные:
```sql
SELECT clear_debug_tables();
```

---

## ✨ Готово!

Теперь у вас есть полноценный инструмент для отладки и анализа работы оптимизатора. 

**Следующие шаги:**
1. Применить миграцию БД
2. Сделать скрипт исполняемым
3. Запустить тестовую оптимизацию
4. Проанализировать результаты в CSV или SQL

Удачи! 🚀
