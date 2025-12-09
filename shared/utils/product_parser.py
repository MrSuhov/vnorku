import re
from typing import List, Optional, Tuple
from shared.models.base import Product
from shared.utils.logging import get_logger

logger = get_logger(__name__)


class ProductParser:
    """Парсинг и нормализация списков продуктов из текста"""
    
    # Единицы измерения и их синонимы
    UNITS_MAP = {
        # Весовые
        'кг': ['кг', 'килограмм', 'килограмма', 'килограммов', 'kg'],
        'г': ['г', 'грамм', 'грамма', 'граммов', 'гр'],
        
        # Объемные
        'л': ['л', 'литр', 'литра', 'литров', 'лит'],
        'мл': ['мл', 'миллилитр', 'миллилитра', 'миллилитров'],
        
        # Штучные
        'шт': ['шт', 'штук', 'штуки', 'штука', 'шт.', 'pc', 'пс'],
        'упак': ['упак', 'упаковка', 'упаковки', 'упаковок', 'пак', 'pack'],
        'бут': ['бут', 'бутылка', 'бутылки', 'бутылок'],
        'пач': ['пач', 'пачка', 'пачки', 'пачек']
    }
    
    def __init__(self):
        # Создаем обратный словарь для поиска стандартной единицы
        self.unit_lookup = {}
        for standard, variants in self.UNITS_MAP.items():
            for variant in variants:
                self.unit_lookup[variant.lower()] = standard
    
    def normalize_product_list(self, text: str) -> List[Product]:
        """Основной метод нормализации списка продуктов"""
        products = []
        
        # Разбиваем текст на строки
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        for line in lines:
            product = self._parse_line(line)
            if product:
                products.append(product)
            else:
                logger.warning(f"Не удалось распарсить строку: {line}")
        
        return products
    
    def _parse_line(self, line: str) -> Optional[Product]:
        """Парсинг одной строки с продуктом"""
        original_line = line
        line = line.lower().strip()
        
        # Убираем маркеры списка
        line = re.sub(r'^[-*•]\s*', '', line)
        line = re.sub(r'^\d+[\.)]\s*', '', line)
        
        # Паттерны для поиска количества и единиц
        patterns = [
            # "2 кг молока", "3 литра воды"
            r'(\d+(?:[.,]\d+)?)\s*([а-я]+)\s+(.+)',
            # "молоко 2 кг", "вода 3 литра" 
            r'(.+?)\s+(\d+(?:[.,]\d+)?)\s*([а-я]+)$',
            # "молоко - 2 кг", "хлеб - 1 шт"
            r'(.+?)\s*[-–]\s*(\d+(?:[.,]\d+)?)\s*([а-я]+)$',
            # "2кг молока" (без пробела)
            r'(\d+(?:[.,]\d+)?)([а-я]+)\s+(.+)',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                groups = match.groups()
                
                if len(groups) == 3:
                    # Определяем порядок: количество, единица, название
                    if self._is_number(groups[0]):
                        quantity_str, unit_str, name = groups
                    elif self._is_number(groups[1]):
                        name, quantity_str, unit_str = groups
                    else:
                        continue
                    
                    quantity = self._parse_quantity(quantity_str)
                    unit = self._normalize_unit(unit_str)
                    name = name.strip()
                    
                    if quantity and unit and name:
                        return Product(
                            name=name,
                            quantity=quantity,
                            unit=unit,
                            original_text=original_line
                        )
        
        # Если не удалось найти количество, пробуем найти только название
        clean_name = re.sub(r'^[-*•]\s*', '', original_line.strip())
        clean_name = re.sub(r'^\d+[\.)]\s*', '', clean_name)
        
        if clean_name:
            return Product(
                name=clean_name,
                quantity=1.0,
                unit='шт',
                original_text=original_line
            )
        
        return None
    
    def _is_number(self, s: str) -> bool:
        """Проверка, является ли строка числом"""
        try:
            float(s.replace(',', '.'))
            return True
        except ValueError:
            return False
    
    def _parse_quantity(self, quantity_str: str) -> Optional[float]:
        """Парсинг количества из строки"""
        try:
            # Заменяем запятую на точку для float
            quantity_str = quantity_str.replace(',', '.')
            return float(quantity_str)
        except ValueError:
            return None
    
    def _normalize_unit(self, unit_str: str) -> Optional[str]:
        """Нормализация единицы измерения"""
        unit_str = unit_str.lower().strip()
        return self.unit_lookup.get(unit_str)


# Глобальный экземпляр парсера
product_parser = ProductParser()
