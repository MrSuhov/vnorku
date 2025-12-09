# Magnit API Module - Документация

## Обзор

Модуль `magnit.py` предоставляет функциональность для работы с API Magnit через их мобильное приложение:
- Обновление токенов авторизации (refresh tokens)
- Поиск товаров по запросу
- Управление сессиями пользователей

## Расположение

```
/Users/ss/GenAI/korzinka/services/rpa-service/magnit.py
```

## Зависимости

Добавлена в `requirements.txt`:
- `PyJWT==2.8.0` - для декодирования JWT токенов

## Структура модуля

### Константы
- **API Endpoints**: 
  - `MAGNIT_AUTH_URL` - обновление токенов
  - `MAGNIT_SEARCH_URL` - поиск товаров
- **Версии приложения**: 8.72.0 (build 121972)
- **Платформа**: iOS 26.0.1

### Основные функции

#### 1. `initialize_magnit_session(session_id, refresh_token, device_id=None)`
Инициализация сессии Magnit для пользователя.

**Параметры:**
- `session_id` (int): ID сессии в таблице `user_sessions`
- `refresh_token` (str): Refresh token из мобильного приложения
- `device_id` (str, опционально): UUID устройства (генерируется автоматически)

**Возвращает:** `bool` - успешность инициализации

**Пример:**
```python
success = initialize_magnit_session(
    session_id=1,
    refresh_token="bdab3844-fed9-4ad6-bb20-5024cd4d38f0"
)
```

#### 2. `search_products(query, session_id, stores=None, catalog_type="2", include_adult=True)`
Поиск товаров в Magnit.

**Параметры:**
- `query` (str): Поисковый запрос (например, "Шармэль")
- `session_id` (int): ID сессии пользователя
- `stores` (list, опционально): Список магазинов (по умолчанию: express, cosmetic, dostavka)
- `catalog_type` (str): Тип каталога (по умолчанию: "2")
- `include_adult` (bool): Включать взрослые товары

**Возвращает:** `List[Dict]` - список товаров

**Структура результата:**
```python
{
    "name": "Название товара",
    "price": 123.45,
    "unit": "шт",
    "availability": True,
    "store_code": "778168",
    "store_type": "express",
    "raw_data": {...}  # Полный ответ API
}
```

**Пример:**
```python
products = search_products("Шармэль", session_id=1)
for product in products:
    print(f"{product['name']}: {product['price']} руб.")
```

#### 3. `refresh_token_if_needed(session_id)`
Проверка и обновление токена при необходимости.

**Параметры:**
- `session_id` (int): ID сессии

**Возвращает:** `str` - актуальный access token или None

### Внутренние функции

- `refresh_access_token()` - обновление access token через refresh token
- `get_valid_token()` - получение актуального токена (с авто-обновлением)
- `build_base_headers()` - формирование HTTP заголовков
- `calculate_request_sign()` - **STUB** - генерация подписи X-Request-Sign
- `parse_search_results()` - парсинг результатов поиска

### Работа с базой данных

Модуль сохраняет данные в поле `data` (JSON) таблицы `user_sessions`:

```json
{
  "magnit_device_id": "7a7d5943-c54b-4447-bfa7-5b38ae6a2bab",
  "magnit_access_token": "eyJhbGci...",
  "magnit_refresh_token": "bdab3844-fed9-4ad6-bb20-5024cd4d38f0",
  "magnit_token_expires_at": "2025-10-06T12:00:00Z"
}
```

## Критические ограничения

### ⚠️ X-Request-Sign - НЕ РЕАЛИЗОВАНО

**Проблема:** Magnit API требует подпись запросов в заголовке `X-Request-Sign` (128 hex символов).

**Текущее состояние:** 
- Модуль использует **STUB** (заглушку)
- Функция `calculate_request_sign()` возвращает пустую строку
- API может отклонять запросы без подписи

**Возможные решения:**
1. **Тестирование без подписи** - проверить, работает ли API без X-Request-Sign
2. **Mock подпись** - использовать подпись из логов для proof-of-concept
3. **Reverse engineering** - декомпилировать приложение и извлечь алгоритм

**Алгоритм (предположительно):**
- HMAC-SHA512 (64 байта = 128 hex символов)
- Входные данные: URL + method + body + timestamp (?)
- Требуется секретный ключ из приложения

## Тестирование

### Файл: `test_magnit.py`

Тестовый скрипт проверяет:
1. Инициализацию сессии с refresh token
2. Обновление токена
3. Поиск товаров

**Запуск:**
```bash
cd /Users/ss/GenAI/korzinka/services/rpa-service
source ../../venv/bin/activate
python3 test_magnit.py
```

**Тестовые данные:**
- Session ID: 999
- Refresh Token: `bdab3844-fed9-4ad6-bb20-5024cd4d38f0` (из логов)

### Ожидаемые результаты

**Тест 1 - Initialize Session:**
- ✓ Должен создать access token
- ✓ Должен сохранить device_id в БД
- ✓ Должен сохранить expires_at

**Тест 2 - Refresh Token:**
- ✓ Должен вернуть актуальный access token
- ⚠️ Может повторно запросить refresh если токен истек

**Тест 3 - Search Products:**
- ⚠️ **Может не работать** без X-Request-Sign
- ✓ Если работает - должен вернуть список товаров
- ✓ Если не работает - покажет ошибку API и структуру ответа

## Логирование

Модуль использует стандартный logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Уровни логов:**
- `INFO` - основные операции (refresh, search)
- `DEBUG` - детали запросов и ответов
- `WARNING` - отсутствие X-Request-Sign
- `ERROR` - ошибки API и исключения

## Примеры использования

### Инициализация новой сессии
```python
from magnit import initialize_magnit_session

# После получения refresh_token через мобильное приложение
session_id = 123
refresh_token = "uuid-from-mobile-app"

if initialize_magnit_session(session_id, refresh_token):
    print("Сессия создана!")
```

### Поиск товаров
```python
from magnit import search_products

products = search_products("молоко", session_id=123)

for product in products:
    print(f"{product['name']}: {product['price']} руб.")
```

### Ручное обновление токена
```python
from magnit import refresh_token_if_needed

token = refresh_token_if_needed(session_id=123)
if token:
    print(f"Токен актуален: {token[:20]}...")
```

## Интеграция с RPA

Модуль можно использовать как альтернативу Selenium для Magnit:

```python
# Вместо RPA браузера
from magnit import search_products

def magnit_search_via_api(query, session_id):
    """API-версия поиска вместо RPA."""
    products = search_products(query, session_id)
    
    # Конвертировать в формат RPA
    return convert_to_rpa_format(products)
```

## TODO / Следующие шаги

1. **Reverse engineer X-Request-Sign:**
   - Декомпилировать iOS/Android приложение
   - Найти алгоритм генерации подписи
   - Извлечь секретный ключ
   - Реализовать в `calculate_request_sign()`

2. **Тестирование:**
   - Запустить test_magnit.py
   - Проверить, работает ли API без подписи
   - Если нет - начать reverse engineering

3. **Первичная авторизация:**
   - Реализовать получение первого refresh_token
   - Интеграция с SMS кодами (?)
   - Или использовать существующий RPA flow

4. **Парсинг результатов:**
   - Уточнить структуру ответа API
   - Доработать `parse_search_results()`
   - Добавить обработку всех полей товара

5. **Корзина и заказы:**
   - Добавление товаров в корзину
   - Оформление заказа
   - Применение промокодов

## Файлы проекта

```
/Users/ss/GenAI/korzinka/
├── services/rpa-service/
│   ├── magnit.py              # Основной модуль
│   ├── test_magnit.py         # Тесты
│   └── magnit/
│       └── flows_dump.mitm.candidates.json  # Логи трафика
├── requirements.txt           # Обновлен (добавлен PyJWT)
└── logs/                      # Логи работы модуля
```

## Контакты и поддержка

Модуль разработан на основе анализа трафика мобильного приложения Magnit версии 8.72.0 (build 121972).

**Дата создания:** 05.10.2025
**Статус:** MVP (требует тестирования и доработки X-Request-Sign)
