#!/bin/bash
# Скрипт для очистки зависших транзакций в PostgreSQL

set -e

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║      DATABASE CLEANUP - Kill Stuck Transactions       ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
echo

cd /Users/ss/GenAI/korzinka

echo -e "${YELLOW}🔍 Searching for stuck transactions...${NC}"
echo

# Запускаем Python скрипт очистки
./venv/bin/python3 -c "
import asyncio
import sys
sys.path.insert(0, '/Users/ss/GenAI/korzinka')

from shared.utils.db_cleanup import cleanup_before_start

result = asyncio.run(cleanup_before_start())

if result > 0:
    print(f'\n✅ Successfully killed {result} stuck transaction(s)')
    sys.exit(0)
else:
    print('\n✅ No stuck transactions found - database is clean')
    sys.exit(0)
" 2>&1 | grep -v "sqlalchemy.engine" | grep -v "BEGIN\|ROLLBACK\|SELECT"

echo
echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                 CLEANUP COMPLETED                      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
