# Изменения в PDF-генераторе: Использование актуальных данных о доставке

**Дата:** 2025-10-10  
**Задача:** Использовать актуальные данные о доставке из `lsd_stocks.delivery_cost_model` вместо устаревших из `lsd_configs.delivery_cost_model`

---

## Реализованные изменения

### 1. Обновление SQL-запроса для монокорзин

**Файл:** `services/order-service/sql/get_mono_baskets.sql`

**Изменения:**
- Заменено `lc.delivery_cost_model` (из `lsd_configs`) на `bc.delivery_cost_model` (из `basket_combinations`)
- `basket_combinations.delivery_cost_model` копируется из актуальных данных `lsd_stocks` при создании корзины
- Добавлены комментарии в SQL о источнике данных

**Обоснование:**
- `lsd_configs.delivery_cost_model` содержит статичные/дефолтные данные
- `lsd_stocks.delivery_cost_model` обновляется при каждом RPA-поиске и содержит актуальную информацию
- `basket_combinations.delivery_cost_model` копируется из `lsd_stocks` при формировании корзины

---

### 2. Обновление SQL-запроса для лучшей корзины

**Файл:** `services/order-service/pdf_generator.py`, метод `_get_best_basket_data()`

**Изменения:**
- Добавлено извлечение `delivery_cost_model` для каждого LSD в лучшей корзине
- Используется `basket_combinations.delivery_cost_model` через подзапрос
- Для каждого `lsd_config_id` берётся последняя запись из `basket_combinations` (ORDER BY id DESC)

**Код:**
```sql
SELECT DISTINCT ON (lsd_config_id) 
    lsd_config_id,
    delivery_cost_model
FROM basket_combinations
WHERE basket_id = ba.basket_id AND order_id = :order_id
ORDER BY lsd_config_id, id DESC
```

---

### 3. Добавление логирования источника данных

**Файл:** `services/order-service/pdf_generator.py`

**Добавлено логирование в:**

1. **Метод `_get_best_basket_data()`** (строки ~345-353):
   ```python
   for lsd in lsds:
       dcm = lsd.get('delivery_cost_model')
       if dcm:
           logger.info(f"📊 [Best Basket] Using delivery_cost_model from basket_combinations for {lsd.get('lsd_name')}")
       else:
           logger.warning(f"⚠️ [Best Basket] No delivery_cost_model found for {lsd.get('lsd_name')}")
   ```

2. **Метод `_get_mono_baskets_data()`** (строки ~475-483):
   ```python
   dcm = row_dict.get('delivery_cost_model')
   lsd_name = row_dict.get('lsd_display_name', 'unknown')
   if dcm:
       logger.info(f"📊 [Mono Basket] Using delivery_cost_model from basket_combinations for {lsd_name}")
   else:
       logger.warning(f"⚠️ [Mono Basket] No delivery_cost_model found for {lsd_name}")
   ```

3. **Метод `_parse_delivery_model()`** (строки ~926-929):
   ```python
   logger.debug(f"🔍 [Parse Delivery] Input type: {type(delivery_cost_model).__name__}")
   if delivery_cost_model:
       logger.debug(f"🔍 [Parse Delivery] Input data: {str(delivery_cost_model)[:200]}...")
   ```

---

### 4. Добавление условий доставки в раздел "Лучшая корзина"

**Файл:** `services/order-service/pdf_generator.py`, метод `_create_section0_best_basket()`

**Изменения:**
- Добавлен блок отображения условий доставки для каждого LSD в лучшей корзине
- Условия доставки выводятся после таблицы товаров
- Для каждого LSD вызывается `_parse_delivery_model()` для форматирования данных

**Код (строки ~643-666):**
```python
# Добавляем условия доставки для каждого LSD
lsds = data.get('lsds', [])
if lsds:
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("<b>Условия доставки по сервисам:</b>", self.bold_style))
    story.append(Spacer(1, 0.2*cm))
    
    for lsd in lsds:
        lsd_name = lsd.get('lsd_name', 'Неизвестно')
        delivery_cost_model = lsd.get('delivery_cost_model')
        
        if delivery_cost_model:
            delivery_info = self._parse_delivery_model(delivery_cost_model)
            story.append(Paragraph(f"<b>{lsd_name}:</b>", self.bold_style))
            for line in delivery_info.split('\n'):
                if line.strip():
                    story.append(Paragraph(line, self.body_style))
            story.append(Spacer(1, 0.2*cm))
        else:
            logger.warning(f"⚠️ No delivery_cost_model for {lsd_name} in best basket")
            story.append(Paragraph(f"<b>{lsd_name}:</b> Данные о доставке отсутствуют", self.body_style))
            story.append(Spacer(1, 0.2*cm))
```

---

### 5. Обновление docstring метода `_get_best_basket_data()`

**Файл:** `services/order-service/pdf_generator.py`

**Добавлен комментарий:**
```python
"""
Получение данных лучшей корзины (rank=1)

ВАЖНО: delivery_cost_model берётся из актуальных данных basket_combinations
(которые копируются из lsd_stocks), а не из устаревших lsd_configs
"""
```

---

## Архитектура данных о доставке

### Поток данных:

```
RPA Search (поиск товаров)
    ↓
Извлечение delivery_cost_model с сайта ЛСД
    ↓
Сохранение в lsd_stocks.delivery_cost_model (JSONB)
    ↓
Копирование в basket_combinations.delivery_cost_model при создании корзины
    ↓
Использование в PDF-отчёте
```

### Таблицы и поля:

1. **`lsd_configs.delivery_cost_model`** (JSON)
   - Статичные/дефолтные данные
   - НЕ используется в PDF-отчёте

2. **`lsd_stocks.delivery_cost_model`** (JSON)
   - Актуальные данные, извлечённые через RPA
   - Обновляются при каждом поиске товаров
   - Источник данных для `basket_combinations`

3. **`basket_combinations.delivery_cost_model`** (JSON)
   - Копия из `lsd_stocks` на момент создания корзины
   - **Используется в PDF-отчёте**

---

## Тестирование

### План тестирования:

1. Запустить RPA-поиск для заказа
2. Проверить, что `lsd_stocks.delivery_cost_model` заполнен
3. Запустить оптимизацию корзин
4. Проверить, что `basket_combinations.delivery_cost_model` заполнен
5. Сгенерировать PDF-отчёт
6. Проверить логи на наличие сообщений:
   - `📊 [Best Basket] Using delivery_cost_model from basket_combinations`
   - `📊 [Mono Basket] Using delivery_cost_model from basket_combinations`
7. Проверить PDF-отчёт:
   - Раздел "Лучшая корзина" содержит "Условия доставки по сервисам"
   - Раздел "Монокорзины" содержит "Условия доставки" для каждой корзины
8. Сравнить данные в PDF с данными в БД:
   ```sql
   SELECT lsd_config_id, delivery_cost_model 
   FROM basket_combinations 
   WHERE order_id = <order_id> 
   LIMIT 5;
   ```

### Ожидаемый результат:

- Условия доставки в PDF соответствуют актуальным данным из `lsd_stocks`
- Отсутствуют warning логи о missing `delivery_cost_model`
- PDF-отчёт содержит корректную информацию о стоимости доставки

---

## Потенциальные проблемы

### 1. Отсутствие `delivery_cost_model` в `basket_combinations`

**Причина:** RPA не извлёк данные о доставке при поиске товаров

**Решение:** 
- Проверить RPA-конфиг для данного ЛСД
- Убедиться, что `delivery_ranges.enabled: true` в `search_config_rpa`
- Проверить логи RPA на ошибки извлечения

### 2. Несоответствие структуры JSON

**Причина:** Формат `delivery_cost_model` отличается от ожидаемого

**Решение:**
- Метод `_parse_delivery_model()` содержит проверки структуры
- При ошибке возвращается fallback: "Данные о доставке отсутствуют"
- Проверить логи DEBUG для диагностики

### 3. Пустой `delivery_cost_model` в PDF

**Причина:** Данные не скопировались из `lsd_stocks` в `basket_combinations`

**Решение:**
- Проверить код создания `basket_combinations` в оптимизаторе
- Убедиться, что fallback из `lsd_configs` работает корректно

---

## Файлы изменений

1. `services/order-service/sql/get_mono_baskets.sql` - SQL-запрос для монокорзин
2. `services/order-service/pdf_generator.py` - генератор PDF с обновлённой логикой
3. `services/order-service/PDF_DELIVERY_FIX_2025-10-10.md` - данный документ

---

## Статус

✅ **Реализовано:**
- Шаг 1: Обновление SQL для монокорзин
- Шаг 2: Проверка SQL для best_basket
- Шаг 3: Обновление SQL для best_basket
- Шаг 4: Обновление метода `_create_section0_best_basket`
- Шаг 5: Добавление логирования

⏭️ **Следующие шаги:**
- Тестирование пользователем
- Проверка логов
- Верификация данных в PDF

---

## Контакты

При возникновении проблем проверьте логи:
- RPA Service: `/Users/ss/GenAI/korzinka/logs/rpa_service.log`
- Order Service: `/Users/ss/GenAI/korzinka/logs/order_service.log`
