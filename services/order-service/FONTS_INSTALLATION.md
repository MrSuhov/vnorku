# Установка шрифтов DejaVu для PDF-отчетов

## Зачем нужны шрифты DejaVu?

Шрифты DejaVu необходимы для корректного отображения **кириллицы** (русских букв) в PDF-отчетах. Без них PDF будет использовать Helvetica, который может отображать русские буквы некорректно.

## Автоматический поиск шрифтов

PDF-генератор автоматически ищет шрифты DejaVu в следующих местах:

**Linux:**
- `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`
- `/usr/share/fonts/dejavu/DejaVuSans.ttf`

**macOS:**
- `/opt/homebrew/share/fonts/truetype/dejavu/DejaVuSans.ttf` (Homebrew ARM)
- `/usr/local/share/fonts/truetype/dejavu/DejaVuSans.ttf` (Homebrew Intel)
- `/Library/Fonts/DejaVuSans.ttf` (системные)
- `/System/Library/Fonts/DejaVuSans.ttf` (системные)

**Внутри проекта:**
- `./fonts/DejaVuSans.ttf`

## Способы установки

### Способ 1: Через Homebrew (macOS) - РЕКОМЕНДУЕТСЯ

```bash
brew tap homebrew/cask-fonts
brew install font-dejavu
```

**Шрифты будут установлены в:** 
- ARM Mac: `/opt/homebrew/share/fonts/truetype/dejavu/`
- Intel Mac: `/usr/local/share/fonts/truetype/dejavu/`

### Способ 2: Скачать и установить вручную

1. Скачать шрифты: https://dejavu-fonts.github.io/Download.html
2. Распаковать архив
3. Скопировать файлы `.ttf` в одну из папок:

**macOS:**
```bash
# Для всей системы (требуются права администратора)
sudo cp DejaVuSans*.ttf /Library/Fonts/

# Или только для текущего пользователя
cp DejaVuSans*.ttf ~/Library/Fonts/
```

**Linux:**
```bash
# Для всей системы
sudo cp DejaVuSans*.ttf /usr/share/fonts/truetype/dejavu/

# Или только для текущего пользователя
mkdir -p ~/.fonts
cp DejaVuSans*.ttf ~/.fonts/
fc-cache -f -v
```

### Способ 3: Положить в проект (не рекомендуется)

```bash
# Создать папку для шрифтов
mkdir -p /Users/ss/GenAI/korzinka/services/order-service/fonts

# Скопировать шрифты
cp DejaVuSans.ttf /Users/ss/GenAI/korzinka/services/order-service/fonts/
cp DejaVuSans-Bold.ttf /Users/ss/GenAI/korzinka/services/order-service/fonts/
```

## Проверка установки

После установки запустите тест:

```bash
cd /Users/ss/GenAI/korzinka
source venv/bin/activate
python services/order-service/test_pdf_generation.py 31
```

**Ожидаемый вывод:**
```
✅ DejaVuSans fonts registered from: /opt/homebrew/share/fonts/truetype/dejavu/DejaVuSans.ttf
```

**Если шрифты не найдены:**
```
⚠️ DejaVuSans not found. Using Helvetica (limited Cyrillic support)
   To install DejaVu fonts:
   - macOS: brew install font-dejavu
   - Linux: sudo apt-get install fonts-dejavu-core
   - Or download from: https://dejavu-fonts.github.io/
```

## Что делать, если шрифты не устанавливаются?

PDF-генератор будет работать и без шрифтов DejaVu, используя Helvetica. Кириллица может отображаться некорректно, но структура PDF будет корректной.

**Для продакшена настоятельно рекомендуется установить DejaVu!**

## Устранение неполадок

### Шрифты установлены, но не находятся

**Проверьте пути:**
```bash
# macOS Homebrew
ls -la /opt/homebrew/share/fonts/truetype/dejavu/
ls -la /usr/local/share/fonts/truetype/dejavu/

# macOS системные
ls -la /Library/Fonts/DejaVu*
ls -la ~/Library/Fonts/DejaVu*
```

### После установки через Homebrew путь не найден

Homebrew может устанавливать шрифты в разные места в зависимости от архитектуры:
- **ARM (M1/M2)**: `/opt/homebrew/...`
- **Intel**: `/usr/local/...`

Проверьте оба пути или используйте Способ 2 (ручная установка).

## Проверка в PDF

После генерации PDF откройте файл и проверьте:
1. Русские буквы отображаются корректно
2. Нет "квадратиков" или "�" символов
3. Текст читается нормально

Если есть проблемы - убедитесь что шрифты установлены и найдены генератором.
