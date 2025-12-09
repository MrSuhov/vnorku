# Примеры конфигурации delivery_ranges

## Базовый пример с одним кликом

```json
{
  "delivery_ranges": {
    "enabled": true,
    "trigger": {
      "action": "click",
      "selector": "button.delivery-info",
      "wait_after": 1000
    },
    "ordered_extraction": {
      "fee_selectors": [
        "span.delivery-fee-1",
        "span.delivery-fee-2",
        null
      ],
      "threshold_selectors": [
        "span.threshold-1",
        "span.threshold-2",
        "span.threshold-3"
      ]
    },
    "close_trigger": {
      "selector": "button.close-modal"
    }
  }
}
```

## Пример с несколькими последовательными кликами

```json
{
  "delivery_ranges": {
    "enabled": true,
    "trigger": {
      "actions": [
        {
          "action": "click",
          "selector": "button.open-menu",
          "wait_after": 500
        },
        {
          "action": "click",
          "selector": "div.delivery-submenu",
          "wait_after": 300
        },
        {
          "action": "click",
          "selector": "a.show-delivery-info",
          "wait_after": 1000
        }
      ]
    },
    "ordered_extraction": {
      "fee_selectors": ["..."],
      "threshold_selectors": ["..."]
    }
  }
}
```

## Пример с вводом индекса перед открытием модалки

```json
{
  "delivery_ranges": {
    "enabled": true,
    "trigger": {
      "actions": [
        {
          "action": "type",
          "selector": "input[name='zipcode']",
          "text": "{zipcode}",
          "wait_after": 500
        },
        {
          "action": "click",
          "selector": "button.search-delivery",
          "wait_after": 1000
        },
        {
          "action": "click",
          "selector": "div.delivery-details-link",
          "wait_after": 500
        }
      ]
    },
    "ordered_extraction": {
      "fee_selectors": ["..."],
      "threshold_selectors": ["..."]
    }
  }
}
```

## Доступные action типы в trigger.actions

### 1. click
Клик по элементу
```json
{
  "action": "click",
  "selector": "button.open-modal",
  "wait_after": 500
}
```

### 2. hover
Наведение курсора на элемент
```json
{
  "action": "hover",
  "selector": "div.menu-item",
  "wait_after": 300
}
```

### 3. type
Ввод текста с поддержкой плейсхолдеров
```json
{
  "action": "type",
  "selector": "input[name='address']",
  "text": "{address}",
  "wait_after": 500
}
```

**Поддерживаемые плейсхолдеры:**
- `{phone}` - полный номер телефона (+79161234567)
- `{phone_without_7}` - номер без +7 (9161234567)
- `{address}` - полный адрес (117335, Профсоюзная 32)
- `{zipcode}` - почтовый индекс (117335)
- `{address_wo_zipcode}` - адрес без индекса (Профсоюзная 32)

### 4. wait
Просто пауза
```json
{
  "action": "wait",
  "wait_after": 2000
}
```

## Обратная совместимость

### Старый формат (один селектор)
```json
{
  "trigger": {
    "action": "click",
    "selector": "button.delivery",
    "wait_after": 500
  }
}
```

### Старый формат (fallback селекторы)
```json
{
  "trigger": {
    "action": "click",
    "selectors": [
      "button.delivery-v2",
      "button.delivery-v1",
      "a.delivery-link"
    ],
    "wait_after": 500
  }
}
```

**Логика fallback:** Пробует каждый селектор по очереди, останавливается на первом найденном.

### Новый формат (последовательные actions)
```json
{
  "trigger": {
    "actions": [
      {"action": "click", "selector": "..."},
      {"action": "click", "selector": "..."}
    ]
  }
}
```

**Логика последовательности:** Выполняет ВСЕ действия по порядку. Если хотя бы одно не удалось - прерывает последовательность.

## Реальный пример (Самокат с индексом)

```json
{
  "delivery_ranges": {
    "enabled": true,
    "trigger": {
      "actions": [
        {
          "action": "type",
          "selector": "input#postal-code",
          "text": "{zipcode}",
          "wait_after": 500
        },
        {
          "action": "click",
          "selector": "button[type='submit']",
          "wait_after": 1500
        },
        {
          "action": "hover",
          "selector": "div.delivery-info-tooltip",
          "wait_after": 300
        },
        {
          "action": "click",
          "selector": "a.show-full-details",
          "wait_after": 800
        }
      ]
    },
    "ordered_extraction": {
      "fee_selectors": [
        "//div[@class='range-1']//span[@class='fee']",
        "//div[@class='range-2']//span[@class='fee']",
        null
      ],
      "threshold_selectors": [
        "//div[@class='range-1']//span[@class='threshold']",
        "//div[@class='range-2']//span[@class='threshold']",
        "//div[@class='range-3']//span[@class='threshold']"
      ]
    },
    "close_trigger": {
      "selector": "button.modal-close",
      "optional": true
    }
  }
}
```

## Отладка

При ошибке выполнения actions:
1. Проверяется каждый action по порядку
2. При первом неудачном action - последовательность прерывается
3. HTML страницы сохраняется в `/Users/ss/GenAI/korzinka/logs/page_dump_[timestamp].html`
4. В логах указывается какой именно action не сработал

Ищите в логах:
```
🎯 Sequential trigger mode: 3 action(s) to execute
🔘 [1/3] Executing action: type
✅ [1/3] Action completed successfully
🔘 [2/3] Executing action: click
❌ Action [2] failed, stopping trigger sequence
⚠️ Page HTML saved to: /Users/ss/GenAI/korzinka/logs/page_dump_20250127_143022.html
```
