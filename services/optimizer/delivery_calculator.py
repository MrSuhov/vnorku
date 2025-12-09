"""
Калькулятор стоимости доставки для корзин.
Читает данные из basket_combinations и рассчитывает delivery_cost и topup.
"""

import logging
from typing import List, Dict, Any, Tuple
import psycopg2
from psycopg2.extras import execute_values
import time
import csv
import tempfile
import json

logger = logging.getLogger(__name__)


class DeliveryCalculator:
    """Калькулятор стоимости доставки для basket_combinations"""
    
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
    
    def calculate_delivery_by_model(self, delivery_model: dict, total_cost: float, delivery_fixed_fee: float = 0.0) -> float:
        """
        Рассчитывает стоимость доставки на основе модели доставки.
        
        Args:
            delivery_model: JSON модель доставки из lsd_config
            total_cost: Общая стоимость товаров в корзине для ЛСД
            delivery_fixed_fee: Фиксированная доплата за доставку
            
        Returns:
            Стоимость доставки (базовая + фиксированная доплата)
        """
        if not delivery_model or 'delivery_cost' not in delivery_model:
            return float(delivery_fixed_fee)  # Только фиксированная доплата
        
        delivery_ranges = delivery_model.get('delivery_cost', [])
        
        # Проходим по диапазонам в порядке возрастания min
        for range_item in sorted(delivery_ranges, key=lambda x: x.get('min', 0)):
            min_amount = range_item.get('min', 0) or 0
            max_amount = range_item.get('max')
            delivery_fee = range_item.get('fee', 0)
            
            # Проверяем попадает ли total_cost в диапазон
            if total_cost >= min_amount:
                if max_amount is None or total_cost < max_amount:
                    base_delivery_cost = float(delivery_fee)
                    total_delivery_cost = base_delivery_cost + float(delivery_fixed_fee)
                    return total_delivery_cost
        
        # Если не нашли подходящий диапазон, возвращаем только фиксированную доплату
        return float(delivery_fixed_fee)
    
    def fetch_basket_data(self, order_id: int) -> List[Dict[str, Any]]:
        """
        Получает данные из basket_combinations, сгруппированные по basket_id и lsd_config_id.
        
        Args:
            order_id: ID заказа
            
        Returns:
            Список словарей с данными для расчёта доставки
        """
        query = """
            SELECT 
                basket_id,
                lsd_config_id,
                SUM(order_item_ids_cost) as total_basket_cost,
                -- Берем первую модель доставки (они одинаковые для одного ЛСД)
                (array_agg(delivery_cost_model))[1] as delivery_model,
                (array_agg(min_order_amount))[1] as min_order_amount,
                -- НОВОЕ: добавляем delivery_fixed_fee
                COALESCE((SELECT delivery_fixed_fee FROM lsd_configs WHERE id = lsd_config_id), 0) as delivery_fixed_fee
            FROM basket_combinations
            WHERE order_id = %s
                AND lsd_config_id IS NOT NULL
                AND order_item_ids_cost IS NOT NULL
            GROUP BY basket_id, lsd_config_id
            ORDER BY basket_id, lsd_config_id
        """
        
        with self.conn.cursor() as cur:
            cur.execute(query, (order_id,))
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
        
        if not rows:
            logger.warning(f"Нет данных в basket_combinations для заказа {order_id}")
            return []
        
        result = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            result.append(row_dict)
        
        logger.info(f"Получено {len(result)} записей корзин × ЛСД для расчёта доставки")
        return result
    
    def calculate_delivery_costs(self, basket_data: List[Dict[str, Any]]) -> List[Tuple]:
        """
        Рассчитывает стоимость доставки и topup для каждой корзины × ЛСД.
        
        Args:
            basket_data: Список данных из fetch_basket_data
            
        Returns:
            Список кортежей для вставки в basket_delivery_costs
        """
        logger.info(f"Начинаем расчёт стоимости доставки для {len(basket_data)} записей...")
        start_time = time.time()
        
        rows = []
        
        for item in basket_data:
            basket_id = item['basket_id']
            lsd_config_id = item['lsd_config_id']
            total_basket_cost = float(item['total_basket_cost'])
            delivery_model = item['delivery_model']
            min_order_amount = float(item['min_order_amount'] or 0)
            delivery_fixed_fee = float(item['delivery_fixed_fee'] or 0)  # НОВОЕ: извлекаем фиксированную доплату

            # Рассчитываем topup (сколько нужно доплатить до минимальной суммы)
            topup = 0.0
            if min_order_amount > 0 and total_basket_cost < min_order_amount:
                topup = min_order_amount - total_basket_cost

            # ВАЖНО: Рассчитываем стоимость доставки от суммы ПОСЛЕ топапа
            # Потому что топап поднимает сумму корзины, и доставка рассчитывается от новой суммы
            total_with_topup = total_basket_cost + topup
            delivery_cost = self.calculate_delivery_by_model(delivery_model, total_with_topup, delivery_fixed_fee)
            
            row = (
                basket_id,
                lsd_config_id,
                delivery_cost,
                topup,
                total_basket_cost,
                min_order_amount
            )
            rows.append(row)
        
        elapsed = time.time() - start_time
        logger.info(f"Рассчитано {len(rows)} записей за {elapsed:.2f} сек")
        
        return rows
    
    def save_to_db_via_csv(self, rows: List[Tuple], order_id: int):
        """
        Записывает результаты в basket_delivery_costs через CSV и COPY FROM.
        
        Args:
            rows: Список кортежей для вставки
            order_id: ID заказа (для удаления старых записей)
        """
        if not rows:
            logger.warning("Нет данных для записи")
            return
        
        logger.info(f"Начинаем запись {len(rows):,} строк через CSV...")
        start_time = time.time()
        
        # Удаляем старые данные для корзин этого заказа
        with self.conn.cursor() as cur:
            cur.execute("""
                DELETE FROM basket_delivery_costs 
                WHERE basket_id IN (
                    SELECT DISTINCT basket_id 
                    FROM basket_combinations 
                    WHERE order_id = %s
                )
            """, (order_id,))
            deleted = cur.rowcount
            if deleted > 0:
                logger.info(f"Удалено {deleted:,} старых строк")
        
        # Создаем временный CSV файл
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as csvfile:
            temp_filename = csvfile.name
            logger.info(f"Создан временный файл: {temp_filename}")
            
            csv_writer = csv.writer(csvfile)
            csv_start = time.time()
            
            for row in rows:
                csv_writer.writerow(row)
            
            csv_elapsed = time.time() - csv_start
            logger.info(f"CSV файл записан за {csv_elapsed:.2f} сек")
        
        # Загружаем через COPY FROM
        copy_start = time.time()
        with open(temp_filename, 'r') as f:
            with self.conn.cursor() as cur:
                cur.copy_expert(
                    """
                    COPY basket_delivery_costs (
                        basket_id, lsd_config_id, delivery_cost, topup,
                        lsd_total_basket_cost, min_order_amount
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
                """
                SELECT COUNT(*) 
                FROM basket_delivery_costs 
                WHERE basket_id IN (
                    SELECT DISTINCT basket_id 
                    FROM basket_combinations 
                    WHERE order_id = %s
                )
                """,
                (order_id,)
            )
            row_count = cur.fetchone()[0]
        
        logger.info(f"Результат: {row_count:,} строк в basket_delivery_costs")
    
    def calculate_basket_delivery_costs(self, order_id: int) -> Dict[str, Any]:
        """
        Главная функция: рассчитывает и записывает стоимость доставки для всех корзин заказа.
        
        Args:
            order_id: ID заказа
            
        Returns:
            Dict с результатами: row_count, elapsed_time
        """
        total_start = time.time()
        
        logger.info(f"=" * 80)
        logger.info(f"Расчёт стоимости доставки для заказа {order_id}")
        logger.info(f"=" * 80)
        
        # 1. Получаем данные из basket_combinations
        basket_data = self.fetch_basket_data(order_id)
        if not basket_data:
            return {"row_count": 0, "elapsed_time": 0}
        
        # 2. Рассчитываем стоимость доставки
        rows = self.calculate_delivery_costs(basket_data)
        
        # 3. Записываем в БД через CSV
        self.save_to_db_via_csv(rows, order_id)
        
        total_elapsed = time.time() - total_start
        
        logger.info(f"=" * 80)
        logger.info(f"ИТОГО: {len(rows):,} записей за {total_elapsed:.2f} сек")
        logger.info(f"=" * 80)
        
        return {
            "row_count": len(rows),
            "elapsed_time": total_elapsed
        }


def calculate_basket_delivery_costs_for_order(order_id: int, db_connection_string: str) -> Dict[str, Any]:
    """
    Удобная функция-обёртка для расчёта стоимости доставки.
    
    Args:
        order_id: ID заказа
        db_connection_string: PostgreSQL connection string
        
    Returns:
        Dict с результатами
    """
    with DeliveryCalculator(db_connection_string) as calculator:
        return calculator.calculate_basket_delivery_costs(order_id)


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
    result = calculate_basket_delivery_costs_for_order(16, db_url)
    print(f"\nРезультат: {result}")
