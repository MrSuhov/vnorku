#!/bin/bash
# Скрипт установки PDF-модуля для Korzinka Order Service

set -e

echo "🚀 Установка PDF-модуля..."

# 1. Установка зависимостей
echo "📦 Установка reportlab..."
pip install reportlab==4.0.7

# 2. Проверка наличия шрифтов DejaVu
echo "🔤 Проверка шрифтов DejaVu..."
if [ "$(uname)" == "Darwin" ]; then
    # macOS
    if ! fc-list | grep -q "DejaVu"; then
        echo "⚠️  Шрифты DejaVu не найдены. Установка через Homebrew..."
        brew install font-dejavu || echo "❌ Не удалось установить шрифты. Продолжаем без них."
    else
        echo "✅ Шрифты DejaVu найдены"
    fi
elif [ "$(expr substr $(uname -s) 1 5)" == "Linux" ]; then
    # Linux
    if ! fc-list | grep -q "DejaVu"; then
        echo "⚠️  Шрифты DejaVu не найдены. Установка..."
        sudo apt-get install -y fonts-dejavu-core || echo "❌ Не удалось установить шрифты. Продолжаем без них."
    else
        echo "✅ Шрифты DejaVu найдены"
    fi
fi

# 3. Применение миграции БД
echo "🗄️  Применение миграции БД..."
psql postgresql://korzinka_user:korzinka_pass@localhost:5432/korzinka \
  -f /Users/ss/GenAI/korzinka/sql/add_document_fields_to_user_messages.sql

echo ""
echo "✅ Установка завершена!"
echo ""
echo "📚 Документация: /Users/ss/GenAI/korzinka/services/order-service/PDF_README.md"
echo ""
echo "🧪 Для тестирования запустите:"
echo "   python test_pdf_generation.py"
