"""
Оптимизатор заказов с режимом отладки.
Расширенная версия order_optimizer.py с сохранением промежуточных данных в CSV и временные таблицы.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
from itertools import product
import psycopg2
import time
import json
import sys
import os

# Импортируем базовый оптимизатор
from order_optimizer import OrderOptimizer as BaseOptimizer

# Импортируем CSV exporter
from utils.csv_exporter import CSVExporter

logger = logging.getLogger('order_optimizer_debug')


class OrderOptimizerDebug(BaseOptimizer):
    """Оптимизатор с поддержкой debug-режима для анализа промежуточных данных"""
    
    def __init__(self, db_connection_string: str, debug_mode: bool = False):
        """
        Args:
            db_connection_string: PostgreSQL connection string
            debug_mode: Включить режим отладки (сохранение всех данных в CSV и БД)
        """
        super().__init__(db_connection_string)
        self.debug_mode = debug_mode
        self.csv_exporter = CSVExporter() if debug_mode else None
        self.debug_files = {}
        
        if debug_mode:
            logger.info("🔍 Debug mode ENABLED - промежуточные данные будут сохранены")
        else:
            logger.info("⚡ Normal mode - только топ-N корзин в БД")
    
    def __enter__(self):
        """Переопределяем __enter__ чтобы инициализировать debug таблицы после подключения"""
        # Вызываем родительский __enter__ для создания соединения
        super().__enter__()
        
        # Теперь можно инициализировать временные таблицы
        if self.debug_mode:
            self._init_debug_tables()
        
        return self
    
    def _init_debug_tables(self):
        """Создаёт временные таблицы для отладки если их нет"""
        sql_file = os.path.join(os.path.dirname(__file__), 'sql', 'debug_tables.sql')
        
        if not os.path.exists(sql_file):
            logger.warning(f"SQL файл не найден: {sql_file}")
            return
        
        logger.info("Создаём временные таблицы для отладки...")
        
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql = f.read()
        
        with self.conn.cursor() as cur:
            cur.execute(sql)
        self.conn.commit()
        
        logger.info("✓ Временные таблицы готовы: _basket_combinations, _basket_delivery_costs, _basket_analyses")
    
    def _prepare_basket_rows_for_csv(self, combinations: List[Tuple], order_id: int) -> List[Tuple]:
        """Подготавливает строки для basket_combinations (без Json объектов)"""
        rows = []
        basket_id = 1
        
        for combination in combinations:
            for variant in combination:
                row = (
                    basket_id, variant['id'], order_id, variant['order_item_id'],
                    variant['product_name'], variant['lsd_name'], variant['base_unit'],
                    variant['base_quantity'], variant['price'], variant['fprice'],
                    variant['fprice_min'], variant['fprice_diff'], variant['loss'],
                    variant['order_item_ids_quantity'], variant['min_order_amount'],
                    variant['lsd_config_id'], 
                    json.dumps(variant['delivery_cost_model']),
                    variant['order_item_ids_cost'],
                    variant['id']  # fprice_optimizer_id в конце
                )
                rows.append(row)
            basket_id += 1
        
        return rows
    
    def _prepare_delivery_rows(self, analyzed_baskets: List[Dict[str, Any]]) -> List[Tuple]:
        """Подготавливает строки для basket_delivery_costs"""
        rows = []
        
        for basket in analyzed_baskets:
            basket_id = basket['basket_id']
            for lsd_id, info in basket['delivery_info'].items():
                row = (
                    basket_id, lsd_id, info['delivery_cost'], info['topup'],
                    info['lsd_total_basket_cost'], info['min_order_amount']
                )
                rows.append(row)
        
        return rows
    
    def _prepare_analysis_rows(self, analyzed_baskets: List[Dict[str, Any]]) -> List[Tuple]:
        """Подготавливает строки для basket_analyses"""
        rows = []
        
        for rank, basket in enumerate(analyzed_baskets, start=1):
            row = (
                basket['order_id'],
                basket['basket_id'],
                basket['total_loss'],
                basket['total_goods_cost'],
                json.dumps(basket['delivery_cost_json']),
                json.dumps(basket['delivery_topup_json']),
                basket['total_delivery_cost'],
                basket['total_cost'],
                basket['total_loss_and_delivery'],
                rank
            )
            rows.append(row)
        
        return rows
    
    def _save_to_debug_tables(self, bc_rows: List[Tuple], bdc_rows: List[Tuple], ba_rows: List[Tuple]):
        """Сохраняет все данные во временные таблицы через COPY FROM для максимальной скорости"""
        logger.info("Сохранение данных во временные таблицы через COPY FROM...")
        start_time = time.time()
        
        with self.conn.cursor() as cur:
            # Очищаем временные таблицы
            cur.execute("SELECT clear_debug_tables()")
            
            # _basket_combinations через COPY
            if bc_rows:
                import io
                buf = io.StringIO()
                for row in bc_rows:
                    # Преобразуем кортеж в строку для COPY
                    # Экранируем табуляции и переносы строк в данных
                    line = '\t'.join(
                        str(val).replace('\t', ' ').replace('\n', ' ').replace('\r', ' ') if val is not None else '\\N'
                        for val in row
                    )
                    buf.write(line + '\n')
                
                buf.seek(0)
                cur.copy_from(
                    buf,
                    '_basket_combinations',
                    columns=(
                        'basket_id', 'id', 'order_id', 'order_item_id', 
                        'product_name', 'lsd_name', 'base_unit', 'base_quantity', 'price', 
                        'fprice', 'fprice_min', 'fprice_diff', 'loss', 'order_item_ids_quantity', 
                        'min_order_amount', 'lsd_config_id', 'delivery_cost_model', 'order_item_ids_cost',
                        'fprice_optimizer_id'
                    )
                )
                logger.info(f"  ✓ _basket_combinations: {len(bc_rows):,} строк")
            
            # _basket_delivery_costs через COPY
            if bdc_rows:
                buf = io.StringIO()
                for row in bdc_rows:
                    line = '\t'.join(
                        str(val) if val is not None else '\\N'
                        for val in row
                    )
                    buf.write(line + '\n')
                
                buf.seek(0)
                cur.copy_from(
                    buf,
                    '_basket_delivery_costs',
                    columns=('basket_id', 'lsd_config_id', 'delivery_cost', 'topup', 'lsd_total_basket_cost', 'min_order_amount')
                )
                logger.info(f"  ✓ _basket_delivery_costs: {len(bdc_rows):,} строк")
            
            # _basket_analyses через COPY
            if ba_rows:
                buf = io.StringIO()
                for row in ba_rows:
                    line = '\t'.join(
                        str(val).replace('\t', ' ').replace('\n', ' ').replace('\r', ' ') if val is not None else '\\N'
                        for val in row
                    )
                    buf.write(line + '\n')
                
                buf.seek(0)
                cur.copy_from(
                    buf,
                    '_basket_analyses',
                    columns=(
                        'order_id', 'basket_id', 'total_loss', 'total_goods_cost',
                        'delivery_cost', 'delivery_topup', 'total_delivery_cost',
                        'total_cost', 'total_loss_and_delivery', 'basket_rank'
                    )
                )
                logger.info(f"  ✓ _basket_analyses: {len(ba_rows):,} строк")
        
        self.conn.commit()
        elapsed = time.time() - start_time
        total_rows = len(bc_rows) + len(bdc_rows) + len(ba_rows)
        logger.info(f"✓ Временные таблицы заполнены за {elapsed:.2f} сек ({total_rows/elapsed:.0f} строк/сек)")
    
    def optimize_order_debug(self, order_id: int, top_n: int = 10) -> Dict[str, Any]:
        """
        Полная оптимизация с сохранением промежуточных данных (debug режим).
        
        Args:
            order_id: ID заказа
            top_n: Количество лучших корзин для сохранения в основные таблицы
            
        Returns:
            Dict с результатами + пути к CSV файлам
        """
        total_start = time.time()
        
        logger.info("=" * 80)
        logger.info(f"🔍 DEBUG ОПТИМИЗАЦИЯ ЗАКАЗА #{order_id}")
        logger.info("=" * 80)
        
        # Этап 1: Генерация комбинаций
        logger.info("\n[1/5] Генерация комбинаций...")
        grouped_data = self.fetch_fprice_data(order_id)
        if not grouped_data:
            return {"status": "no_data", "elapsed_time": 0}
        
        combinations = self.generate_combinations_in_memory(grouped_data)
        
        # Этап 2: Анализ всех корзин
        logger.info("\n[2/5] Анализ всех корзин...")
        analyzed_baskets = self.analyze_all_baskets(combinations, order_id)
        
        # Этап 3: Подготовка данных для сохранения
        logger.info("\n[3/5] Подготовка данных для экспорта...")
        bc_rows = self._prepare_basket_rows_for_csv(combinations, order_id)
        bdc_rows = self._prepare_delivery_rows(analyzed_baskets)
        ba_rows = self._prepare_analysis_rows(analyzed_baskets)
        
        logger.info(f"  Подготовлено строк:")
        logger.info(f"    basket_combinations: {len(bc_rows):,}")
        logger.info(f"    basket_delivery_costs: {len(bdc_rows):,}")
        logger.info(f"    basket_analyses: {len(ba_rows):,}")
        
        # Этап 4: Сохранение в CSV
        if self.csv_exporter:
            logger.info("\n[4/5] Экспорт в CSV...")
            self.debug_files['basket_combinations'] = self.csv_exporter.export_basket_combinations(bc_rows, order_id)
            self.debug_files['basket_delivery_costs'] = self.csv_exporter.export_basket_delivery_costs(bdc_rows, order_id)
            self.debug_files['basket_analyses'] = self.csv_exporter.export_basket_analyses(ba_rows, order_id)
            
            logger.info("\n📁 CSV файлы сохранены:")
            for table, filepath in self.debug_files.items():
                logger.info(f"  {table}: {filepath}")
        
        # Этап 5: Сохранение во временные таблицы БД
        if self.debug_mode:
            logger.info("\n[5/5] Сохранение во временные таблицы БД...")
            self._save_to_debug_tables(bc_rows, bdc_rows, ba_rows)
        
        # Сохраняем топ-N в основные таблицы (как обычно)
        logger.info(f"\n[Финал] Запись топ-{top_n} в основные таблицы...")
        top_baskets = analyzed_baskets[:top_n]
        for rank, basket in enumerate(top_baskets, start=1):
            basket['rank'] = rank
        
        self.save_top_baskets_to_db(top_baskets, order_id)
        
        total_elapsed = time.time() - total_start
        
        # Итоговая статистика
        best = analyzed_baskets[0]
        logger.info(f"\n" + "=" * 80)
        logger.info(f"✅ DEBUG ОПТИМИЗАЦИЯ ЗАВЕРШЕНА")
        logger.info(f"=" * 80)
        logger.info(f"Всего комбинаций: {len(combinations):,}")
        logger.info(f"Проанализировано корзин: {len(analyzed_baskets):,}")
        logger.info(f"Сохранено в основных таблицах: топ-{len(top_baskets)}")
        logger.info(f"Сохранено во временных таблицах: все {len(analyzed_baskets):,} корзин")
        logger.info(f"\nЛучшая корзина: #{best['basket_id']}")
        logger.info(f"  - Потери + доставка: {best['total_loss_and_delivery']:.2f}₽")
        logger.info(f"  - Итого: {best['total_cost']:.2f}₽")
        logger.info(f"\nВремя выполнения: {total_elapsed:.2f} сек")
        logger.info(f"=" * 80)
        
        return {
            "status": "success",
            "order_id": order_id,
            "total_combinations": len(combinations),
            "analyzed_baskets": len(analyzed_baskets),
            "saved_baskets_main": len(top_baskets),
            "saved_baskets_debug": len(analyzed_baskets),
            "best_basket_id": best['basket_id'],
            "best_total_cost": best['total_cost'],
            "best_loss_and_delivery": best['total_loss_and_delivery'],
            "elapsed_time": total_elapsed,
            "csv_files": self.debug_files if self.debug_mode else None
        }


def optimize_order_debug(order_id: int, db_connection_string: str, top_n: int = 10) -> Dict[str, Any]:
    """
    Функция-обёртка для debug-оптимизации заказа.
    
    Args:
        order_id: ID заказа
        db_connection_string: PostgreSQL connection string
        top_n: Количество лучших корзин для основных таблиц
        
    Returns:
        Dict с результатами + пути к CSV файлам
    """
    with OrderOptimizerDebug(db_connection_string, debug_mode=True) as optimizer:
        return optimizer.optimize_order_debug(order_id, top_n)


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    # Настраиваем логирование
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Загружаем DATABASE_URL
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("ERROR: DATABASE_URL не найден в .env")
        exit(1)
    
    # Получаем order_id из аргументов или используем дефолтный
    import sys
    order_id = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    
    print(f"\n🔍 Запуск DEBUG оптимизации для заказа #{order_id}...\n")
    
    result = optimize_order_debug(order_id, db_url, top_n=10)
    
    if result['status'] == 'success':
        print(f"\n" + "=" * 80)
        print(f"✅ УСПЕХ!")
        print(f"=" * 80)
        print(f"Заказ: #{result['order_id']}")
        print(f"Всего комбинаций: {result['total_combinations']:,}")
        print(f"Лучшая корзина: #{result['best_basket_id']}")
        print(f"Стоимость: {result['best_total_cost']:.2f}₽")
        print(f"Время: {result['elapsed_time']:.2f} сек")
        
        if result.get('csv_files'):
            print(f"\n📁 CSV файлы:")
            for table, filepath in result['csv_files'].items():
                print(f"  {table}:")
                print(f"    {filepath}")
        
        print(f"\n💾 Временные таблицы в БД:")
        print(f"  _basket_combinations")
        print(f"  _basket_delivery_costs")
        print(f"  _basket_analyses")
        print(f"\n" + "=" * 80)