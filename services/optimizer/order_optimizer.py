"""
Оптимизатор заказов - единый модуль для полного анализа.
Все расчёты происходят в памяти, в БД записываются только топ-10 лучших корзин.
"""

import logging
from typing import List, Dict, Any, Tuple
from itertools import product
import psycopg2
from psycopg2.extras import execute_values
import time
import json
import sys
import os

# Настраиваем логирование для оптимизатора
logger = logging.getLogger('order_optimizer')
logger.setLevel(logging.INFO)

# Удаляем существующие обработчики
logger.handlers.clear()

# Создаём директорию для логов если её нет
logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
os.makedirs(logs_dir, exist_ok=True)

# Файловый обработчик
file_handler = logging.FileHandler(
    os.path.join(logs_dir, 'optimizer.log'),
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    '%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Консольный обработчик (опционально)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# ВАЖНО: Предотвращаем передачу логов родительским логгерам (избегаем дублирования)
logger.propagate = False

logger.info("✅ Optimizer logging configured")


class OrderOptimizer:
    """Полный оптимизатор заказа - от генерации комбинаций до выбора лучших корзин"""
    
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
    
    # =========================================================================
    # ЭТАП 1: ГЕНЕРАЦИЯ КОМБИНАЦИЙ (в памяти)
    # =========================================================================
    
    def fetch_fprice_data(self, order_id: int, exclusions: Dict[str, Any] = None) -> Dict[int, List[Dict[str, Any]]]:
        """Получает данные из fprice_optimizer, сгруппированные по order_item_id.

        Args:
            order_id: ID заказа
            exclusions: Словарь с исключениями пользователя:
                - keywords: список ключевых слов категорий для исключения
                - products: список названий продуктов из чёрного списка
        """
        query = """
            SELECT
                id, order_id, lsd_config_id, lsd_name, order_item_id, product_name,
                price, fprice, base_unit, base_quantity, requested_unit, requested_quantity,
                order_item_ids_quantity, order_item_ids_cost, fprice_min, fprice_diff,
                loss, min_order_amount, delivery_cost_model, delivery_fixed_fee
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

        # Применяем фильтрацию исключений если они переданы
        if exclusions:
            grouped = self._apply_exclusions_filter(grouped, exclusions)

        # Логируем статистику
        for order_item_id, variants in sorted(grouped.items()):
            logger.info(f"Товар order_item_id={order_item_id}: {len(variants)} вариантов")

        return grouped

    def _apply_exclusions_filter(self, grouped: Dict[int, List[Dict[str, Any]]],
                                  exclusions: Dict[str, Any]) -> Dict[int, List[Dict[str, Any]]]:
        """Применяет фильтрацию исключений к товарам.

        Args:
            grouped: Данные товаров, сгруппированные по order_item_id
            exclusions: Словарь с исключениями:
                - keywords: список ключевых слов категорий
                - products: список названий продуктов из чёрного списка

        Returns:
            Отфильтрованные данные. Если все варианты товара исключены,
            оставляем первый вариант с предупреждением.
        """
        keywords = [kw.lower() for kw in exclusions.get('keywords', [])]
        products = [p.lower() for p in exclusions.get('products', [])]

        if not keywords and not products:
            return grouped

        logger.info(f"🚫 Применяем фильтр исключений: {len(keywords)} ключевых слов, {len(products)} продуктов")

        filtered_grouped = {}
        excluded_count = 0
        warnings = []

        for order_item_id, variants in grouped.items():
            filtered_variants = []

            for variant in variants:
                product_name = variant['product_name'].lower()

                # Проверяем черный список продуктов
                is_blacklisted = any(p in product_name for p in products)

                # Проверяем ключевые слова категорий
                matches_keyword = any(kw in product_name for kw in keywords)

                if is_blacklisted or matches_keyword:
                    excluded_count += 1
                    logger.debug(f"  ❌ Исключён: {variant['product_name']} (ЛСД: {variant['lsd_name']})")
                else:
                    filtered_variants.append(variant)

            if filtered_variants:
                filtered_grouped[order_item_id] = filtered_variants
            else:
                # ВСЕ варианты исключены - оставляем первый с предупреждением
                filtered_grouped[order_item_id] = variants[:1]
                warning_msg = f"⚠️ Все варианты товара order_item_id={order_item_id} ({variants[0]['product_name']}) исключены, оставлен первый"
                warnings.append(warning_msg)
                logger.warning(warning_msg)

        logger.info(f"🚫 Фильтрация завершена: исключено {excluded_count} вариантов")
        if warnings:
            logger.warning(f"🚫 Предупреждения: {len(warnings)} товаров с полным исключением")

        return filtered_grouped
    
    def generate_combinations_in_memory(self, grouped_data: Dict[int, List[Dict[str, Any]]]) -> List[List[Dict[str, Any]]]:
        """Генерирует все возможные комбинации товаров в памяти."""
        if not grouped_data:
            return []
        
        # Сортируем order_item_id для детерминированного порядка
        sorted_items = sorted(grouped_data.keys())
        
        # Подготавливаем списки вариантов для каждого товара
        variant_lists = [grouped_data[item_id] for item_id in sorted_items]
        
        # Считаем ожидаемое количество комбинаций
        expected_count = 1
        for variants in variant_lists:
            expected_count *= len(variants)
        
        logger.info(f"Генерация {expected_count:,} комбинаций в памяти...")
        start_time = time.time()
        
        # Генерируем комбинации через itertools.product
        combinations = list(product(*variant_lists))
        
        elapsed = time.time() - start_time
        logger.info(f"Сгенерировано {len(combinations):,} комбинаций за {elapsed:.2f} сек")
        
        return combinations
    
    # =========================================================================
    # ЭТАП 2: РАСЧЁТ ДОСТАВКИ (в памяти)
    # =========================================================================
    
    def calculate_delivery_by_model(self, delivery_model: dict, total_cost: float, delivery_fixed_fee: float = 0.0) -> float:
        """Рассчитывает стоимость доставки на основе модели доставки.
        
        Args:
            delivery_model: JSON модель доставки
            total_cost: Общая стоимость товаров
            delivery_fixed_fee: Фиксированная доплата за доставку
        
        Returns:
            Стоимость доставки (базовая + фиксированная доплата)
        """
        if not delivery_model or 'delivery_cost' not in delivery_model:
            return float(delivery_fixed_fee)  # Только фиксированная доплата
        
        delivery_ranges = delivery_model.get('delivery_cost', [])
        
        for range_item in sorted(delivery_ranges, key=lambda x: x.get('min', 0)):
            min_amount = range_item.get('min', 0) or 0
            max_amount = range_item.get('max')
            delivery_fee = range_item.get('fee', 0)
            
            if total_cost >= min_amount:
                if max_amount is None or total_cost < max_amount:
                    base_delivery_cost = float(delivery_fee)
                    total_delivery_cost = base_delivery_cost + float(delivery_fixed_fee)
                    return total_delivery_cost
        
        # Если не нашли подходящий диапазон, возвращаем только фиксированную доплату
        return float(delivery_fixed_fee)
    
    def calculate_delivery_for_basket(self, basket: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Рассчитывает стоимость доставки для одной корзины."""
        # Группируем по lsd_config_id
        lsd_groups = {}
        for item in basket:
            lsd_id = item['lsd_config_id']
            if lsd_id not in lsd_groups:
                lsd_groups[lsd_id] = {
                    'lsd_name': item['lsd_name'],
                    'items': [],
                    'total_cost': 0.0,
                    'delivery_model': item['delivery_cost_model'],
                    'min_order_amount': float(item['min_order_amount'] or 0),
                    'delivery_fixed_fee': float(item['delivery_fixed_fee'] or 0)
                }
            lsd_groups[lsd_id]['items'].append(item)
            lsd_groups[lsd_id]['total_cost'] += float(item['order_item_ids_cost'] or 0)
        
        # Рассчитываем доставку для каждого ЛСД
        delivery_info = {}
        for lsd_id, group in lsd_groups.items():
            delivery_cost = self.calculate_delivery_by_model(
                group['delivery_model'], 
                group['total_cost'],
                group['delivery_fixed_fee']
            )
            
            topup = 0.0
            if group['min_order_amount'] > 0 and group['total_cost'] < group['min_order_amount']:
                topup = group['min_order_amount'] - group['total_cost']
            
            delivery_info[lsd_id] = {
                'lsd_name': group['lsd_name'],
                'lsd_total_basket_cost': group['total_cost'],
                'delivery_cost': delivery_cost,
                'topup': topup,
                'min_order_amount': group['min_order_amount']
            }
        
        return delivery_info
    
    # =========================================================================
    # ЭТАП 3: АНАЛИЗ КОРЗИН (в памяти)
    # =========================================================================
    
    def analyze_basket(self, basket_id: int, basket: List[Dict[str, Any]], 
                      delivery_info: Dict[int, Dict[str, Any]], order_id: int) -> Dict[str, Any]:
        """Анализирует одну корзину и возвращает все метрики."""
        # Группируем по ЛСД для JSON структур
        lsd_groups = {}
        for item in basket:
            lsd_name = item['lsd_name']
            if lsd_name not in lsd_groups:
                lsd_groups[lsd_name] = []
            lsd_groups[lsd_name].append(item)
        
        # Рассчитываем метрики
        total_loss = sum(float(item['loss'] or 0) for item in basket)
        total_goods_cost = sum(float(item['order_item_ids_cost'] or 0) for item in basket)
        
        # Собираем delivery_cost и delivery_topup по ЛСД
        delivery_cost_dict = {}
        delivery_topup_dict = {}
        total_delivery_cost = 0.0
        
        for lsd_id, info in delivery_info.items():
            lsd_name = info['lsd_name']
            delivery_cost_dict[lsd_name] = info['delivery_cost']
            delivery_topup_dict[lsd_name] = info['topup']
            total_delivery_cost += info['delivery_cost']
        
        total_cost = total_goods_cost + total_delivery_cost
        total_loss_and_delivery = total_loss + total_delivery_cost
        
        return {
            'basket_id': basket_id,
            'order_id': order_id,
            'basket_items': basket,
            'delivery_info': delivery_info,
            'total_loss': total_loss,
            'total_goods_cost': total_goods_cost,
            'delivery_cost_json': delivery_cost_dict,
            'delivery_topup_json': delivery_topup_dict,
            'total_delivery_cost': total_delivery_cost,
            'total_cost': total_cost,
            'total_loss_and_delivery': total_loss_and_delivery
        }
    
    def analyze_all_baskets(self, combinations: List[List[Dict[str, Any]]], 
                           order_id: int) -> List[Dict[str, Any]]:
        """Анализирует все корзины и возвращает отсортированный список."""
        logger.info(f"Анализ {len(combinations):,} корзин...")
        start_time = time.time()
        
        analyzed_baskets = []
        
        for basket_id, basket in enumerate(combinations, start=1):
            # Рассчитываем доставку
            delivery_info = self.calculate_delivery_for_basket(basket)
            
            # Анализируем корзину
            analysis = self.analyze_basket(basket_id, basket, delivery_info, order_id)
            analyzed_baskets.append(analysis)
            
            # Логируем прогресс каждые 50k корзин
            if basket_id % 50000 == 0:
                logger.info(f"  Проанализировано {basket_id:,} / {len(combinations):,} корзин...")
        
        # Сортируем по total_loss_and_delivery (лучшие первыми)
        analyzed_baskets.sort(key=lambda x: (x['total_loss_and_delivery'], x['total_cost']))
        
        elapsed = time.time() - start_time
        logger.info(f"Анализ завершён за {elapsed:.2f} сек ({len(combinations)/elapsed:.0f} корзин/сек)")
        
        # Логируем топ-3
        for i, basket in enumerate(analyzed_baskets[:3], start=1):
            logger.info(f"  #{i}: basket_id={basket['basket_id']}, "
                       f"потери+доставка={basket['total_loss_and_delivery']:.2f}₽, "
                       f"итого={basket['total_cost']:.2f}₽")
        
        return analyzed_baskets
    
    # =========================================================================
    # ЭТАП 3.5: ОТБОР ОПТИМАЛЬНЫХ КОРЗИН (НОВАЯ ЛОГИКА)
    # =========================================================================
    
    def _select_optimal_baskets(self, analyzed_baskets: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Отбирает оптимальные корзины по новой логике:
        1. Лучшая корзина (rank=1) - минимальный total_loss_and_delivery
        2. Если лучшая НЕ моно-корзина:
           - Для каждого ЛСД из лучшей корзины ищем его моно-корзину
        3. Если лучшая УЖЕ моно-корзина:
           - Ищем ДВА других ЛСД с лучшими моно-корзинами
        
        Args:
            analyzed_baskets: Все корзины, отсортированные по total_loss_and_delivery
            
        Returns:
            Tuple из:
            - List[Dict]: Отобранные корзины для сохранения
            - List[str]: ЛСД из лучшей корзины, для которых не нашлось моно-корзин
        """
        if not analyzed_baskets:
            return [], []
        
        # 1. Лучшая корзина
        best_basket = analyzed_baskets[0]
        
        # 2. Определяем уникальные ЛСД в лучшей корзине
        unique_lsds_in_best = set(item['lsd_name'] for item in best_basket['basket_items'])
        is_mono_best = (len(unique_lsds_in_best) == 1)
        
        # 3. Формируем список топ-корзин
        top_baskets = [best_basket]  # rank=1
        missing_mono_lsds = []  # ЛСД без моно-корзин
        
        if not is_mono_best:
            # СЛУЧАЙ A: Лучшая корзина содержит несколько ЛСД
            logger.info(f"Лучшая корзина содержит {len(unique_lsds_in_best)} ЛСД: {', '.join(sorted(unique_lsds_in_best))}")
            
            # Для каждого ЛСД ищем моно-корзину
            for lsd_name in sorted(unique_lsds_in_best):
                # Фильтруем моно-корзины этого ЛСД (все товары только из этого ЛСД)
                mono_candidates = [
                    basket for basket in analyzed_baskets
                    if len(set(item['lsd_name'] for item in basket['basket_items'])) == 1
                    and all(item['lsd_name'] == lsd_name for item in basket['basket_items'])
                ]
                
                if mono_candidates:
                    # Берём с минимальным total_loss_and_delivery (уже отсортировано)
                    mono_basket = mono_candidates[0]
                    top_baskets.append(mono_basket)
                    
                    diff = mono_basket['total_loss_and_delivery'] - best_basket['total_loss_and_delivery']
                    logger.info(f"  ✓ Моно-корзина {lsd_name}: "
                               f"total_loss_and_delivery={mono_basket['total_loss_and_delivery']:.2f}₽ "
                               f"(+{diff:.2f}₽)")
                else:
                    logger.info(f"  ✗ Моно-корзина {lsd_name}: не найдена, пропускаем")
                    missing_mono_lsds.append(lsd_name)
        
        else:
            # СЛУЧАЙ B: Лучшая корзина уже моно-корзина
            best_lsd = list(unique_lsds_in_best)[0]
            logger.info(f"Лучшая корзина уже моно-корзина: {best_lsd}")
            
            # Собираем все моно-корзины ДРУГИХ ЛСД
            other_mono_baskets = {}  # {lsd_name: best_basket_for_this_lsd}
            
            for basket in analyzed_baskets:
                basket_lsds = set(item['lsd_name'] for item in basket['basket_items'])
                
                # Проверяем: это моно-корзина И это НЕ best_lsd
                if len(basket_lsds) == 1:
                    lsd_name = list(basket_lsds)[0]
                    
                    if lsd_name != best_lsd:
                        # Сохраняем только лучшую для каждого ЛСД
                        if lsd_name not in other_mono_baskets:
                            other_mono_baskets[lsd_name] = basket
                        elif basket['total_loss_and_delivery'] < other_mono_baskets[lsd_name]['total_loss_and_delivery']:
                            other_mono_baskets[lsd_name] = basket
            
            # Сортируем по total_loss_and_delivery и берём первые 2
            sorted_other_mono = sorted(
                other_mono_baskets.items(),
                key=lambda x: x[1]['total_loss_and_delivery']
            )[:2]
            
            for lsd_name, mono_basket in sorted_other_mono:
                top_baskets.append(mono_basket)
                diff = mono_basket['total_loss_and_delivery'] - best_basket['total_loss_and_delivery']
                logger.info(f"  ✓ Альтернативная моно-корзина {lsd_name}: "
                           f"total_loss_and_delivery={mono_basket['total_loss_and_delivery']:.2f}₽ "
                           f"(+{diff:.2f}₽)")
            
            if len(sorted_other_mono) == 0:
                logger.info("  ℹ️  Альтернативных моно-корзин не найдено")
        
        logger.info(f"Всего корзин для сохранения: {len(top_baskets)}")
        if missing_mono_lsds:
            logger.warning(f"⚠️  ЛСД без моно-корзин: {', '.join(missing_mono_lsds)}")
        
        return top_baskets, missing_mono_lsds
    
    # =========================================================================
    # ЭТАП 4: ЗАПИСЬ В БД
    # =========================================================================
    
    def save_top_baskets_to_db(self, top_baskets: List[Dict[str, Any]], order_id: int):
        """Записывает топ-N корзин в БД."""
        logger.info(f"Запись топ-{len(top_baskets)} корзин в БД...")
        start_time = time.time()
        
        # Удаляем старые данные
        with self.conn.cursor() as cur:
            # ВАЖНО: Сначала basket_delivery_costs
            cur.execute("""
                DELETE FROM basket_delivery_costs 
                WHERE order_id = %s
            """, (order_id,))
            deleted_bdc = cur.rowcount
            
            # Затем basket_combinations
            cur.execute("DELETE FROM basket_combinations WHERE order_id = %s", (order_id,))
            deleted_bc = cur.rowcount
            
            # И basket_analyses
            cur.execute("DELETE FROM basket_analyses WHERE order_id = %s", (order_id,))
            deleted_ba = cur.rowcount
            
            logger.info(f"Удалено старых записей: basket_delivery_costs={deleted_bdc}, "
                       f"basket_combinations={deleted_bc}, basket_analyses={deleted_ba}")
        
        # Подготавливаем данные для вставки
        bc_rows = []
        bdc_rows = []
        ba_rows = []
        
        for basket in top_baskets:
            basket_id = basket['basket_id']
            
            # basket_combinations - разворачиваем все товары
            for item in basket['basket_items']:
                lsd_stock_id = item['id']  # id из fprice_optimizer = lsd_stocks.id
                fprice_optimizer_id = item['id']
                
                # Логируем для первой корзины
                if basket_id == basket['basket_id'] and len(bc_rows) < 3:
                    logger.info(f"  Товар: {item['product_name']}, lsd_stock_id={lsd_stock_id}, fprice_opt_id={fprice_optimizer_id}")
                
                bc_rows.append((
                    basket_id, item['id'], order_id, item['order_item_id'],
                    item['product_name'], item['lsd_name'], item['base_unit'],
                    item['base_quantity'], item['price'], item['fprice'],
                    item['fprice_min'], item['fprice_diff'], item['loss'],
                    item['order_item_ids_quantity'], item['min_order_amount'],
                    item['lsd_config_id'], json.dumps(item['delivery_cost_model']),
                    item['order_item_ids_cost'], fprice_optimizer_id, lsd_stock_id
                ))
            
            # basket_delivery_costs - по ЛСД
            for lsd_id, info in basket['delivery_info'].items():
                bdc_rows.append((
                    order_id, basket_id, lsd_id, info['delivery_cost'], info['topup'],
                    info['lsd_total_basket_cost'], info['min_order_amount']
                ))
            
            # basket_analyses - одна строка на корзину
            ba_rows.append((
                order_id, basket_id, basket['total_loss'], basket['total_goods_cost'],
                json.dumps(basket['delivery_cost_json']),
                json.dumps(basket['delivery_topup_json']),
                basket['total_delivery_cost'], basket['total_cost'],
                basket['total_loss_and_delivery'],
                basket['rank']  # НОВОЕ: добавляем ранг корзины
            ))
        
        # Вставляем данные
        with self.conn.cursor() as cur:
            # basket_combinations
            execute_values(cur, """
                INSERT INTO basket_combinations (
                    basket_id, id, order_id, order_item_id, product_name, lsd_name,
                    base_unit, base_quantity, price, fprice, fprice_min, fprice_diff,
                    loss, order_item_ids_quantity, min_order_amount, lsd_config_id,
                    delivery_cost_model, order_item_ids_cost, fprice_optimizer_id, lsd_stock_id
                ) VALUES %s
            """, bc_rows)
            logger.info(f"  Записано {len(bc_rows)} строк в basket_combinations")
            
            # Проверяем что записалось
            cur.execute("""
                SELECT basket_id, product_name, fprice_optimizer_id, lsd_stock_id 
                FROM basket_combinations 
                WHERE order_id = %s 
                LIMIT 3
            """, (order_id,))
            sample_rows = cur.fetchall()
            logger.info(f"  Примеры записанных строк:")
            for row in sample_rows:
                logger.info(f"    basket_id={row[0]}, product={row[1]}, fprice_opt={row[2]}, lsd_stock={row[3]}")
            
            # basket_delivery_costs
            execute_values(cur, """
                INSERT INTO basket_delivery_costs (
                    order_id, basket_id, lsd_config_id, delivery_cost, topup,
                    lsd_total_basket_cost, min_order_amount
                ) VALUES %s
                ON CONFLICT (order_id, basket_id, lsd_config_id) 
                DO UPDATE SET
                    delivery_cost = EXCLUDED.delivery_cost,
                    topup = EXCLUDED.topup,
                    lsd_total_basket_cost = EXCLUDED.lsd_total_basket_cost,
                    min_order_amount = EXCLUDED.min_order_amount
            """, bdc_rows)
            logger.info(f"  Записано {len(bdc_rows)} строк в basket_delivery_costs")
            
            # basket_analyses
            execute_values(cur, """
                INSERT INTO basket_analyses (
                    order_id, basket_id, total_loss, total_goods_cost,
                    delivery_cost, delivery_topup, total_delivery_cost,
                    total_cost, total_loss_and_delivery, basket_rank
                ) VALUES %s
            """, ba_rows)
            logger.info(f"  Записано {len(ba_rows)} строк в basket_analyses")
        
        self.conn.commit()
        
        elapsed = time.time() - start_time
        logger.info(f"Запись в БД завершена за {elapsed:.2f} сек")
    
    # =========================================================================
    # ГЛАВНАЯ ФУНКЦИЯ
    # =========================================================================
    
    def optimize_order(self, order_id: int, top_n: int = 10, exclusions: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Полная оптимизация заказа: генерация комбинаций → расчёт доставки →
        анализ → запись оптимальных корзин в БД.

        Args:
            order_id: ID заказа
            top_n: Параметр более не используется (оставлен для обратной совместимости)
            exclusions: Словарь с исключениями пользователя:
                - keywords: список ключевых слов категорий для исключения
                - products: список названий продуктов из чёрного списка

        Returns:
            Dict с результатами оптимизации
        """
        total_start = time.time()

        logger.info(f"=" * 80)
        logger.info(f"ОПТИМИЗАЦИЯ ЗАКАЗА #{order_id}")
        if exclusions:
            logger.info(f"🚫 С исключениями: {len(exclusions.get('keywords', []))} ключевых слов, {len(exclusions.get('products', []))} продуктов")
        logger.info(f"=" * 80)

        # Этап 1: Получаем данные и генерируем комбинации (с учётом исключений)
        logger.info("\n[1/4] Генерация комбинаций...")
        grouped_data = self.fetch_fprice_data(order_id, exclusions=exclusions)
        if not grouped_data:
            return {"status": "no_data", "elapsed_time": 0}
        
        combinations = self.generate_combinations_in_memory(grouped_data)
        
        # Этап 2-3: Анализ всех корзин (включая расчёт доставки)
        logger.info("\n[2/4] Расчёт доставки и анализ корзин...")
        analyzed_baskets = self.analyze_all_baskets(combinations, order_id)
        
        # Этап 4: Отбираем оптимальные корзины по новой логике
        logger.info(f"\n[3/4] Отбор оптимальных корзин...")
        top_baskets, missing_mono_lsds = self._select_optimal_baskets(analyzed_baskets)
        
        # Присваиваем ранги
        for rank, basket in enumerate(top_baskets, start=1):
            basket['rank'] = rank
        
        logger.info(f"\n[4/4] Запись {len(top_baskets)} корзин в БД...")
        self.save_top_baskets_to_db(top_baskets, order_id)
        
        total_elapsed = time.time() - total_start
        
        # Итоговая статистика
        best = top_baskets[0]
        logger.info(f"\n" + "=" * 80)
        logger.info(f"ОПТИМИЗАЦИЯ ЗАВЕРШЕНА")
        logger.info(f"=" * 80)
        logger.info(f"Всего комбинаций: {len(combinations):,}")
        logger.info(f"Сохранено в БД: {len(top_baskets)} корзин")
        logger.info(f"Лучшая корзина: #{best['basket_id']}")
        logger.info(f"  - Потери + доставка: {best['total_loss_and_delivery']:.2f}₽")
        logger.info(f"  - Итого: {best['total_cost']:.2f}₽")
        if missing_mono_lsds:
            logger.info(f"  - ЛСД без моно-корзин: {', '.join(missing_mono_lsds)}")
        logger.info(f"Время выполнения: {total_elapsed:.2f} сек")
        logger.info(f"=" * 80)
        
        return {
            "status": "success",
            "order_id": order_id,
            "total_combinations": len(combinations),
            "saved_baskets": len(top_baskets),
            "best_basket_id": best['basket_id'],
            "best_total_cost": best['total_cost'],
            "best_loss_and_delivery": best['total_loss_and_delivery'],
            "elapsed_time": total_elapsed,
            "missing_mono_lsds": missing_mono_lsds  # НОВОЕ: список ЛСД без моно-корзин
        }


def optimize_order(order_id: int, db_connection_string: str, top_n: int = 10, exclusions: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Удобная функция-обёртка для оптимизации заказа.

    Args:
        order_id: ID заказа
        db_connection_string: PostgreSQL connection string
        top_n: Количество лучших корзин для сохранения (по умолчанию 10)
        exclusions: Словарь с исключениями пользователя (keywords, products)

    Returns:
        Dict с результатами оптимизации
    """
    with OrderOptimizer(db_connection_string) as optimizer:
        return optimizer.optimize_order(order_id, top_n, exclusions=exclusions)


if __name__ == "__main__":
    # Пример использования
    import os
    from dotenv import load_dotenv
    
    # Настраиваем логирование
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Загружаем DATABASE_URL из .env
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("ERROR: DATABASE_URL не найден в .env")
        exit(1)
    
    # Оптимизируем заказ #16, сохраняем топ-10
    result = optimize_order(16, db_url, top_n=10)
    
    if result['status'] == 'success':
        print(f"\n✅ Заказ #{result['order_id']} успешно оптимизирован!")
        print(f"   Лучшая корзина: #{result['best_basket_id']}")
        print(f"   Стоимость: {result['best_total_cost']:.2f}₽")
        print(f"   Время: {result['elapsed_time']:.2f} сек")
