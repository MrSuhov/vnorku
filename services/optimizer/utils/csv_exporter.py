"""
Экспорт промежуточных результатов оптимизации в CSV для анализа.
"""

import csv
import os
from datetime import datetime
from typing import List, Tuple, Any
import logging

logger = logging.getLogger(__name__)


class CSVExporter:
    """Экспортер данных в CSV для отладки"""
    
    def __init__(self, base_dir: str = None):
        """
        Args:
            base_dir: Базовая директория для сохранения CSV (по умолчанию logs/optimizer/debug)
        """
        if base_dir is None:
            # Определяем путь к logs/optimizer/debug относительно корня проекта
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            base_dir = os.path.join(project_root, 'logs', 'optimizer', 'debug')
        
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        logger.info(f"CSV exporter initialized: {self.base_dir}")
    
    def _get_filename(self, order_id: int, table_name: str) -> str:
        """
        Генерирует имя файла с временной меткой.
        
        Args:
            order_id: ID заказа
            table_name: Имя таблицы (basket_combinations, basket_delivery_costs, basket_analyses)
            
        Returns:
            Полный путь к файлу
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"order_{order_id}_{table_name}_{timestamp}.csv"
        return os.path.join(self.base_dir, filename)
    
    def export_basket_combinations(self, rows: List[Tuple], order_id: int) -> str:
        """
        Экспортирует данные basket_combinations в CSV.
        
        Args:
            rows: Список кортежей из prepare_basket_rows
            order_id: ID заказа
            
        Returns:
            Путь к созданному файлу
        """
        filepath = self._get_filename(order_id, 'basket_combinations')
        
        headers = [
            'basket_id', 'id', 'order_id', 'order_item_id', 'product_name', 'lsd_name',
            'base_unit', 'base_quantity', 'price', 'fprice', 'fprice_min', 'fprice_diff',
            'loss', 'order_item_ids_quantity', 'min_order_amount', 'lsd_config_id',
            'delivery_cost_model', 'order_item_ids_cost', 'fprice_optimizer_id'
        ]
        
        logger.info(f"Экспорт basket_combinations: {len(rows):,} строк → {filepath}")
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for row in rows:
                # Конвертируем Json объект в строку для CSV
                csv_row = list(row)
                # delivery_cost_model на позиции 16 (0-based)
                if hasattr(csv_row[16], 'adapted'):  # Json object
                    import json
                    csv_row[16] = json.dumps(csv_row[16].adapted)
                elif isinstance(csv_row[16], dict):
                    import json
                    csv_row[16] = json.dumps(csv_row[16])
                writer.writerow(csv_row)
        
        logger.info(f"✓ Сохранено: {filepath}")
        return filepath
    
    def export_basket_delivery_costs(self, rows: List[Tuple], order_id: int) -> str:
        """
        Экспортирует данные basket_delivery_costs в CSV.
        
        Args:
            rows: Список кортежей из calculate_delivery_costs
            order_id: ID заказа
            
        Returns:
            Путь к созданному файлу
        """
        filepath = self._get_filename(order_id, 'basket_delivery_costs')
        
        headers = [
            'basket_id', 'lsd_config_id', 'delivery_cost', 'topup',
            'lsd_total_basket_cost', 'min_order_amount'
        ]
        
        logger.info(f"Экспорт basket_delivery_costs: {len(rows):,} строк → {filepath}")
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        
        logger.info(f"✓ Сохранено: {filepath}")
        return filepath
    
    def export_basket_analyses(self, rows: List[Tuple], order_id: int) -> str:
        """
        Экспортирует данные basket_analyses в CSV.
        
        Args:
            rows: Список кортежей из analyze_baskets
            order_id: ID заказа
            
        Returns:
            Путь к созданному файлу
        """
        filepath = self._get_filename(order_id, 'basket_analyses')
        
        headers = [
            'order_id', 'basket_id', 'total_loss', 'total_goods_cost',
            'delivery_cost', 'delivery_topup', 'total_delivery_cost',
            'total_cost', 'total_loss_and_delivery'
        ]
        
        logger.info(f"Экспорт basket_analyses: {len(rows):,} строк → {filepath}")
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        
        logger.info(f"✓ Сохранено: {filepath}")
        return filepath
