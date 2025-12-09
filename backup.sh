#!/bin/bash

# Создаем бекап проекта после успешного запуска Пятёрочки и ВкусВилл

echo "🗜️ Создание полного бекапа проекта Korzinka..."

# Переменные
PROJECT_ROOT="/Users/ss/GenAI/korzinka"
BACKUPS_DIR="$PROJECT_ROOT/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="korzinka_${TIMESTAMP}.zip"
BACKUP_PATH="$BACKUPS_DIR/$BACKUP_NAME"

# ============================================
# Шаг 1: Бекап базы данных
# ============================================
echo ""
echo "📊 Шаг 1/2: Создание бекапа базы данных..."
"$PROJECT_ROOT/backup_db.sh"

if [ $? -ne 0 ]; then
    echo "❌ Ошибка при создании бекапа БД"
    exit 1
fi

# ============================================
# Шаг 2: Бекап файлов проекта
# ============================================
echo ""
echo "📦 Шаг 2/2: Создание архива файлов проекта..."

# Создаем папку для бекапов если её нет
mkdir -p "$BACKUPS_DIR"

echo "📦 Создаем архив: $BACKUP_NAME"

# Переходим в корень проекта
cd "$PROJECT_ROOT" || exit 1

# Создаем zip архив используя tar как промежуточный формат (безопаснее для socket'ов)
echo "🔍 Создание архива..."
tar -czf "${BACKUP_PATH%.zip}.tar.gz" \
    --exclude="venv" \
    --exclude="backups" \
    --exclude=".git" \
    --exclude="browser_profiles" \
    --exclude="cookies" \
    --exclude="debug_html" \
    --exclude="node_modules" \
    --exclude=".idea" \
    --exclude="__pycache__" \
    --exclude="*.pyc" \
    --exclude="*.pyo" \
    --exclude="*.log" \
    --exclude=".DS_Store" \
    --exclude=".env" \
    --exclude="*.sock" \
    --exclude="*.socket" \
    --exclude="*.pid" \
    --exclude=".service_pids" \
    --exclude="nohup.out" \
    . 2>/dev/null

# Обновляем путь к бекапу (теперь это .tar.gz вместо .zip)
BACKUP_PATH="${BACKUP_PATH%.zip}.tar.gz"
BACKUP_NAME="${BACKUP_NAME%.zip}.tar.gz"

# Проверяем успешность создания архива
if [ $? -eq 0 ]; then
    echo "✅ Архив создан успешно"
else
    echo "❌ Ошибка при создании архива"
    exit 1
fi

# Получаем статистику
BACKUP_SIZE=$(stat -f%z "$BACKUP_PATH" 2>/dev/null || stat -c%s "$BACKUP_PATH" 2>/dev/null)
SIZE_MB=$((BACKUP_SIZE / 1024 / 1024))

# Считаем количество файлов в архиве
FILES_COUNT=$(unzip -l "$BACKUP_PATH" | tail -1 | awk '{print $2}')

echo "📊 Статистика бекапа:"
echo "  📁 Файлов в архиве: $FILES_COUNT"
echo "  💾 Размер: ${SIZE_MB} MB"
echo "  📍 Путь: $BACKUP_PATH"

# Создаем README для бекапа
README_PATH="$BACKUPS_DIR/README_${TIMESTAMP}.md"
CURRENT_DATE=$(date +"%Y-%m-%d %H:%M:%S")

cat > "$README_PATH" << EOF
# Бекап Korzinka - $TIMESTAMP

## 📁 Содержимое бекапа

### 📦 Архив проекта
- Весь проект кроме venv, логов, кэша
- Рабочие конфигурации RPA
- Все сервисы и скрипты
- **Архив:** $BACKUP_NAME
- **Размер:** ${SIZE_MB} MB
- **Файлов:** $FILES_COUNT

### 📊 Бекап базы данных
- PostgreSQL dump базы korzinka
- Расположение: backups/db/
- Последний бекап можно найти в backups/db/

**Дата создания:** $CURRENT_DATE

## 🔄 Восстановление

### База данных:
\`\`\`bash
gunzip -c backups/db/korzinka_backup_YYYYMMDD_HHMMSS.sql.gz | PGPASSWORD=korzinka_pass psql -h localhost -U korzinka_user -d korzinka
\`\`\`

### Файлы проекта:
\`\`\`bash
tar -xzf backups/$BACKUP_NAME -C /Users/ss/GenAI/korzinka_restored
\`\`\`
EOF

echo "📝 README создан: README_${TIMESTAMP}.md"
echo "🎉 Бекап завершен успешно!"
