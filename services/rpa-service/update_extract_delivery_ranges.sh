#!/bin/bash

# Резервная копия
cp /Users/ss/GenAI/korzinka/services/rpa-service/selenium_product_search.py /Users/ss/GenAI/korzinka/services/rpa-service/selenium_product_search.py.backup_$(date +%Y%m%d_%H%M%S)

# Извлекаем функцию из обновлённого файла (пропускаем первую строку с комментарием)
UPDATED_FUNCTION=$(tail -n +2 /Users/ss/GenAI/korzinka/services/rpa-service/selenium_product_search_updated.py)

# Создаём временный файл с новым содержимым
{
    # Всё до функции extract_delivery_ranges (строки 1-826)
    head -n 826 /Users/ss/GenAI/korzinka/services/rpa-service/selenium_product_search.py
    
    # Вставляем обновлённую функцию
    echo "$UPDATED_FUNCTION"
    echo ""
    
    # Всё после функции extract_delivery_ranges (строки 1103-)
    tail -n +1103 /Users/ss/GenAI/korzinka/services/rpa-service/selenium_product_search.py
    
} > /Users/ss/GenAI/korzinka/services/rpa-service/selenium_product_search.py.new

# Заменяем файл
mv /Users/ss/GenAI/korzinka/services/rpa-service/selenium_product_search.py.new /Users/ss/GenAI/korzinka/services/rpa-service/selenium_product_search.py

echo "✅ Function extract_delivery_ranges successfully updated!"
echo "📁 Backup saved as: selenium_product_search.py.backup_$(date +%Y%m%d_%H%M%S)"
