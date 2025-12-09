#!/bin/bash

# Скрипт оптимизации заказа через Python оптимизатор
# Использование: ./optimize_order_py.sh <order_id> [--engine numpy|legacy|auto] [--top-n N]

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Определяем директории
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Проверка наличия venv
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo -e "${RED}❌ Виртуальное окружение не найдено${NC}"
    echo "Создайте venv: python3 -m venv $PROJECT_ROOT/venv"
    exit 1
fi

# Активируем Python из venv
PYTHON="$PROJECT_ROOT/venv/bin/python3"

# Проверка наличия order_id
if [ -z "$1" ]; then
    echo -e "${RED}❌ Ошибка: не указан номер заказа${NC}"
    echo ""
    echo "Использование: $0 <order_id> [options]"
    echo ""
    echo "Опции:"
    echo "  --engine <numpy|legacy|auto>  Движок оптимизации (по умолчанию: auto)"
    echo "  --top-n <N>                   Количество лучших корзин (по умолчанию: 10)"
    echo "  --top-k-prefilter <K>         Предфильтрация для NumPy (по умолчанию: 100000)"
    echo ""
    echo "Примеры:"
    echo "  $0 25                          # Auto-выбор движка, топ-10 корзин"
    echo "  $0 25 --engine numpy           # Принудительно NumPy"
    echo "  $0 25 --engine numpy --top-n 5 # NumPy, топ-5 корзин"
    exit 1
fi

# Запускаем Python оптимизатор
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  PYTHON ОПТИМИЗАТОР ЗАКАЗОВ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}"
echo ""

"$PYTHON" "$SCRIPT_DIR/optimize.py" "$@"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ Оптимизация завершена успешно${NC}"
    echo ""
    echo -e "${BLUE}Просмотр результатов:${NC}"
    echo "  psql \$DATABASE_URL -c \"SELECT * FROM basket_analyses WHERE order_id = $1 ORDER BY basket_rank;\""
    echo ""
    echo -e "${BLUE}Логи:${NC}"
    echo "  tail -f $PROJECT_ROOT/logs/optimizer_numpy.log"
else
    echo ""
    echo -e "${RED}❌ Оптимизация завершилась с ошибкой (код: $EXIT_CODE)${NC}"
    echo ""
    echo -e "${YELLOW}Проверьте логи:${NC}"
    echo "  tail -100 $PROJECT_ROOT/logs/optimizer_numpy.log"
fi

exit $EXIT_CODE
