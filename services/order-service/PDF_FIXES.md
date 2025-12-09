# Исправления PDF-генератора

## Дата: 2025-10-07

## Проблемы:
1. **PDF одностраничный** - отсутствовал раздел 2 с моно-корзинами
2. **Кириллица не работала** - шрифты DejaVu не были найдены

## Исправления:

### 1. Добавлена поддержка моно-корзин в оптимизаторе

**Файл:** `/Users/ss/GenAI/korzinka/services/optimizer/order_optimizer_numpy.py`

**Изменения:**
- В методе `select_top_baskets()` добавлено определение моно-корзин
- Моно-корзина = все товары из одного LSD (`len(lsd_ids_in_basket) == 1`)
- Добавлен флаг `is_mono_basket` в данные корзины
- Флаг сохраняется в таблицу `basket_analyses`

**SQL:**
```sql
ALTER TABLE basket_analyses ADD COLUMN is_mono_basket BOOLEAN DEFAULT FALSE;
CREATE INDEX idx_basket_analyses_is_mono ON basket_analyses(order_id, is_mono_basket) WHERE is_mono_basket = TRUE;
```

### 2. Исправлены пути к шрифтам DejaVu

**Файл:** `/Users/ss/GenAI/korzinka/services/order-service/pdf_generator.py`

**Изменения:**
- Добавлен актуальный путь к шрифтам Homebrew:
  `/opt/homebrew/Caskroom/font-dejavu/2.37/dejavu-fonts-ttf-2.37/ttf/DejaVuSans.ttf`
- Поиск шрифтов теперь начинается с актуального пути

**Установка шрифтов:**
```bash
brew install font-dejavu
```

### 3. Добавлен PageBreak между разделами

**Файл:** `/Users/ss/GenAI/korzinka/services/order-service/pdf_generator.py`

**Изменения:**
- После раздела 1 добавлен `PageBreak()` для начала раздела 2 с новой страницы
- Гарантирует многостраничность PDF

### 4. Обновлена модель БД

**Файл:** `/Users/ss/GenAI/korzinka/shared/database/models.py`

**Изменения:**
- Добавлено поле `is_mono_basket` в модель `BasketAnalysis`
- Приведена модель в соответствие с реальной структурой таблицы

## Тестирование:

### Проверка шрифтов:
```bash
ls -la /opt/homebrew/Caskroom/font-dejavu/2.37/dejavu-fonts-ttf-2.37/ttf/DejaVuSans.ttf
```

### Проверка БД:
```sql
-- Проверить наличие поля is_mono_basket
\d basket_analyses

-- Проверить моно-корзины для заказа
SELECT basket_id, is_mono_basket, total_cost 
FROM basket_analyses 
WHERE order_id = 25 AND is_mono_basket = TRUE
ORDER BY total_cost;
```

### Тестовый заказ:
```bash
# Создать новый заказ и дождаться статуса OPTIMIZED
# PDF должен содержать:
# - Раздел 1: Минимальные цены (первая страница)
# - Раздел 2: Монокорзины (вторая страница+)
# - Кириллица должна отображаться корректно
```

## Результат:

✅ PDF теперь многостраничный с разделом 1 и 2
✅ Кириллица отображается корректно с шрифтом DejaVu
✅ Моно-корзины определяются автоматически при оптимизации
✅ Логи показывают количество моно-корзин в топ-10

## Дополнительно:

### Логи оптимизатора:
Теперь показывают метку [МОНО] или [МУЛЬТИ] для каждой корзины в топ-3:
```
  #1 [МОНО]: basket_id=12345, loss+delivery=150.00₽, итого=2500.00₽
  #2 [МУЛЬТИ]: basket_id=12346, loss+delivery=155.00₽, итого=2480.00₽
  #3 [МОНО]: basket_id=12347, loss+delivery=160.00₽, итого=2520.00₽
Моно-корзин в топ-10: 3
```

### Структура SQL-запроса get_mono_baskets.sql:
- Ищет корзины где `COUNT(DISTINCT lsd_config_id) = 1`
- Возвращает детали корзины и товаров
- Сортирует по `total_cost ASC`
