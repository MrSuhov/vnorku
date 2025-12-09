# PDF Отчеты по заказам

## Описание

Модуль генерации PDF-отчетов для заказов Korzinka. Отчет содержит два раздела:

1. **Минимальные цены** - товары с нулевым loss (без переплат)
2. **Монокорзины** - лучшие моно-корзины для каждого LSD с информацией о доставке

## Структура файлов

```
services/order-service/
├── pdf_generator.py              # Генератор PDF-отчетов
├── telegram_document_sender.py   # Отправка документов в Telegram
├── sql/
│   ├── get_min_prices.sql       # SQL для минимальных цен
│   └── get_mono_baskets.sql     # SQL для моно-корзин
└── main.py                       # Интеграция в основной сервис
```

## Установка

### 1. Установить зависимости

```bash
cd /Users/ss/GenAI/korzinka
pip install reportlab==4.0.7
```

### 2. Установить шрифты DejaVu (для поддержки кириллицы)

**macOS:**
```bash
brew install font-dejavu
```

**Linux:**
```bash
sudo apt-get install fonts-dejavu-core
```

**Windows:**
Скачать шрифты с https://dejavu-fonts.github.io/ и установить вручную.

### 3. Применить миграцию БД

```bash
psql postgresql://korzinka_user:korzinka_pass@localhost:5432/korzinka \
  -f /Users/ss/GenAI/korzinka/sql/add_document_fields_to_user_messages.sql
```

## Использование

### Автоматическая отправка

При достижении статуса `OPTIMIZED` заказ автоматически:
1. Генерирует текстовое сообщение с топ-1 корзиной
2. Генерирует PDF-отчет с детальной информацией
3. Отправляет оба сообщения в Telegram-группу пользователя

### Ручная генерация PDF

```python
from pdf_generator import OrderReportGenerator
from shared.database import get_async_session

async def generate_pdf_manually(order_id: int):
    async for db in get_async_session():
        generator = OrderReportGenerator(order_id, db)
        pdf_bytes = await generator.generate_report()
        
        # Сохранить в файл
        with open(f'/tmp/order_{order_id}.pdf', 'wb') as f:
            f.write(pdf_bytes)
        
        print(f"PDF saved: {len(pdf_bytes)} bytes")
        break

# Запуск
import asyncio
asyncio.run(generate_pdf_manually(16))
```

## Формат PDF-отчета

### Раздел 1: Минимальные цены

Таблица с колонками:
- **Товар** - название товара из заказа
- **Сервис** - LSD с минимальной ценой (может быть несколько через запятую)
- **Лучшая цена** - fprice (цена за базовую единицу)
- **Ед. изм.** - базовая единица измерения (кг, л, шт)
- **Кол-во** - базовое количество в упаковке
- **Сумма на полке** - итоговая стоимость для запрошенного количества
- **Кол-во в заказе** - запрошенное количество
- **Ед. изм. в заказе** - запрошенная единица измерения
- **Формула** - формула расчета fprice (например: "160 руб / 0.25 кг = 640 руб/кг")

### Раздел 2: Монокорзины

Для каждого LSD (отсортированные по стоимости):

**Заголовок:** `2.X. {LSD название} - {стоимость} руб`

**Таблица товаров:**
- Товар
- Цена
- Кол-во
- Ед.изм
- Стоимость

**Итоги:**
- Итого товары: X руб
- Топап: X руб
- Доставка: X руб
- Потери: X руб
- **ВСЕГО: X руб**
- Итого потерь и доставок: X руб

**Условия доставки:**
- Стоимость комплектации: X руб
- Минимальная сумма заказа: X руб
- Диапазоны доставки:
  - От 0 руб: 149 руб
  - От 1000 руб: 99 руб
  - От 2000 руб: бесплатно

## Дизайн

- **Ориентация:** альбомная (landscape A4)
- **Цветовая схема:** серо-белая
  - Заголовки таблиц: темно-серый фон (#4A4A4A), белый текст
  - Чередующиеся строки: белый / светло-серый (#F5F5F5)
- **Шрифты:** DejaVuSans (с поддержкой кириллицы)
- **Формат цен:** "руб" (не символ ₽)

## SQL-запросы

### get_min_prices.sql

Находит минимальный fprice для каждого товара и все LSD с этой ценой.

**Параметры:** `:order_id`

**Возвращает:**
- order_item_id
- product_name
- lsd_names (через запятую)
- fprice
- base_unit
- base_quantity
- requested_quantity
- requested_unit
- price
- found_unit

### get_mono_baskets.sql

Находит все моно-корзины для заказа с деталями товаров и условиями доставки.

**Параметры:** `:order_id`

**Возвращает:**
- basket_id
- lsd_display_name
- total_cost
- total_goods_cost
- total_delivery_cost
- total_loss
- delivery_topup
- delivery_fixed_fee
- delivery_cost_model
- items (JSON массив товаров)

## Логирование

Все отправленные документы логируются в таблицу `user_messages`:

```sql
SELECT 
    id,
    order_id,
    chat_id,
    is_document,
    filename,
    file_size,
    response_status,
    created_at
FROM user_messages
WHERE is_document = true
ORDER BY created_at DESC;
```

## Устранение неполадок

### Ошибка: "DejaVuSans font not found"

**Решение:** Установить шрифты DejaVu (см. раздел "Установка")

Если не удается установить, PDF будет использовать Helvetica (может некорректно отображать кириллицу).

### Ошибка: "No data for PDF generation"

**Возможные причины:**
1. В заказе нет товаров с loss=0
2. Нет моно-корзин для данного заказа

**Решение:** Проверить данные в БД:

```sql
-- Проверить товары с loss=0
SELECT * FROM lsd_stocks 
WHERE order_id = 16 AND loss = 0;

-- Проверить моно-корзины
SELECT * FROM basket_analyses 
WHERE order_id = 16 AND is_mono_basket = true;
```

### PDF-файл слишком большой

**Решение:** PDF оптимизирован для небольшого размера (обычно < 100 KB). Если файл больше:
1. Проверить количество товаров в заказе
2. Проверить размер таблиц

### Telegram не принимает PDF

**Лимиты Telegram:**
- Максимальный размер файла: 50 МБ
- Таймаут загрузки: 60 секунд

**Решение:** Наши PDF обычно < 1 МБ, проблем быть не должно.

## Тестирование

### 1. Unit-тест SQL-запросов

```bash
# Минимальные цены
psql -d korzinka -c "
\i /Users/ss/GenAI/korzinka/services/order-service/sql/get_min_prices.sql
" -v order_id=16

# Моно-корзины
psql -d korzinka -c "
\i /Users/ss/GenAI/korzinka/services/order-service/sql/get_mono_baskets.sql
" -v order_id=16
```

### 2. Тест генерации PDF

```python
import asyncio
from pdf_generator import OrderReportGenerator
from shared.database import get_async_session

async def test_pdf():
    async for db in get_async_session():
        generator = OrderReportGenerator(16, db)
        pdf_bytes = await generator.generate_report()
        
        if pdf_bytes:
            with open('/tmp/test_order_16.pdf', 'wb') as f:
                f.write(pdf_bytes)
            print(f"✅ PDF generated: {len(pdf_bytes)} bytes")
        else:
            print("❌ PDF generation failed")
        break

asyncio.run(test_pdf())
```

### 3. Интеграционный тест

1. Создать тестовый заказ через полный флоу
2. Дождаться статуса OPTIMIZED
3. Проверить отправку в Telegram:
   - Текстовое сообщение с топ-1 корзиной
   - PDF-файл с детальным отчетом
4. Открыть PDF и проверить:
   - Корректность кириллицы
   - Читабельность таблиц
   - Корректность данных

## Мониторинг

### Проверка отправленных PDF

```sql
-- Последние 10 отправленных PDF
SELECT 
    um.id,
    um.order_id,
    o.status as order_status,
    um.filename,
    um.file_size / 1024 as size_kb,
    um.response_status,
    um.error_message,
    um.created_at
FROM user_messages um
LEFT JOIN orders o ON o.id = um.order_id
WHERE um.is_document = true
ORDER BY um.created_at DESC
LIMIT 10;
```

### Средний размер PDF

```sql
SELECT 
    COUNT(*) as total_pdfs,
    AVG(file_size / 1024) as avg_size_kb,
    MIN(file_size / 1024) as min_size_kb,
    MAX(file_size / 1024) as max_size_kb
FROM user_messages
WHERE is_document = true;
```

## Производительность

- **Генерация PDF:** ~0.5-2 секунды (зависит от количества товаров)
- **Отправка в Telegram:** ~1-3 секунды (зависит от размера файла)
- **Общее время:** ~2-5 секунд на заказ

## Поддержка

При возникновении проблем:
1. Проверить логи: `/Users/ss/GenAI/korzinka/logs/order-service.log`
2. Проверить таблицу `user_messages` для отслеживания ошибок отправки
3. Проверить наличие данных в БД (lsd_stocks, basket_analyses)

## Changelog

### 2025-10-06
- ✅ Создан модуль генерации PDF-отчетов
- ✅ Добавлена отправка документов в Telegram
- ✅ Интегрирована в основной флоу (process_optimized_orders)
- ✅ Добавлены SQL-запросы для получения данных
- ✅ Обновлена модель UserMessage для поддержки документов
- ✅ Добавлена миграция БД
- ✅ Обновлены requirements.txt
