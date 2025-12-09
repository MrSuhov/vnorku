# Удаление полей delivery_fee и free_delivery_threshold

**Дата:** 27 сентября 2025  
**Миграция:** `e8f9a1b2c3d4`

## Выполненные изменения

### 1. База данных
- Удалены поля `delivery_fee` и `free_delivery_threshold` из таблицы `lsd_configs`
- Пересоздано представление `fprice_lsd_order` без этих полей

### 2. Модели Python
- Удалены поля из SQLAlchemy модели `LSDConfig` в `/Users/ss/GenAI/korzinka/shared/database/models.py`
- Удалены поля из Pydantic модели `LSDConfigModel` в `/Users/ss/GenAI/korzinka/shared/models/base.py`

## Обоснование
Эти поля были помечены как устаревшие (`устарело`) и больше не используются в коде. Вместо них используется поле `delivery_cost_model`, которое хранит JSON с более гибкой моделью стоимости доставки с диапазонами.

## Откат изменений
В случае необходимости отката можно использовать:
```bash
cd /Users/ss/GenAI/korzinka
source venv/bin/activate
alembic downgrade -1
```

Это вернет поля в таблицу и восстановит представление с этими полями.
