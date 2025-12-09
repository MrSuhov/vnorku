"""
Анализатор корзин для оптимизатора заказов.
Рассчитывает метрики для каждой корзины и записывает в basket_analyses.
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


class BasketAnalyzer:
    """Анализатор корзин - рассчитывает метрики для каждой корзины"""
    
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
    
    def fetch_basket_combinations_data(self, order_id: int) -> Dict[int, List[Dict[str, Any]]]:
        """
        Получает данные из basket_combinations, сгруппированные по basket_id.
        
        Args:
            order_id: ID заказа
            
        Returns:
            Dict где ключ = basket_id, значение = список товаров в корзине
        """
        query = """
            SELECT 
                basket_id,
                order_item_id,
                lsd_config_id,
                lsd_name,
                product_name,
                order_item_ids_cost,
                loss,
                price,
                fprice
            FROM basket_combinations
            WHERE order_id = %s
            ORDER BY basket_id, order_item_id
        """
        
        with self.conn.cursor() as cur:
            cur.execute(query, (order_id,))
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
        
        if not rows:
            logger.warning(f"Нет данных в basket_combinations для заказа {order_id}")
            return {}
        
        # Группируем по basket_id
        grouped = {}
        for row in rows:
            row_dict = dict(zip(columns, row))
            basket_id = row_dict['basket_id']
            
            if basket_id not in grouped:
                grouped[basket_id] = []
            grouped[basket_id].append(row_dict)
        
        logger.info(f"Получено {len(grouped)} корзин для анализа")
        return grouped
    
    def fetch_basket_delivery_data(self, order_id: int) -> Dict[Tuple[int, int], Dict[str, Any]]:
        """
        Получает данные из basket_delivery_costs.
        
        Args:
            order_id: ID заказа
            
        Returns:
            Dict где ключ = (basket_id, lsd_config_id), значение = данные о доставке
        """
        query = """
            SELECT 
                bdc.basket_id,
                bdc.lsd_config_id,
                bdc.delivery_cost,
                bdc.topup,
                bdc.lsd_total_basket_cost,
                bdc.min_order_amount
            FROM basket_delivery_costs bdc
            WHERE bdc.basket_id IN (
                SELECT DISTINCT basket_id 
                FROM basket_combinations 
                WHERE order_id = %s
            )
            ORDER BY bdc.basket_id, bdc.lsd_config_id
        """
        
        with self.conn.cursor() as cur:
            cur.execute(query, (order_id,))
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
        
        # Группируем по (basket_id, lsd_config_id)
        grouped = {}
        for row in rows:
            row_dict = dict(zip(columns, row))
            key = (row_dict['basket_id'], row_dict['lsd_config_id'])
            grouped[key] = row_dict
        
        logger.info(f"Получено {len(grouped)} записей о доставке")
        return grouped
    
    def analyze_baskets(self, basket_combinations: Dict[int, List[Dict[str, Any]]], 
                       delivery_data: Dict[Tuple[int, int], Dict[str, Any]],
                       order_id: int) -> List[Tuple]:
        """
        Анализирует корзины и рассчитывает метрики.
        
        Args:
            basket_combinations: Данные из basket_combinations, сгруппированные по basket_id
            delivery_data: Данные о доставке, ключ = (basket_id, lsd_config_id)
            order_id: ID заказа
            
        Returns:
            Список кортежей для вставки в basket_analyses
        """
        logger.info(f"Начинаем анализ {len(basket_combinations)} корзин...")
        start_time = time.time()
        
        rows = []
        
        for basket_id, items in basket_combinations.items():
            # Группируем товары по lsd_config_id для расчёта delivery_cost и delivery_topup
            lsd_groups = {}
            for item in items:
                lsd_id = item['lsd_config_id']
                if lsd_id not in lsd_groups:
                    lsd_groups[lsd_id] = {
                        'lsd_name': item['lsd_name'],
                        'items': []
                    }
                lsd_groups[lsd_id]['items'].append(item)
            
            # Рассчитываем метрики
            total_loss = sum(float(item['loss'] or 0) for item in items)
            total_goods_cost = sum(float(item['order_item_ids_cost'] or 0) for item in items)
            
            # Собираем delivery_cost и delivery_topup по ЛСД
            delivery_cost_dict = {}
            delivery_topup_dict = {}
            total_delivery_cost = 0.0
            total_topup = 0.0
            
            for lsd_id, lsd_group in lsd_groups.items():
                lsd_name = lsd_group['lsd_name']
                key = (basket_id, lsd_id)
                
                if key in delivery_data:
                    delivery_info = delivery_data[key]
                    delivery_cost = float(delivery_info['delivery_cost'] or 0)
                    topup = float(delivery_info['topup'] or 0)
                    
                    delivery_cost_dict[lsd_name] = delivery_cost
                    delivery_topup_dict[lsd_name] = topup
                    total_delivery_cost += delivery_cost
                    total_topup += topup
                else:
                    delivery_cost_dict[lsd_name] = 0.0
                    delivery_topup_dict[lsd_name] = 0.0
            
            # Общая стоимость доставки (доставка + топап)
            total_delivery_and_topup = total_delivery_cost + total_topup
            
            # Общая стоимость заказа (товары + доставка + топап)
            total_cost = total_goods_cost + total_delivery_and_topup
            
            # Потери + доставка + топап (ключевая метрика для ранжирования)
            total_loss_and_delivery = total_loss + total_delivery_and_topup
            
            row = (
                order_id,
                basket_id,
                round(total_loss, 2),
                round(total_goods_cost, 2),
                json.dumps(delivery_cost_dict),  # delivery_cost как JSON
                json.dumps(delivery_topup_dict),  # delivery_topup как JSON
                round(total_delivery_and_topup, 2),  # ИСПРАВЛЕНО: теперь включает топап
                round(total_cost, 2),
                round(total_loss_and_delivery, 2)
            )
            rows.append(row)
        
        elapsed = time.time() - start_time
        logger.info(f"Проанализировано {len(rows)} корзин за {elapsed:.2f} сек")
        
        return rows
    
    def save_to_db_via_csv(self, rows: List[Tuple], order_id: int):
        """
        Записывает результаты анализа в basket_analyses через CSV и COPY FROM.
        
        Args:
            rows: Список кортежей для вставки
            order_id: ID заказа (для удаления старых записей)
        """
        if not rows:
            logger.warning("Нет данных для записи")
            return
        
        logger.info(f"Начинаем запись {len(rows):,} строк через CSV...")
        start_time = time.time()
        
        # Удаляем старые данные для этого заказа
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM basket_analyses WHERE order_id = %s", (order_id,))
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
                    COPY basket_analyses (
                        order_id, basket_id, total_loss, total_goods_cost,
                        delivery_cost, delivery_topup, total_delivery_cost,
                        total_cost, total_loss_and_delivery
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
        
        # Обновляем basket_rank для корзин этого заказа
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE basket_analyses ba
                SET basket_rank = ranked.rank
                FROM (
                    SELECT 
                        id,
                        ROW_NUMBER() OVER (
                            ORDER BY total_loss_and_delivery ASC, total_cost ASC
                        ) as rank
                    FROM basket_analyses
                    WHERE order_id = %s
                ) ranked
                WHERE ba.id = ranked.id
            """, (order_id,))
            updated = cur.rowcount
            self.conn.commit()
            logger.info(f"Обновлено basket_rank для {updated} корзин")
        
        elapsed = time.time() - start_time
        logger.info(f"Записано {len(rows):,} строк за {elapsed:.2f} сек ({len(rows)/elapsed:.0f} строк/сек)")
        logger.info(f"  - CSV запись: {csv_elapsed:.2f} сек")
        logger.info(f"  - COPY FROM: {copy_elapsed:.2f} сек")
        
        # Получаем и выводим лучшую корзину
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT basket_id, total_loss_and_delivery, total_cost
                FROM basket_analyses
                WHERE order_id = %s
                ORDER BY total_loss_and_delivery ASC, total_cost ASC
                LIMIT 1
            """, (order_id,))
            best = cur.fetchone()
            
            if best:
                logger.info(f"Лучшая корзина: basket_id={best[0]}, потери+доставка={best[1]}₽, итого={best[2]}₽")
    
    def analyze_order_baskets(self, order_id: int) -> Dict[str, Any]:
        """
        Главная функция: анализирует все корзины заказа и записывает результаты.
        
        Args:
            order_id: ID заказа
            
        Returns:
            Dict с результатами: basket_count, best_basket_id, best_total_cost, elapsed_time
        """
        total_start = time.time()
        
        logger.info(f"=" * 80)
        logger.info(f"Анализ корзин для заказа {order_id}")
        logger.info(f"=" * 80)
        
        # 1. Получаем данные из basket_combinations
        basket_combinations = self.fetch_basket_combinations_data(order_id)
        if not basket_combinations:
            return {"basket_count": 0, "best_basket_id": None, "best_total_cost": 0, "elapsed_time": 0}
        
        # 2. Получаем данные о доставке
        delivery_data = self.fetch_basket_delivery_data(order_id)
        
        # 3. Анализируем корзины
        rows = self.analyze_baskets(basket_combinations, delivery_data, order_id)
        
        # 4. Записываем в БД через CSV
        self.save_to_db_via_csv(rows, order_id)
        
        # 5. Получаем информацию о лучшей корзине
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT basket_id, total_cost
                FROM basket_analyses
                WHERE order_id = %s
                ORDER BY total_loss_and_delivery ASC, total_cost ASC
                LIMIT 1
            """, (order_id,))
            best = cur.fetchone()
        
        total_elapsed = time.time() - total_start
        
        logger.info(f"=" * 80)
        logger.info(f"ИТОГО: {len(rows):,} корзин проанализировано за {total_elapsed:.2f} сек")
        logger.info(f"=" * 80)
        
        return {
            "basket_count": len(rows),
            "best_basket_id": best[0] if best else None,
            "best_total_cost": float(best[1]) if best else 0,
            "elapsed_time": total_elapsed
        }


def analyze_order_baskets_for_order(order_id: int, db_connection_string: str) -> Dict[str, Any]:
    """
    Удобная функция-обёртка для анализа корзин.
    
    Args:
        order_id: ID заказа
        db_connection_string: PostgreSQL connection string
        
    Returns:
        Dict с результатами
    """
    with BasketAnalyzer(db_connection_string) as analyzer:
        return analyzer.analyze_order_baskets(order_id)


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
    result = analyze_order_baskets_for_order(16, db_url)
    print(f"\nРезультат: {result}")
