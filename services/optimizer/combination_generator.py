"""
Генератор комбинаций корзин для оптимизатора заказов.
Использует Python для быстрой генерации всех возможных комбинаций товаров.
"""

import logging
from typing import List, Dict, Any, Tuple
from itertools import product
import psycopg2
from psycopg2.extras import execute_values, Json
import time
import csv
import tempfile
import json

logger = logging.getLogger(__name__)


class CombinationGenerator:
    """Генератор комбинаций товаров для basket_combinations"""
    
    def __init__(self, db_connection_string: str):
        """
        Args:
            db_connection_string: PostgreSQL connection string
        """
        self.db_connection_string = db_connection_string
        self.conn = None
        
    def __enter__(self):
        self.conn = psycopg2.connect(self.db_connection_string)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
    
    def fetch_fprice_data(self, order_id: int) -> Dict[int, List[Dict[str, Any]]]:
        """
        Получает данные из fprice_optimizer, сгруппированные по order_item_id.
        
        Args:
            order_id: ID заказа
            
        Returns:
            Dict где ключ = order_item_id, значение = список вариантов товара
        """
        query = """
            SELECT 
                id, order_id, lsd_config_id, lsd_name, order_item_id, product_name,
                price, fprice, base_unit, base_quantity, requested_unit, requested_quantity,
                order_item_ids_quantity, order_item_ids_cost, fprice_min, fprice_diff, 
                loss, min_order_amount, delivery_cost_model
            FROM fprice_optimizer
            WHERE order_id = %s
            ORDER BY order_item_id, id
        """
        
        with self.conn.cursor() as cur:
            cur.execute(query, (order_id,))
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
        
        if not rows:
            logger.warning(f"Нет данных в fprice_optimizer для заказа {order_id}")
            return {}
        
        # Группируем по order_item_id
        grouped = {}
        for row in rows:
            row_dict = dict(zip(columns, row))
            order_item_id = row_dict['order_item_id']
            
            if order_item_id not in grouped:
                grouped[order_item_id] = []
            grouped[order_item_id].append(row_dict)
        
        # Логируем статистику
        for order_item_id, variants in sorted(grouped.items()):
            logger.info(f"Товар order_item_id={order_item_id}: {len(variants)} вариантов")
        
        return grouped
    
    def generate_combinations(self, grouped_data: Dict[int, List[Dict[str, Any]]]) -> Tuple[int, List[List[Dict[str, Any]]]]:
        """
        Генерирует все возможные комбинации товаров.
        
        Args:
            grouped_data: Данные, сгруппированные по order_item_id
            
        Returns:
            Tuple (expected_count, combinations) где:
                - expected_count: ожидаемое количество комбинаций
                - combinations: список комбинаций, каждая комбинация = список вариантов товаров
        """
        if not grouped_data:
            return 0, []
        
        # Сортируем order_item_id для детерминированного порядка
        sorted_items = sorted(grouped_data.keys())
        
        # Подготавливаем списки вариантов для каждого товара
        variant_lists = [grouped_data[item_id] for item_id in sorted_items]
        
        # Считаем ожидаемое количество комбинаций
        expected_count = 1
        for variants in variant_lists:
            expected_count *= len(variants)
        
        logger.info(f"Ожидается {expected_count:,} комбинаций")
        
        # Генерируем комбинации через itertools.product
        logger.info("Начинаем генерацию комбинаций...")
        start_time = time.time()
        
        combinations = list(product(*variant_lists))
        
        elapsed = time.time() - start_time
        logger.info(f"Сгенерировано {len(combinations):,} комбинаций за {elapsed:.2f} сек")
        
        return expected_count, combinations
    
    def prepare_basket_rows(self, combinations: List[Tuple[Dict[str, Any], ...]], 
                           order_id: int) -> List[Tuple]:
        """
        Преобразует комбинации в строки для вставки в basket_combinations.
        
        Args:
            combinations: Список комбинаций из generate_combinations
            order_id: ID заказа
            
        Returns:
            Список кортежей для вставки в БД
        """
        logger.info(f"Подготовка {len(combinations):,} комбинаций × товаров к записи...")
        start_time = time.time()
        
        rows = []
        basket_id = 1
        
        for combination in combinations:
            # Каждая комбинация - это кортеж вариантов товаров
            for variant in combination:
                row = (
                    basket_id,                              # basket_id
                    variant['id'],                          # id
                    order_id,                               # order_id
                    variant['order_item_id'],               # order_item_id
                    variant['product_name'],                # product_name
                    variant['lsd_name'],                    # lsd_name
                    variant['base_unit'],                   # base_unit
                    variant['base_quantity'],               # base_quantity
                    variant['price'],                       # price
                    variant['fprice'],                      # fprice
                    variant['fprice_min'],                  # fprice_min
                    variant['fprice_diff'],                 # fprice_diff
                    variant['loss'],                        # loss
                    variant['order_item_ids_quantity'],     # order_item_ids_quantity
                    variant['min_order_amount'],            # min_order_amount
                    variant['lsd_config_id'],               # lsd_config_id
                    Json(variant['delivery_cost_model']),   # delivery_cost_model (convert dict to JSON)
                    variant['order_item_ids_cost'],         # order_item_ids_cost
                )
                rows.append(row)
            
            basket_id += 1
        
        elapsed = time.time() - start_time
        logger.info(f"Подготовлено {len(rows):,} строк за {elapsed:.2f} сек")
        
        return rows
    
    def save_to_db_via_csv(self, rows: List[Tuple], order_id: int):
        """
        Записывает строки в таблицу basket_combinations через CSV и COPY FROM.
        
        Args:
            rows: Список кортежей для вставки
            order_id: ID заказа
        """
        if not rows:
            logger.warning("Нет данных для записи")
            return
        
        logger.info(f"Начинаем запись {len(rows):,} строк через CSV...")
        start_time = time.time()
        
        # Удаляем старые данные
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM basket_combinations WHERE order_id = %s", (order_id,))
            deleted = cur.rowcount
            if deleted > 0:
                logger.info(f"Удалено {deleted:,} старых строк")
        
        # Создаем временный CSV файл
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as csvfile:
            temp_filename = csvfile.name
            logger.info(f"Создан временный файл: {temp_filename}")
            
            csv_writer = csv.writer(csvfile)
            
            # Конвертируем строки для CSV
            csv_start = time.time()
            for row in rows:
                # Преобразуем Json объект обратно в строку
                csv_row = list(row)
                # delivery_cost_model находится на позиции 16 (0-based)
                if isinstance(csv_row[16], Json):
                    csv_row[16] = json.dumps(csv_row[16].adapted)
                elif isinstance(csv_row[16], dict):
                    csv_row[16] = json.dumps(csv_row[16])
                csv_writer.writerow(csv_row)
            
            csv_elapsed = time.time() - csv_start
            logger.info(f"CSV файл записан за {csv_elapsed:.2f} сек")
        
        # Загружаем через COPY FROM
        copy_start = time.time()
        with open(temp_filename, 'r') as f:
            with self.conn.cursor() as cur:
                cur.copy_expert(
                    """
                    COPY basket_combinations (
                        basket_id, id, order_id, order_item_id, product_name, lsd_name,
                        base_unit, base_quantity, price, fprice, fprice_min, fprice_diff,
                        loss, order_item_ids_quantity, min_order_amount, lsd_config_id,
                        delivery_cost_model, order_item_ids_cost
                    ) FROM STDIN WITH (FORMAT CSV)
                    """,
                    f
                )
        
        self.conn.commit()
        copy_elapsed = time.time() - copy_start
        
        # Удаляем временный файл
        import os
        os.unlink(temp_filename)
        logger.info(f"Временный файл удален")
        
        elapsed = time.time() - start_time
        logger.info(f"Записано {len(rows):,} строк за {elapsed:.2f} сек ({len(rows)/elapsed:.0f} строк/сек)")
        logger.info(f"  - CSV запись: {csv_elapsed:.2f} сек")
        logger.info(f"  - COPY FROM: {copy_elapsed:.2f} сек")
        
        # Проверяем результат
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(DISTINCT basket_id) FROM basket_combinations WHERE order_id = %s",
                (order_id,)
            )
            basket_count = cur.fetchone()[0]
            
            cur.execute(
                "SELECT COUNT(*) FROM basket_combinations WHERE order_id = %s",
                (order_id,)
            )
            row_count = cur.fetchone()[0]
        
        logger.info(f"Результат: {basket_count:,} уникальных корзин, {row_count:,} строк")
    
    def generate_basket_combinations(self, order_id: int, batch_size: int = 10000) -> Dict[str, Any]:
        """
        Главная функция: генерирует и записывает все комбинации корзин.
        
        Args:
            order_id: ID заказа
            batch_size: Размер пакета для записи в БД
            
        Returns:
            Dict с результатами: basket_count, row_count, elapsed_time
        """
        total_start = time.time()
        
        logger.info(f"=" * 80)
        logger.info(f"Генерация комбинаций корзин для заказа {order_id}")
        logger.info(f"=" * 80)
        
        # 1. Получаем данные
        grouped_data = self.fetch_fprice_data(order_id)
        if not grouped_data:
            return {"basket_count": 0, "row_count": 0, "elapsed_time": 0}
        
        # 2. Генерируем комбинации
        expected_count, combinations = self.generate_combinations(grouped_data)
        
        # 3. Подготавливаем строки для вставки
        rows = self.prepare_basket_rows(combinations, order_id)
        
        # 4. Записываем в БД через CSV
        self.save_to_db_via_csv(rows, order_id)
        
        total_elapsed = time.time() - total_start
        
        logger.info(f"=" * 80)
        logger.info(f"ИТОГО: {expected_count:,} комбинаций за {total_elapsed:.2f} сек")
        logger.info(f"=" * 80)
        
        return {
            "basket_count": expected_count,
            "row_count": len(rows),
            "elapsed_time": total_elapsed
        }


def generate_basket_combinations_for_order(order_id: int, db_connection_string: str) -> Dict[str, Any]:
    """
    Удобная функция-обёртка для генерации комбинаций.
    
    Args:
        order_id: ID заказа
        db_connection_string: PostgreSQL connection string
        
    Returns:
        Dict с результатами
    """
    with CombinationGenerator(db_connection_string) as generator:
        return generator.generate_basket_combinations(order_id)


if __name__ == "__main__":
    # Пример использования
    import os
    from dotenv import load_dotenv
    
    # Настраиваем логирование
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Загружаем DATABASE_URL из .env
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("ERROR: DATABASE_URL не найден в .env")
        exit(1)
    
    # Тестируем на заказе #16
    result = generate_basket_combinations_for_order(16, db_url)
    print(f"\nРезультат: {result}")
