# CLAUDE.md

Этот файл содержит инструкции для Claude Code при работе с кодом в этом репозитории.

## О проекте

**vnorku** (домен: vnorku.ru) — сервис оптимизации продуктовых заказов. Автоматически находит лучшие цены и промокоды в локальных службах доставки (ЛСД) в России. Использует RPA (Robotic Process Automation) для поиска товаров, сравнения цен и оптимального распределения заказа между несколькими службами доставки.

## Инфраструктура

### Сервер бэкенда
- **Адрес**: `109.73.207.207`
- **Важно**: Это shared-сервер, на котором работают и другие сервисы помимо vnorku

### Разделение Dev/Prod сред

Среды разработки и продакшена разделены через разные Telegram-боты:

| Среда | Токен в .env | Инстанс |
|-------|--------------|---------|
| **DEV** | `TELEGRAM_BOT_TOKEN=8422...` | Локальная машина разработчика |
| **PROD** | `TELEGRAM_BOT_TOKEN=5601...` | Сервер 109.73.207.207 |

**Принцип изоляции:**
- DEV-бот обрабатывается **локальным** инстансом сервисов + **локальной** базой данных
- PROD-бот обрабатывается **серверным** инстансом сервисов + **серверной** базой данных
- Данные между средами не пересекаются — каждый бот работает со своей изолированной инфраструктурой

**Переключение среды:**
В `.env` файле закомментирован неактивный токен. Для переключения — закомментировать текущий и раскомментировать нужный.

### SSH ControlMaster

Для стабильного SSH соединения используется ControlMaster. Перед работой с сервером установи master-соединение:

```bash
# Установить master-соединение (держится 30 минут)
ssh -fN 109.73.207.207

# Проверить статус соединения
ssh -O check 109.73.207.207

# Закрыть master-соединение
ssh -O exit 109.73.207.207
```

Конфигурация в `~/.ssh/config`, сокеты в `~/.ssh/controlmasters/`

## Архитектура

**Микросервисная архитектура** из 5 независимых Python-сервисов, взаимодействующих по HTTP:

### Сервисы (порты)
- **telegram-bot** (8001): Telegram-бот для пользователей
- **user-service** (8002): Управление пользователями и аутентификация
- **order-service** (8003): Обработка заказов, координация поиска, оптимизация
- **rpa-service** (8004): Браузерная автоматизация для авторизации и поиска в ЛСД
- **promotion-service** (8005): Управление промокодами

### Коммуникация между сервисами
Сервисы общаются через прямые HTTP-запросы (например, order-service вызывает rpa-service по адресу `http://localhost:8004`). Очередей сообщений нет — координация через REST API и состояние в БД.

### Общие компоненты (`shared/`)
- **database/**: SQLAlchemy модели и async connection pooling
- **rpa/**: Универсальный RPA-движок на Playwright со stealth-техниками
- **models/**: Pydantic-модели для валидации данных
- **utils/**: Нормализация текста, логирование, шифрование, парсинг товаров

## База данных

PostgreSQL с основными таблицами:

**Пользователи:**
- `users` — профили с telegram_id, адресами, предпочтениями
- `user_sessions` — данные сессий и cookies для авторизации в ЛСД
- `lsd_accounts` — аккаунты пользователей в конкретных ЛСД

**Заказы:**
- `orders` — основная таблица заказов со статусами
- `order_items` — товары из списка покупок (поддерживает альтернативы через `/`)
- `lsd_stocks` — результаты поиска: товары найденные в каждом ЛСД с ценами
- `basket_analyses` — результаты оптимизации с разбивкой по ЛСД
- `order_baskets` — оптимизированные корзины по ЛСД
- `order_basket_items` — товары в каждой оптимизированной корзине

**Конфигурация:**
- `lsd_configs` — настройки ЛСД: base_url, RPA-конфиги, конфиги поиска
- `promotions` — доступные промокоды и их условия
- `product_prices` — история цен

**Планы питания:**
- `food_categories` — категории продуктов (молочные, мясо, овощи и т.д.)
- `food_products` — продукты питания с КБЖУ (калории, белки, жиры, углеводы)
- `meal_plans` — планы питания пользователей с целевыми значениями КБЖУ
- `meal_daily_logs` — дневные логи питания с фактическими значениями
- `meal_entries` — записи приёмов пищи (завтрак, обед, ужин, перекус)

## Команды разработки

### Настройка окружения
```bash
# Создать и активировать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Скопировать и настроить конфигурацию
cp .env.example .env
# Отредактировать .env
```

### Управление базой данных
```bash
# Запустить PostgreSQL и Redis через Docker
docker-compose up -d postgres redis

# Применить миграции
alembic upgrade head

# Создать новую миграцию
alembic revision --autogenerate -m "описание"

# Посмотреть историю миграций
alembic history
```

### Управление сервисами

**Рекомендуемый способ — полный стек:**
```bash
# Запустить все сервисы с автоочисткой зависших процессов
./start_services.sh

# Остановить все сервисы
./stop_services.sh

# Перезапустить один сервис
./start_services.sh rpa           # или telegram, user, order, promotion
./start_services.sh telegram-bot  # полные имена тоже работают
```

**Для разработки — отдельные сервисы:**
```bash
# Запустить каждый сервис в отдельном терминале
python services/telegram-bot/main.py
python services/user-service/main.py
python services/order-service/main.py
python services/rpa-service/main.py
python services/promotion-service/main.py
```

### Мониторинг и отладка
```bash
# Смотреть логи всех сервисов
tail -f logs/*.log

# Логи конкретного сервиса
tail -f logs/rpa-service.log

# Поиск ошибок
grep -i error logs/*.log
```

## Основные паттерны

### Поток обработки заказа

1. **Пользователь отправляет заказ** → telegram-bot создаёт заказ через order-service
2. **Статус: NEW** → Пользователь подтверждает → статус: CONFIRMED
3. **Анализ начинается** → order-service вызывает rpa-service для параллельного поиска
4. **Статус: ANALYZING** → поиски завершены → статус: ANALYSIS_COMPLETE
5. **Оптимизация** → order-optimizer создаёт ранжированные корзины
6. **Статус: OPTIMIZING** → оптимизация завершена → статус: OPTIMIZED
7. **Результаты отправлены** → Лучшая корзина + PDF-отчёт в Telegram → статус: RESULTS_SENT

### RPA-движок

Универсальный RPA Engine (`shared/rpa/universal_rpa_engine.py`) управляет браузерной автоматизацией:

**Сессионное выполнение:**
- Каждый RPA-поток работает в `RPASession` с браузерным контекстом
- Шаги определены в `lsd_configs.rpa_config` JSON с зависимостями и условиями
- Типы шагов: navigate, wait, click, type, extract_qr, verify_success, save_cookies

**Stealth-техники:**
- `AdvancedStealth`: Рандомизация отпечатков, WebGL noise, canvas spoofing
- `OzonStealth`: Антидетект для Ozon (undetected-chromedriver)
- `SafariLikeBrowser`: macOS Safari user-agent и заголовки

### Поиск товаров с альтернативами

Товары поддерживают альтернативы через `/`: `"форель / семга / лосось"`

**Логика парсинга** (`shared/utils/alternatives_parser.py`):
- Основной товар: первый элемент до `/`
- Альтернативы: элементы после `/`
- Пример: `"копченая форель / семга"` → основной: `"копченая форель"`, альт: `["копченая семга"]`

### Параллельный поиск

Order-service координирует параллельные поиски через asyncio semaphore pool:

```python
# Создать пул семафоров (например, 3 параллельных браузера)
semaphore = asyncio.Semaphore(settings.max_concurrent_browsers)

# Каждый ЛСД получает воркер, который захватывает слот
async def _lsd_worker(semaphore, lsd, order_items):
    async with semaphore:  # Ждать свободный слот
        stocks = await _search_products_in_lsd_isolated(lsd, order_items)
        return stocks

# Запустить все воркеры параллельно (семафор ограничивает реальный параллелизм)
tasks = [_lsd_worker(sem, lsd, items) for lsd in active_lsds]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

## Конфигурация

### Схема конфигурации ЛСД

Каждый ЛСД в таблице `lsd_configs` имеет:
- `rpa_config`: Шаги авторизации с селекторами и действиями
- `search_config_rpa`: Селекторы поиска товаров и парсинга результатов
- `delivery_cost_model`: JSON с моделью стоимости доставки
- `is_active`, `is_mvp`: Флаги функций

### Настройки сервисов (`config/settings.py`)

Ключевые настройки из окружения:
- `MAX_CONCURRENT_BROWSERS`: Размер пула браузеров (по умолчанию: 3)
- `TELEGRAM_BOT_TOKEN`: Токен бота
- Порты сервисов: `TELEGRAM_BOT_PORT`, `ORDER_SERVICE_PORT` и т.д.
- БД: `DATABASE_URL` для async PostgreSQL
- `DEBUG`: Включить подробное логирование

## Тестирование RPA

### Ручное тестирование через Telegram-бот
1. Запустить все сервисы: `./start_services.sh`
2. Отправить `/start` боту
3. Тест авторизации: `/auth yandex_lavka` (QR) или `/auth vkusvill` (SMS)
4. Мониторить логи: `tail -f logs/rpa-service.log`

### Индикаторы успеха в логах
```
✅ Executing step verify_success
✅ SUCCESS step verify_success completed!
✅ Force-executing critical step after success: save_cookies
✅ Browser FORCE-CLOSED
```

## Типичные задачи разработки

### Добавление нового ЛСД

1. **БД**: Вставить в `lsd_configs` с `rpa_config` и `search_config_rpa`
2. **RPA Config**: Определить шаги авторизации
3. **Search Config**: Определить селекторы поиска
4. **Тестирование**: Использовать `/auth {lsd_name}` в боте

### Изменение логики оптимизации

Оптимизация в `services/order-service/order_optimizer_handler.py`:
- Читает `lsd_stocks` для всех товаров × ЛСД
- Генерирует все возможные комбинации корзин
- Вычисляет итоговую стоимость с доставкой
- Ранжирует по цене и сохраняет top-N в `basket_analyses`

### Отладка зависших заказов

Order-service имеет встроенный мониторинг (`monitor_analyzing_orders()` каждые 10с):
- Обнаруживает заказы в ANALYZING > 30 минут
- Автоматический retry с очисткой старых `lsd_stocks`
- Принудительный retry: `POST /orders/force-retry/{order_id}`

### План питания (Meal Plan)

Функционал трекинга питания с расчётом КБЖУ:

**Команда**: `/meal` — главное меню планов питания

**Возможности:**
- Калькулятор КБЖУ (Миффлин-Сан Жеор + TDEE)
- Готовые шаблоны планов (1500-3000 ккал)
- Ручной ввод целевых значений
- Логирование приёмов пищи по категориям продуктов
- История и статистика за неделю
- Прогресс-бар выполнения дневной нормы

**Структура кода:**
- `handlers/meal_plan.py` — основной обработчик
- `data/products_ru.json` — база продуктов (119 продуктов, 12 категорий)
- `scripts/load_food_products.py` — скрипт загрузки продуктов в БД

**Расчёт калорий:**
```python
# BMR (базовый метаболизм) по формуле Миффлина-Сан Жеора
# Мужчины: BMR = 10 * вес + 6.25 * рост - 5 * возраст + 5
# Женщины: BMR = 10 * вес + 6.25 * рост - 5 * возраст - 161

# TDEE = BMR × коэффициент активности
# sedentary: 1.2, light: 1.375, moderate: 1.55, active: 1.725, very_active: 1.9

# Корректировка по цели:
# Похудение: TDEE - 500 ккал
# Поддержание: TDEE
# Набор массы: TDEE + 300 ккал
```

**Загрузка продуктов:**
```bash
# После применения миграции загрузить продукты в БД
python scripts/load_food_products.py
```

## Структура файлов

```
vnorku/
├── services/
│   ├── telegram-bot/       # Обработчики бота
│   │   ├── main.py         # Основной файл бота
│   │   └── handlers/
│   │       ├── registration_mock.py   # Регистрация пользователей
│   │       ├── orders.py              # Обработка заказов
│   │       └── meal_plan.py           # Планы питания и КБЖУ
│   ├── order-service/      # CRUD заказов, координация, оптимизация
│   │   ├── main.py         # API endpoints, логика параллельного поиска
│   │   ├── order_optimizer_handler.py  # Алгоритм оптимизации корзин
│   │   └── basket_formatter.py         # Форматирование для Telegram
│   ├── rpa-service/        # Браузерная автоматизация
│   │   └── main.py         # RPA endpoints
│   └── user-service/       # Управление пользователями
├── shared/
│   ├── database/
│   │   └── models.py       # SQLAlchemy модели
│   ├── rpa/
│   │   ├── universal_rpa_engine.py      # Ядро RPA
│   │   ├── lsd_authenticator.py         # Универсальная авторизация
│   │   └── vkusvill_authenticator.py    # ЛСД-специфичная логика
│   └── utils/
│       ├── alternatives_parser.py       # Парсинг альтернатив
│       ├── text_normalizer.py           # Нормализация названий
│       └── unified_logging.py           # Настройка логирования
├── data/
│   └── products_ru.json    # База продуктов с КБЖУ
├── scripts/
│   └── load_food_products.py  # Загрузка продуктов в БД
├── migrations/             # Миграции Alembic
├── logs/                   # Логи сервисов (gitignored)
├── cookies/                # Cookies сессий (gitignored)
├── start_services.sh       # Запуск с очисткой
└── stop_services.sh        # Остановка сервисов
```

## Важные замечания

- **Сессии БД**: Каждый параллельный RPA-поиск использует изолированную async-сессию
- **Статусы заказа**: Переходы односторонние: NEW → CONFIRMED → ANALYZING → ANALYSIS_COMPLETE → OPTIMIZING → OPTIMIZED → RESULTS_SENT
- **Восстановление после ошибок**: Заказы в ANALYZING авто-retry до 3 раз, потом FAILED
- **Хранение cookies**: Предпочтительно файловое хранение (`cookie_file`) вместо inline JSON
- **Telegram интеграция**: Все исходящие сообщения логируются в `user_messages`
- **Контроль параллелизма**: Размер пула браузеров критичен для баланса производительности и ресурсов
