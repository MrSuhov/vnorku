#!/bin/bash
# Wrapper script для rematch_stocks.py с активацией venv

# Получаем абсолютный путь к директории скрипта
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Корень проекта - 2 уровня вверх от services/rpa-service
PROJECT_ROOT="$SCRIPT_DIR/../.."

# Переходим в корень проекта
cd "$PROJECT_ROOT" || {
    echo "❌ Ошибка: не удалось перейти в $PROJECT_ROOT"
    exit 1
}

# Показываем текущую директорию для отладки
echo "📁 Project root: $(pwd)"

# Проверяем наличие venv
if [ ! -d "venv" ]; then
    echo "❌ Ошибка: venv не найден в $(pwd)"
    echo "Создайте виртуальное окружение: python3 -m venv venv"
    exit 1
fi

# Активируем виртуальное окружение
source venv/bin/activate || {
    echo "❌ Ошибка активации venv"
    exit 1
}

# Проверяем наличие rematch_stocks.py
REMATCH_SCRIPT="services/rpa-service/rematch_stocks.py"
if [ ! -f "$REMATCH_SCRIPT" ]; then
    echo "❌ Ошибка: $REMATCH_SCRIPT не найден в $(pwd)"
    exit 1
fi

# Запускаем утилиту с переданными аргументами
python3 "$REMATCH_SCRIPT" "$@"
