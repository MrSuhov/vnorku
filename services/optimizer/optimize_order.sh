#!/bin/bash

# Скрипт оптимизации корзины заказа (быстрая версия)
# Использование: ./optimize_order.sh <order_id> [top_n]

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Определяем корневую директорию проекта
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"

# Параметры БД из .env или дефолтные
if [ -f "$PROJECT_ROOT/.env" ]; then
    # Читаем только DATABASE_URL из .env
    DB_URL=$(grep -E '^DATABASE_URL=' "$PROJECT_ROOT/.env" | cut -d '=' -f 2-)
fi
DB_URL="${DB_URL:-postgresql://korzinka_user:korzinka_pass@localhost:5432/korzinka}"

# Проверка аргументов
if [ -z "$1" ]; then
    echo -e "${RED}Ошибка: не указан номер заказа${NC}"
    echo "Использование: $0 <order_id> [top_n]"
    echo "Пример: $0 1 3"
    exit 1
fi

ORDER_ID=$1
TOP_N=${2:-3}

echo -e "${BLUE}=== ОПТИМИЗАЦИЯ ЗАКАЗА #${ORDER_ID} ===${NC}"
echo ""

# Шаг 1
echo -e "${YELLOW}[1/3] Генерация комбинаций...${NC}"
psql "$DB_URL" -q -c "CALL generate_order_combinations(${ORDER_ID});"
echo -e "${GREEN}✓ OK${NC}"

# Шаг 2
echo -e "${YELLOW}[2/3] Генерация валидных корзин...${NC}"
psql "$DB_URL" -q -c "CALL generate_valid_baskets(${ORDER_ID});"
echo -e "${GREEN}✓ OK${NC}"

# Шаг 3
echo -e "${YELLOW}[3/3] Расчет доставки...${NC}"
psql "$DB_URL" -q -c "CALL calculate_optimized_baskets(${ORDER_ID}, ${TOP_N});"
echo -e "${GREEN}✓ OK${NC}"

# Результаты
echo ""
echo -e "${BLUE}=== РЕЗУЛЬТАТЫ ===${NC}"

psql "$DB_URL" -t -A -F'|' << EOF | column -t -s'|'
SELECT 
    ROW_NUMBER() OVER (ORDER BY total_savings, total_cost)::text as "#",
    total_cost || ' руб' as "Итого",
    total_savings || ' руб' as "Экономия",
    (SELECT SUM((v.value->>'fee')::numeric + (v.value->>'topup')::numeric) 
     FROM jsonb_each(delivery_costs::jsonb) v) || ' руб' as "Доставка"
FROM basket_analyses
WHERE order_id = ${ORDER_ID}
ORDER BY total_savings, total_cost
LIMIT ${TOP_N};
EOF

echo ""
echo -e "${GREEN}✓ Результаты сохранены в basket_analyses${NC}"
echo ""
echo -e "${BLUE}Просмотр деталей:${NC}"
echo "  psql \$DATABASE_URL -c \"SELECT * FROM basket_analyses WHERE order_id = ${ORDER_ID};\""
echo "  или: ./services/optimizer/show_results.sh ${ORDER_ID}"
