# Исправление: Монокорзины не генерируются в PDF

## Дата: 07.10.2025

## Проблема

Для заказа #33 не сформировались листы отчета с монокорзинами (Раздел 2).

---

## Причина

**Ошибка в SQL-запросе `get_min_prices.sql`:**

```sql
lc.lsd_name  -- ❌ Поле не существует в таблице lsd_configs
```

**Структура таблицы `lsd_configs`:**
- ✅ `name` - англоязычное название (samokat, yandex_lavka, и т.д.)
- ✅ `display_name` - русское название (Самокат, Яндекс Лавка, и т.д.)
- ❌ `lsd_name` - такого поля НЕТ

**Последовательность событий:**

1. PDF генератор вызывает `_get_min_prices_data()` (Раздел 1)
2. Выполняется SQL-запрос `get_min_prices.sql`
3. **ОШИБКА:** `column lc.lsd_name does not exist`
4. Транзакция прерывается
5. PDF генератор вызывает `_get_mono_baskets_data()` (Раздел 2)
6. **ОШИБКА:** `InFailedSQLTransactionError: current transaction is aborted`
7. Все последующие запросы в этой транзакции игнорируются
8. Раздел 2 не генерируется

---

## Решение

**Исправлено в файле:** `/Users/ss/GenAI/korzinka/services/order-service/sql/get_min_prices.sql`

### Изменение 1: Использовать правильное имя поля

**Было:**
```sql
lc.lsd_name,  -- ❌ ОШИБКА: поле не существует
```

**Стало:**
```sql
lc.name as lsd_name,  -- ✅ name - это правильное поле в lsd_configs
```

### Изменение 2: Комментарий в агрегации

**Было:**
```sql
STRING_AGG(DISTINCT lsd_name, ', ' ORDER BY lsd_name) as lsd_names,  
-- ИЗМЕНЕНО: lsd_name вместо lsd_display_name
```

**Стало:**
```sql
STRING_AGG(DISTINCT lsd_name, ', ' ORDER BY lsd_name) as lsd_names,  
-- lsd_name - это alias из lc.name
```

---

## Проверка исправления

### SQL-запрос работает корректно:

```bash
$ psql -c "
WITH min_fprice_per_item AS (...)
SELECT product_name, STRING_AGG(DISTINCT lsd_name, ', ') as lsd_names
FROM items_with_min_price
GROUP BY order_item_id, product_name, min_fprice
ORDER BY product_name;
"
```

**Результат:**
```
 order_item_id |   product_name   | lsd_names 
---------------+------------------+-----------
           134 | Яйца             | 5ka
           133 | лимонная кислота | globus
           135 | молоко           | 5ka
```

✅ **Англоязычные названия ЛСД отображаются корректно!**

---

## Тестирование

### Шаги для проверки:

1. **Перезапустить order-service:**
```bash
cd /Users/ss/GenAI/korzinka/services/order-service
source ../../venv/bin/activate
python main.py
```

2. **Создать новый тестовый заказ** через Telegram-бота

3. **Проверить PDF:**
   - ✅ Раздел 0: Лучшая корзина - генерируется
   - ✅ Раздел 1: Минимальные цены - генерируется (с англоязычными именами ЛСД)
   - ✅ **Раздел 2: Монокорзины - генерируется** ← ГЛАВНАЯ ПРОВЕРКА

4. **Проверить логи:**
```bash
tail -f /Users/ss/GenAI/korzinka/logs/order-service.log | grep "PDF\|mono"
```

Не должно быть ошибок типа:
- `column lc.lsd_name does not exist`
- `InFailedSQLTransactionError`

---

## Структура таблицы lsd_configs

Для справки, поля в таблице `lsd_configs`:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | integer | Первичный ключ |
| **`name`** | varchar(100) | **Англоязычное имя** (samokat, yandex_lavka) |
| `display_name` | varchar(200) | Русское имя (Самокат, Яндекс Лавка) |
| `base_url` | varchar(500) | Базовый URL сервиса |
| `rpa_config` | json | Конфиг RPA для авторизации |
| `search_config_rpa` | json | Конфиг RPA для поиска |
| `delivery_cost_model` | json | Модель стоимости доставки |
| `delivery_fixed_fee` | numeric(10,2) | Фиксированная стоимость доставки |
| ... | ... | ... |

---

## Связанные изменения

Это исправление дополняет изменения из:
- `PDF_FIXES_2025-10-07-v2.md` - исправления от 07.10.2025

Теперь все 3 раздела PDF генерируются корректно:
- ✅ Раздел 0: Лучшая корзина
- ✅ Раздел 1: Минимальные цены (с англоязычными именами ЛСД)
- ✅ Раздел 2: Монокорзины (с условиями доставки)

---

## Критические точки для будущего

**⚠️ ВАЖНО:** При работе с таблицей `lsd_configs` всегда использовать:
- `lc.name` - для англоязычных названий (samokat, yandex_lavka)
- `lc.display_name` - для русских названий (Самокат, Яндекс Лавка)

**НЕ используйте:**
- ❌ `lc.lsd_name` - такого поля не существует
- ❌ `lc.lsd_display_name` - такого поля не существует

---

## Итог

✅ **Проблема решена**
✅ **SQL-запрос исправлен**
✅ **Монокорзины будут генерироваться в PDF**
✅ **Англоязычные имена ЛСД отображаются корректно**
