# Логика поиска альтернативных товаров

## Текущее состояние
✅ Модели обновлены: `OrderItem` и `LSDStock` поддерживают альтернативы
✅ Парсер создан: `alternatives_parser.py` распознает слеш
✅ Order-service передает альтернативы в RPA-service

## Что нужно сделать в RPA-service

### 1. Обработка входящих products с альтернативами

В `search_products()` endpoint получаем:
```python
{
    "order_item_id": 123,
    "product_name": "форель",
    "is_alternative_group": True,
    "alternatives": ["семга", "лосось"]
}
```

### 2. Поиск всех вариантов

Если `is_alternative_group == True`:
- Искать основной товар: `product_name`
- Искать каждую альтернативу из `alternatives[]`
- Маркировать результаты флагом `is_alternative`

### 3. Сохранение в lsd_stocks

Для каждого найденного товара:
```python
LSDStock(
    order_item_id=123,  # ОДИН order_item_id для всех вариантов
    found_name="Семга охлажденная",
    is_alternative=True,  # Если это альтернатива
    alternative_for="форель",  # Для какого основного товара
    ...
)
```

### 4. Реализация в `perform_product_search_with_cdp_cookies()`

```python
for product in products:
    # Основной поиск
    await search_single_product_cdp(
        product_name=product['product_name'],
        order_item_id=product['order_item_id'],
        is_alternative=False,
        alternative_for=None
    )
    
    # Поиск альтернатив (если есть)
    if product.get('is_alternative_group'):
        for alt_name in product['alternatives']:
            await search_single_product_cdp(
                product_name=alt_name,
                order_item_id=product['order_item_id'],  # ТОТ ЖЕ order_item_id!
                is_alternative=True,
                alternative_for=product['product_name']
            )
```

### 5. Обновление сохранения результатов

В `save_search_results_to_db()` добавить поля:
```python
lsd_stock = LSDStock(
    ...
    is_alternative=result.is_alternative,
    alternative_for=result.alternative_for
)
```

## Пример результата

Для запроса "форель / семга 500г" будут найдены:
1. `found_name="Форель стейки"`, `is_alternative=False`
2. `found_name="Семга охлажденная"`, `is_alternative=True`, `alternative_for="форель"`
3. `found_name="Семга кусок"`, `is_alternative=True`, `alternative_for="форель"`

Все с одним `order_item_id`, позже оптимизатор выберет самый дешевый вариант.
