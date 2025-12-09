"""
Оптимизатор заказов с полной NumPy векторизацией.
Все вычисления происходят через векторные операции NumPy для максимальной производительности.
"""

import logging
import sys
import os
import time
import json
import gc
from typing import List, Dict, Any, Tuple
import psycopg2
from psycopg2.extras import execute_values
import numpy as np

# Настраиваем логирование
logger = logging.getLogger('order_optimizer_numpy')
logger.setLevel(logging.INFO)
logger.handlers.clear()

# Создаём директорию для логов
logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
os.makedirs(logs_dir, exist_ok=True)

# Файловый обработчик
file_handler = logging.FileHandler(
    os.path.join(logs_dir, 'optimizer_numpy.log'),
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    '%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Консольный обработчик
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

logger.propagate = False

logger.info("✅ NumPy Optimizer logging configured")


class OrderOptimizerNumPy:
    """Оптимизатор заказов с полной векторизацией через NumPy"""
    
    def __init__(self, db_connection_string: str):
        self.db_connection_string = db_connection_string
        self.conn = None
        
    def __enter__(self):
        self.conn = psycopg2.connect(self.db_connection_string)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
    
    # =========================================================================
    # ЭТАП 1: ЗАГРУЗКА ДАННЫХ В NUMPY ФОРМАТ
    # =========================================================================
    
    def load_fprice_data_to_numpy(self, order_id: int, exclusions: dict = None) -> Dict[str, Any]:
        """
        Загружает данные из fprice_optimizer и преобразует в NumPy структуры.

        Args:
            order_id: ID заказа
            exclusions: Словарь с исключениями пользователя:
                - keywords: список ключевых слов для исключения
                - products: список названий продуктов из чёрного списка

        Returns:
            Dict с NumPy массивами и метаданными
        """
        logger.info("Загрузка данных из fprice_optimizer...")
        start_time = time.time()
        
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
            return None
        
        # Группируем по order_item_id
        grouped = {}
        for row in rows:
            row_dict = dict(zip(columns, row))
            order_item_id = row_dict['order_item_id']

            if order_item_id not in grouped:
                grouped[order_item_id] = []
            grouped[order_item_id].append(row_dict)

        # Применяем фильтрацию по исключениям пользователя
        if exclusions:
            grouped = self._apply_exclusions_filter(grouped, exclusions)

        # Сортируем order_item_ids для детерминированного порядка
        sorted_items = sorted(grouped.keys())
        n_items = len(sorted_items)
        n_variants = [len(grouped[item_id]) for item_id in sorted_items]
        
        logger.info(f"Товаров: {n_items}, варианты: {n_variants}")
        
        # Создаём плоские массивы
        all_variants = []
        for item_id in sorted_items:
            all_variants.extend(grouped[item_id])
        
        n_total_variants = len(all_variants)
        
        # Извлекаем данные в NumPy массивы
        losses = np.array([float(v['loss'] or 0) for v in all_variants], dtype=np.float32)
        costs = np.array([float(v['order_item_ids_cost'] or 0) for v in all_variants], dtype=np.float32)
        lsd_config_ids = np.array([v['lsd_config_id'] for v in all_variants], dtype=np.int32)
        fprice_ids = np.array([v['id'] for v in all_variants], dtype=np.int32)
        min_order_amounts = np.array([float(v['min_order_amount'] or 0) for v in all_variants], dtype=np.float32)
        delivery_fixed_fees = np.array([float(v['delivery_fixed_fee'] or 0) for v in all_variants], dtype=np.float32)
        
        # Индексы начала каждого товара
        item_offsets = [0]
        for count in n_variants:
            item_offsets.append(item_offsets[-1] + count)
        
        # Считаем количество комбинаций
        n_combinations = np.prod(n_variants, dtype=np.int64)
        
        elapsed = time.time() - start_time
        logger.info(f"Данные загружены за {elapsed:.2f} сек")
        logger.info(f"  Всего вариантов: {n_total_variants}")
        logger.info(f"  Ожидается комбинаций: {n_combinations:,}")
        logger.info(f"  Размер losses: {losses.nbytes / 1024:.1f} KB")
        logger.info(f"  Размер costs: {costs.nbytes / 1024:.1f} KB")
        
        return {
            'order_id': order_id,
            'n_items': n_items,
            'n_variants': n_variants,
            'n_combinations': int(n_combinations),
            'sorted_items': sorted_items,
            'losses': losses,
            'costs': costs,
            'lsd_config_ids': lsd_config_ids,
            'fprice_ids': fprice_ids,
            'min_order_amounts': min_order_amounts,
            'delivery_fixed_fees': delivery_fixed_fees,
            'item_offsets': item_offsets,
            'variant_metadata': all_variants  # Полные данные для финальной записи
        }

    def _apply_exclusions_filter(self, grouped: dict, exclusions: dict) -> dict:
        """
        Фильтрует варианты товаров по исключениям пользователя.

        Args:
            grouped: Словарь {order_item_id: [варианты]}
            exclusions: Словарь с исключениями:
                - keywords: список ключевых слов категорий
                - products: список названий продуктов из чёрного списка

        Returns:
            Отфильтрованный словарь grouped
        """
        keywords = [kw.lower() for kw in exclusions.get('keywords', [])]
        products = [p.lower() for p in exclusions.get('products', [])]

        if not keywords and not products:
            return grouped

        logger.info(f"🚫 Применение исключений: {len(keywords)} ключевых слов, {len(products)} продуктов")

        filtered_grouped = {}
        excluded_count = 0

        for order_item_id, variants in grouped.items():
            filtered_variants = []

            for variant in variants:
                product_name = variant.get('product_name', '').lower()
                is_excluded = False

                # Проверка по ключевым словам категорий
                for keyword in keywords:
                    if keyword in product_name:
                        is_excluded = True
                        break

                # Проверка по черному списку продуктов
                if not is_excluded:
                    for product in products:
                        if product in product_name:
                            is_excluded = True
                            break

                if not is_excluded:
                    filtered_variants.append(variant)
                else:
                    excluded_count += 1

            if filtered_variants:
                filtered_grouped[order_item_id] = filtered_variants
            else:
                # Если все варианты исключены — оставляем первый с предупреждением
                logger.warning(f"⚠️ Все варианты товара {order_item_id} исключены! "
                             f"Оставляем первый вариант: {variants[0].get('product_name', 'N/A')}")
                filtered_grouped[order_item_id] = [variants[0]]

        logger.info(f"🚫 Исключено вариантов: {excluded_count}")

        return filtered_grouped

    # =========================================================================
    # ЭТАП 2: ГЕНЕРАЦИЯ ИНДЕКСНОЙ МАТРИЦЫ КОМБИНАЦИЙ
    # =========================================================================
    
    def generate_combination_indices(self, n_variants: List[int]) -> np.ndarray:
        """
        Генерирует матрицу индексов комбинаций.
        
        Args:
            n_variants: Список количества вариантов для каждого товара
            
        Returns:
            np.ndarray shape (n_combinations, n_items) dtype=int32
        """
        logger.info("Генерация индексной матрицы комбинаций...")
        start_time = time.time()
        
        n_items = len(n_variants)
        n_combinations = np.prod(n_variants, dtype=np.int64)
        
        # Оценка памяти
        memory_mb = (n_combinations * n_items * 4) / (1024 * 1024)
        logger.info(f"  Ожидаемый размер матрицы: {memory_mb:.1f} MB")
        
        # Генерируем индексы через meshgrid подход
        # Для каждого товара создаём массив индексов, который повторяется нужное кол-во раз
        indices = np.zeros((int(n_combinations), n_items), dtype=np.int32)
        
        # Количество повторений для каждого товара
        repeat_counts = np.ones(n_items, dtype=np.int64)
        for i in range(n_items - 1, 0, -1):
            repeat_counts[i - 1] = repeat_counts[i] * n_variants[i]
        
        # Tile counts (сколько раз повторить весь блок)
        tile_counts = np.ones(n_items, dtype=np.int64)
        for i in range(1, n_items):
            tile_counts[i] = tile_counts[i - 1] * n_variants[i - 1]
        
        # Заполняем матрицу
        for item_idx in range(n_items):
            n_var = n_variants[item_idx]
            repeat_count = int(repeat_counts[item_idx])
            tile_count = int(tile_counts[item_idx])
            
            # Создаём базовый паттерн [0, 0, ..., 1, 1, ..., 2, 2, ...]
            pattern = np.repeat(np.arange(n_var, dtype=np.int32), repeat_count)
            
            # Тайлим его tile_count раз
            indices[:, item_idx] = np.tile(pattern, tile_count)
        
        elapsed = time.time() - start_time
        actual_memory_mb = indices.nbytes / (1024 * 1024)
        logger.info(f"Матрица сгенерирована за {elapsed:.2f} сек")
        logger.info(f"  Размер: {indices.shape}")
        logger.info(f"  Память: {actual_memory_mb:.1f} MB")
        
        return indices
    
    # =========================================================================
    # ЭТАП 3: ВЕКТОРИЗОВАННЫЙ РАСЧЁТ БАЗОВЫХ МЕТРИК
    # =========================================================================
    
    def calculate_basic_metrics(self, combo_indices: np.ndarray, data: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Векторно рассчитывает total_loss и total_goods_cost для всех комбинаций.
        
        Args:
            combo_indices: Матрица индексов комбинаций (n_combinations, n_items)
            data: Словарь с NumPy массивами данных
            
        Returns:
            (total_losses, total_costs) - массивы shape (n_combinations,)
        """
        logger.info("Векторный расчёт базовых метрик...")
        start_time = time.time()
        
        n_combinations = combo_indices.shape[0]
        n_items = combo_indices.shape[1]
        item_offsets = data['item_offsets']
        losses = data['losses']
        costs = data['costs']
        
        # Преобразуем локальные индексы в глобальные
        # combo_indices содержит локальные индексы (0, 1, 2, ... для каждого товара)
        # Нужно добавить item_offsets для получения глобальных индексов
        global_indices = combo_indices.copy()
        for item_idx in range(n_items):
            global_indices[:, item_idx] += item_offsets[item_idx]
        
        # Извлекаем данные для всех комбинаций
        combo_losses = losses[global_indices]  # shape: (n_combinations, n_items)
        combo_costs = costs[global_indices]
        
        # Суммируем по товарам (axis=1)
        total_losses = combo_losses.sum(axis=1)  # shape: (n_combinations,)
        total_costs = combo_costs.sum(axis=1)
        
        elapsed = time.time() - start_time
        logger.info(f"Базовые метрики рассчитаны за {elapsed:.2f} сек ({n_combinations/elapsed:,.0f} корзин/сек)")
        logger.info(f"  total_losses: min={total_losses.min():.2f}, max={total_losses.max():.2f}")
        logger.info(f"  total_costs: min={total_costs.min():.2f}, max={total_costs.max():.2f}")
        
        return total_losses, total_costs
    
    # =========================================================================
    # ЭТАП 4: ПРЕДВАРИТЕЛЬНАЯ ФИЛЬТРАЦИЯ
    # =========================================================================
    
    def prefilter_combinations(self, combo_indices: np.ndarray, total_losses: np.ndarray, 
                              total_costs: np.ndarray, top_k: int = 100000) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Отбирает топ-K комбинаций по total_loss для дальнейшего анализа.
        
        Args:
            combo_indices: Матрица индексов
            total_losses: Массив потерь
            total_costs: Массив стоимостей
            top_k: Количество лучших комбинаций для отбора
            
        Returns:
            (filtered_indices, filtered_losses, filtered_costs)
        """
        logger.info(f"Предварительная фильтрация: отбор топ-{top_k:,} комбинаций по losses...")
        start_time = time.time()
        
        # Частичная сортировка - находим индексы топ-K с минимальными потерями
        top_indices = np.argpartition(total_losses, top_k)[:top_k]
        
        # Сортируем топ-K по losses
        sorted_order = np.argsort(total_losses[top_indices])
        top_indices = top_indices[sorted_order]
        
        filtered_indices = combo_indices[top_indices]
        filtered_losses = total_losses[top_indices]
        filtered_costs = total_costs[top_indices]
        
        elapsed = time.time() - start_time
        logger.info(f"Фильтрация завершена за {elapsed:.2f} сек")
        logger.info(f"  Отобрано: {len(top_indices):,} комбинаций")
        logger.info(f"  Лучшая loss: {filtered_losses[0]:.2f}₽")
        logger.info(f"  Худшая loss в топе: {filtered_losses[-1]:.2f}₽")
        
        return filtered_indices, filtered_losses, filtered_costs
    
    # =========================================================================
    # ЭТАП 5: РАСЧЁТ ДОСТАВКИ (ПОЛНАЯ ВЕКТОРИЗАЦИЯ)
    # =========================================================================

    def _prepare_delivery_lookups(self, data: Dict[str, Any]) -> Dict[int, Dict[str, np.ndarray]]:
        """
        Предрассчитывает lookup-таблицы для диапазонов доставки каждого ЛСД.

        Returns:
            Dict[lsd_id] -> {
                'mins': np.array([0, 500, 1200, ...]),
                'maxs': np.array([500, 1200, inf, ...]),
                'fees': np.array([500, 99, 0, ...])
            }
        """
        logger.info("  Подготовка lookup-таблиц для диапазонов доставки...")

        lsd_config_ids = data['lsd_config_ids']
        variant_metadata = data['variant_metadata']

        unique_lsd_ids = np.unique(lsd_config_ids)
        delivery_lookups = {}

        for lsd_id in unique_lsd_ids:
            # Находим первый вариант с этим lsd_id
            idx = np.where(lsd_config_ids == lsd_id)[0][0]
            delivery_model = variant_metadata[idx].get('delivery_cost_model', {})

            if not delivery_model or 'delivery_cost' not in delivery_model:
                # Пустая модель - бесплатная доставка
                delivery_lookups[int(lsd_id)] = {
                    'mins': np.array([0.0], dtype=np.float32),
                    'maxs': np.array([np.inf], dtype=np.float32),
                    'fees': np.array([0.0], dtype=np.float32)
                }
                continue

            delivery_ranges = delivery_model.get('delivery_cost', [])
            if not delivery_ranges:
                delivery_lookups[int(lsd_id)] = {
                    'mins': np.array([0.0], dtype=np.float32),
                    'maxs': np.array([np.inf], dtype=np.float32),
                    'fees': np.array([0.0], dtype=np.float32)
                }
                continue

            # Сортируем диапазоны по min
            sorted_ranges = sorted(delivery_ranges, key=lambda x: x.get('min', 0))

            mins = []
            maxs = []
            fees = []

            for range_item in sorted_ranges:
                min_val = float(range_item.get('min', 0) or 0)
                max_val = range_item.get('max')
                fee = float(range_item.get('fee', 0))

                mins.append(min_val)
                maxs.append(float(max_val) if max_val is not None else np.inf)
                fees.append(fee)

            delivery_lookups[int(lsd_id)] = {
                'mins': np.array(mins, dtype=np.float32),
                'maxs': np.array(maxs, dtype=np.float32),
                'fees': np.array(fees, dtype=np.float32)
            }

        logger.info(f"  Подготовлено {len(delivery_lookups)} lookup-таблиц")
        return delivery_lookups

    def calculate_delivery_vectorized_v2(self, combo_indices: np.ndarray, data: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
        """
        ПОЛНОСТЬЮ векторизованный расчёт стоимости доставки для всех комбинаций.
        Использует NumPy маски и np.searchsorted для максимальной производительности.

        Args:
            combo_indices: Матрица индексов комбинаций
            data: Словарь с данными

        Returns:
            (total_delivery_costs, total_topups) - два массива shape (n_combinations,)
        """
        logger.info("Векторный расчёт доставки (v2 - полная векторизация)...")
        start_time = time.time()

        n_combinations = combo_indices.shape[0]
        n_items = combo_indices.shape[1]
        item_offsets = data['item_offsets']
        lsd_config_ids = data['lsd_config_ids']
        costs = data['costs']
        min_order_amounts = data['min_order_amounts']
        delivery_fixed_fees = data['delivery_fixed_fees']

        # Преобразуем в глобальные индексы
        global_indices = combo_indices.copy()
        for item_idx in range(n_items):
            global_indices[:, item_idx] += item_offsets[item_idx]

        # Извлекаем данные для всех комбинаций
        combo_lsd_ids = lsd_config_ids[global_indices]  # shape: (n_combinations, n_items)
        combo_costs = costs[global_indices]
        combo_min_orders = min_order_amounts[global_indices]
        combo_fixed_fees = delivery_fixed_fees[global_indices]

        # Подготавливаем lookup-таблицы
        delivery_lookups = self._prepare_delivery_lookups(data)

        # Результирующие массивы
        total_delivery_costs = np.zeros(n_combinations, dtype=np.float32)
        total_topups = np.zeros(n_combinations, dtype=np.float32)

        # Получаем уникальные ЛСД
        unique_lsd_ids = np.unique(lsd_config_ids)
        logger.info(f"  Обработка {len(unique_lsd_ids)} уникальных ЛСД...")

        # Для каждого ЛСД векторно рассчитываем доставку
        for lsd_id in unique_lsd_ids:
            # Создаём маску: где в комбинации есть товары из этого ЛСД
            lsd_mask = (combo_lsd_ids == lsd_id)  # shape: (n_combinations, n_items)

            # Векторно суммируем стоимость для этого ЛСД в каждой комбинации
            lsd_totals = (combo_costs * lsd_mask).sum(axis=1)  # shape: (n_combinations,)

            # Берём min_order_amount и fixed_fee для этого ЛСД (они одинаковые для всех товаров ЛСД)
            # Находим первый товар этого ЛСД в каждой комбинации
            lsd_item_indices = np.argmax(lsd_mask, axis=1)  # Индекс первого True в каждой строке
            min_order = combo_min_orders[np.arange(n_combinations), lsd_item_indices]
            fixed_fee = combo_fixed_fees[np.arange(n_combinations), lsd_item_indices]

            # Маска: где этот ЛСД действительно присутствует (lsd_totals > 0)
            has_lsd = lsd_totals > 0

            # Рассчитываем топап (векторно)
            topup = np.where(
                has_lsd & (min_order > 0) & (lsd_totals < min_order),
                min_order - lsd_totals,
                0.0
            )

            # Корректируем сумму ПОСЛЕ топапа
            lsd_totals_with_topup = lsd_totals + topup

            # Векторно находим диапазон через np.searchsorted
            lookup = delivery_lookups[int(lsd_id)]

            # searchsorted возвращает индекс первого элемента >= искомого
            # Нам нужен индекс диапазона, в который попадает значение
            # Используем side='right' чтобы получить индекс > значения, потом вычитаем 1
            range_indices = np.searchsorted(lookup['mins'], lsd_totals_with_topup, side='right') - 1
            range_indices = np.clip(range_indices, 0, len(lookup['fees']) - 1)

            # Проверяем, что значение не превышает max диапазона
            # Если превышает - ищем следующий диапазон
            in_range = lsd_totals_with_topup < lookup['maxs'][range_indices]

            # Если не в диапазоне и есть следующий диапазон - берём его
            next_range_available = range_indices < (len(lookup['fees']) - 1)
            range_indices = np.where(~in_range & next_range_available, range_indices + 1, range_indices)

            # Извлекаем fee (векторно)
            base_fees = lookup['fees'][range_indices]

            # Применяем только к тем комбинациям, где есть этот ЛСД
            delivery_cost = np.where(has_lsd, base_fees + fixed_fee, 0.0)

            # Аккумулируем результаты
            total_delivery_costs += delivery_cost
            total_topups += topup

        elapsed = time.time() - start_time
        logger.info(f"Доставка рассчитана за {elapsed:.2f} сек ({n_combinations/elapsed:,.0f} корзин/сек)")
        logger.info(f"  min delivery: {total_delivery_costs.min():.2f}₽")
        logger.info(f"  max delivery: {total_delivery_costs.max():.2f}₽")
        logger.info(f"  min topup: {total_topups.min():.2f}₽")
        logger.info(f"  max topup: {total_topups.max():.2f}₽")

        return total_delivery_costs, total_topups

    # =========================================================================
    # СТАРАЯ ВЕРСИЯ (ОСТАВЛЕНА ДЛЯ СОВМЕСТИМОСТИ)
    # =========================================================================

    def calculate_delivery_vectorized(self, combo_indices: np.ndarray, data: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Рассчитывает стоимость доставки для всех комбинаций.
        Частично векторизованный подход.
        
        Args:
            combo_indices: Матрица индексов комбинаций
            data: Словарь с данными
            
        Returns:
            (total_delivery_costs, total_topups) - два массива shape (n_combinations,)
        """
        logger.info("Расчёт стоимости доставки...")
        start_time = time.time()
        
        n_combinations = combo_indices.shape[0]
        n_items = combo_indices.shape[1]
        item_offsets = data['item_offsets']
        lsd_config_ids = data['lsd_config_ids']
        costs = data['costs']
        min_order_amounts = data['min_order_amounts']
        delivery_fixed_fees = data['delivery_fixed_fees']
        variant_metadata = data['variant_metadata']
        
        # Преобразуем в глобальные индексы
        global_indices = combo_indices.copy()
        for item_idx in range(n_items):
            global_indices[:, item_idx] += item_offsets[item_idx]
        
        # Извлекаем lsd_config_id и стоимость для каждого товара в комбинации
        combo_lsd_ids = lsd_config_ids[global_indices]  # shape: (n_combinations, n_items)
        combo_costs = costs[global_indices]
        combo_min_orders = min_order_amounts[global_indices]
        combo_fixed_fees = delivery_fixed_fees[global_indices]
        
        # Результирующие массивы
        total_delivery_costs = np.zeros(n_combinations, dtype=np.float32)
        total_topups = np.zeros(n_combinations, dtype=np.float32)
        
        # Для каждой комбинации группируем по ЛСД и считаем доставку
        logger.info(f"  Обработка {n_combinations:,} комбинаций...")
        
        # Получаем уникальные ЛСД для подготовки lookup-таблиц
        unique_lsd_ids = np.unique(lsd_config_ids)
        
        # Создаём lookup для моделей доставки
        delivery_models = {}
        for lsd_id in unique_lsd_ids:
            # Находим первый вариант с этим lsd_id
            idx = np.where(lsd_config_ids == lsd_id)[0][0]
            delivery_models[lsd_id] = variant_metadata[idx].get('delivery_cost_model', {})
        
        # Обрабатываем батчами для экономии памяти
        batch_size = 10000
        for batch_start in range(0, n_combinations, batch_size):
            batch_end = min(batch_start + batch_size, n_combinations)
            
            batch_lsd_ids = combo_lsd_ids[batch_start:batch_end]
            batch_costs = combo_costs[batch_start:batch_end]
            batch_min_orders = combo_min_orders[batch_start:batch_end]
            batch_fixed_fees = combo_fixed_fees[batch_start:batch_end]
            
            # Для каждой комбинации в батче
            for i in range(batch_end - batch_start):
                # Группируем по ЛСД
                lsd_groups = {}
                for j in range(n_items):
                    lsd_id = batch_lsd_ids[i, j]
                    if lsd_id not in lsd_groups:
                        lsd_groups[lsd_id] = {
                            'total_cost': 0.0,
                            'min_order': batch_min_orders[i, j],
                            'fixed_fee': batch_fixed_fees[i, j]
                        }
                    lsd_groups[lsd_id]['total_cost'] += batch_costs[i, j]
                
                # Считаем доставку для каждого ЛСД
                delivery_cost = 0.0
                total_topup_for_combo = 0.0
                
                for lsd_id, group in lsd_groups.items():
                    lsd_total = group['total_cost']
                    original_lsd_total = lsd_total  # Сохраняем оригинал
                    min_order = group['min_order']
                    fixed_fee = group['fixed_fee']
                    
                    # Topup если нужно
                    topup = 0.0
                    has_topup = False
                    if min_order > 0 and lsd_total < min_order:
                        topup = min_order - lsd_total
                        lsd_total = min_order  # Корректируем для выбора диапазона
                        has_topup = True
                    
                    # Расчёт по модели (используем скорректированную сумму ПОСЛЕ топапа)
                    model = delivery_models.get(lsd_id, {})
                    base_fee = self._calculate_delivery_by_model(model, lsd_total)

                    # Стоимость доставки (base_fee рассчитан от суммы ПОСЛЕ топапа)
                    total_topup_for_combo += topup
                    delivery_cost += base_fee + fixed_fee
                
                total_delivery_costs[batch_start + i] = delivery_cost
                total_topups[batch_start + i] = total_topup_for_combo
            
            if (batch_end - batch_start) >= batch_size and batch_end % 50000 == 0:
                logger.info(f"    Обработано {batch_end:,} / {n_combinations:,} корзин...")
        
        elapsed = time.time() - start_time
        logger.info(f"Доставка рассчитана за {elapsed:.2f} сек ({n_combinations/elapsed:,.0f} корзин/сек)")
        logger.info(f"  min delivery: {total_delivery_costs.min():.2f}₽")
        logger.info(f"  max delivery: {total_delivery_costs.max():.2f}₽")
        logger.info(f"  min topup: {total_topups.min():.2f}₽")
        logger.info(f"  max topup: {total_topups.max():.2f}₽")
        
        return total_delivery_costs, total_topups
    
    def _calculate_delivery_by_model(self, delivery_model: dict, total_cost: float) -> float:
        """Расчёт базовой стоимости доставки по модели."""
        if not delivery_model or 'delivery_cost' not in delivery_model:
            return 0.0
        
        delivery_ranges = delivery_model.get('delivery_cost', [])
        
        for range_item in sorted(delivery_ranges, key=lambda x: x.get('min', 0)):
            min_amount = range_item.get('min', 0) or 0
            max_amount = range_item.get('max')
            delivery_fee = range_item.get('fee', 0)
            
            if total_cost >= min_amount:
                if max_amount is None or total_cost < max_amount:
                    return float(delivery_fee)
        
        return 0.0
    
    def _get_first_delivery_range(self, delivery_model: dict) -> dict:
        """Возвращает первый диапазон доставки."""
        if not delivery_model or 'delivery_cost' not in delivery_model:
            return None
        
        delivery_ranges = delivery_model.get('delivery_cost', [])
        if not delivery_ranges:
            return None
        
        # Сортируем по min и берем первый
        sorted_ranges = sorted(delivery_ranges, key=lambda x: x.get('min', 0))
        return sorted_ranges[0] if sorted_ranges else None
    
    # =========================================================================
    # ЭТАП 6: ФИНАЛЬНАЯ СОРТИРОВКА И ОТБОР
    # =========================================================================
    
    def select_top_baskets(self, combo_indices: np.ndarray, total_losses: np.ndarray,
                          total_costs: np.ndarray, total_delivery: np.ndarray, total_topup: np.ndarray,
                          data: Dict[str, Any], top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Отбирает топ-N корзин + лучшие моно-корзины для каждого LSD.
        
        Returns:
            Список словарей с полными данными о корзинах
        """
        logger.info(f"Отбор топ-{top_n} корзин + моно-корзины...")
        start_time = time.time()
        
        # Рассчитываем ключевую метрику: loss + topup + delivery
        total_loss_and_delivery = total_losses + total_topup + total_delivery
        
        # ИСПРАВЛЕНО: total_cost = goods + topup + delivery
        total_costs_corrected = total_costs + total_topup + total_delivery
        
        # Сортируем по total_loss_and_delivery, затем по total_cost
        sort_keys = np.lexsort((total_costs_corrected, total_loss_and_delivery))
        
        n_items = data['n_items']
        item_offsets = data['item_offsets']
        variant_metadata = data['variant_metadata']
        lsd_config_ids = data['lsd_config_ids']
        
        # Шаг 1: Отбираем топ-N
        top_indices = sort_keys[:top_n]
        top_baskets = []
        top_basket_ids = set()
        
        for rank, idx in enumerate(top_indices, start=1):
            combo_idx = combo_indices[idx]
            
            # Преобразуем в глобальные индексы и извлекаем полные данные
            basket_items = []
            lsd_ids_in_basket = set()
            
            for item_idx in range(n_items):
                global_idx = combo_idx[item_idx] + item_offsets[item_idx]
                item_data = variant_metadata[global_idx]
                basket_items.append(item_data)
                lsd_ids_in_basket.add(item_data['lsd_config_id'])
            
            is_mono_basket = len(lsd_ids_in_basket) == 1
            
            basket = {
                'basket_id': int(idx) + 1,
                'rank': rank,
                'basket_items': basket_items,
                'total_loss': float(total_losses[idx]),
                'total_goods_cost': float(total_costs[idx]),
                'total_topup': float(total_topup[idx]),
                'total_delivery_cost': float(total_delivery[idx]),
                'total_cost': float(total_costs[idx] + total_topup[idx] + total_delivery[idx]),
                'total_loss_and_delivery': float(total_loss_and_delivery[idx]),
                'is_mono_basket': is_mono_basket,
                'lsd_ids': lsd_ids_in_basket
            }
            
            top_baskets.append(basket)
            top_basket_ids.add(int(idx))
            
            if rank <= 3:
                mono_label = "[МОНО]" if is_mono_basket else "[МУЛЬТИ]"
                logger.info(f"  #{rank} {mono_label}: basket_id={basket['basket_id']}, "
                           f"loss+delivery={basket['total_loss_and_delivery']:.2f}₽, "
                           f"итого={basket['total_cost']:.2f}₽")
        
        # Шаг 2: Добавляем лучшие моно-корзины для каждого LSD
        logger.info(f"\nПоиск лучших моно-корзин для каждого LSD...")
        
        # Находим все уникальные LSD в данных
        unique_lsd_ids = np.unique(lsd_config_ids)
        logger.info(f"Найдено {len(unique_lsd_ids)} уникальных LSD")
        
        # Для каждого LSD ищем лучшую моно-корзину
        mono_baskets_added = []
        next_rank = top_n + 1
        
        for lsd_id in unique_lsd_ids:
            # Ищем лучшую моно-корзину для этого LSD
            # Идём по отсортированным индексам
            best_mono_idx = None
            
            for idx in sort_keys:
                # Пропускаем корзины, которые уже в топ-N
                if int(idx) in top_basket_ids:
                    continue
                
                combo_idx = combo_indices[idx]
                
                # Проверяем, является ли эта корзина моно-корзиной для lsd_id
                lsd_ids_in_basket = set()
                for item_idx in range(n_items):
                    global_idx = combo_idx[item_idx] + item_offsets[item_idx]
                    lsd_ids_in_basket.add(lsd_config_ids[global_idx])
                
                # Если это моно-корзина с нужным LSD - берём её
                if len(lsd_ids_in_basket) == 1 and lsd_id in lsd_ids_in_basket:
                    best_mono_idx = idx
                    break
            
            # Если нашли моно-корзину - добавляем
            if best_mono_idx is not None:
                combo_idx = combo_indices[best_mono_idx]
                basket_items = []
                lsd_ids_in_basket = set()
                
                for item_idx in range(n_items):
                    global_idx = combo_idx[item_idx] + item_offsets[item_idx]
                    item_data = variant_metadata[global_idx]
                    basket_items.append(item_data)
                    lsd_ids_in_basket.add(item_data['lsd_config_id'])
                
                lsd_name = basket_items[0]['lsd_name']
                
                basket = {
                    'basket_id': int(best_mono_idx) + 1,
                    'rank': next_rank,
                    'basket_items': basket_items,
                    'total_loss': float(total_losses[best_mono_idx]),
                    'total_goods_cost': float(total_costs[best_mono_idx]),
                    'total_topup': float(total_topup[best_mono_idx]),
                    'total_delivery_cost': float(total_delivery[best_mono_idx]),
                    'total_cost': float(total_costs[best_mono_idx] + total_topup[best_mono_idx] + total_delivery[best_mono_idx]),
                    'total_loss_and_delivery': float(total_loss_and_delivery[best_mono_idx]),
                    'is_mono_basket': True,
                    'lsd_ids': lsd_ids_in_basket
                }
                
                top_baskets.append(basket)
                top_basket_ids.add(int(best_mono_idx))
                mono_baskets_added.append(lsd_name)
                next_rank += 1
                
                logger.info(f"  ✓ Добавлена моно-корзина {lsd_name}: "
                           f"loss+delivery={basket['total_loss_and_delivery']:.2f}₽, "
                           f"итого={basket['total_cost']:.2f}₽")
        
        # Подсчитываем статистику
        mono_count_in_top = sum(1 for b in top_baskets[:top_n] if b['is_mono_basket'])
        total_mono_count = sum(1 for b in top_baskets if b['is_mono_basket'])
        
        logger.info(f"\nМоно-корзин в топ-{top_n}: {mono_count_in_top}")
        logger.info(f"Добавлено дополнительных моно-корзин: {len(mono_baskets_added)}")
        logger.info(f"Всего корзин для сохранения: {len(top_baskets)} (из них {total_mono_count} моно)")
        
        elapsed = time.time() - start_time
        logger.info(f"Отбор завершён за {elapsed:.2f} сек")
        
        return top_baskets
    
    # =========================================================================
    # ЭТАП 7: ЗАПИСЬ В БД
    # =========================================================================
    
    def save_to_db(self, top_baskets: List[Dict[str, Any]], order_id: int):
        """Записывает топ-корзины в БД."""
        logger.info(f"Запись {len(top_baskets)} корзин в БД...")
        start_time = time.time()
        
        # Удаляем старые данные
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM basket_delivery_costs WHERE order_id = %s", (order_id,))
            deleted_bdc = cur.rowcount
            
            cur.execute("DELETE FROM basket_combinations WHERE order_id = %s", (order_id,))
            deleted_bc = cur.rowcount
            
            cur.execute("DELETE FROM basket_analyses WHERE order_id = %s", (order_id,))
            deleted_ba = cur.rowcount
            
            logger.info(f"Удалено старых записей: bdc={deleted_bdc}, bc={deleted_bc}, ba={deleted_ba}")
        
        # Подготавливаем данные
        bc_rows = []
        bdc_rows = []
        ba_rows = []
        
        for basket in top_baskets:
            basket_id = basket['basket_id']
            
            # Группируем по ЛСД для delivery_costs
            lsd_groups = {}
            for item in basket['basket_items']:
                lsd_id = item['lsd_config_id']
                lsd_name = item['lsd_name']
                
                if lsd_id not in lsd_groups:
                    lsd_groups[lsd_id] = {
                        'lsd_name': lsd_name,
                        'total_cost': 0.0,
                        'min_order': float(item['min_order_amount'] or 0),
                        'fixed_fee': float(item['delivery_fixed_fee'] or 0),
                        'model': item['delivery_cost_model']
                    }
                lsd_groups[lsd_id]['total_cost'] += float(item['order_item_ids_cost'] or 0)
            
            # basket_combinations
            for item in basket['basket_items']:
                bc_rows.append((
                    basket_id, item['id'], order_id, item['order_item_id'],
                    item['product_name'], item['lsd_name'], item['base_unit'],
                    item['base_quantity'], item['price'], item['fprice'],
                    item['fprice_min'], item['fprice_diff'], item['loss'],
                    item['order_item_ids_quantity'], item['min_order_amount'],
                    item['lsd_config_id'], json.dumps(item['delivery_cost_model']),
                    item['order_item_ids_cost'], item['id'], item['id']
                ))
            
            # basket_delivery_costs
            delivery_cost_json = {}
            delivery_topup_json = {}
            total_delivery = 0.0
            
            for lsd_id, group in lsd_groups.items():
                lsd_total = group['total_cost']
                original_lsd_total = lsd_total  # Сохраняем оригинал
                topup = 0.0
                has_topup = False
                
                if group['min_order'] > 0 and lsd_total < group['min_order']:
                    topup = group['min_order'] - lsd_total
                    lsd_total = group['min_order']
                    has_topup = True
                
                # Расчёт доставки от суммы ПОСЛЕ топапа
                base_fee = self._calculate_delivery_by_model(group['model'], lsd_total)

                # Стоимость доставки (base_fee рассчитан от суммы ПОСЛЕ топапа)
                delivery_cost = base_fee + group['fixed_fee']
                
                bdc_rows.append((
                    order_id, basket_id, lsd_id, delivery_cost, topup,
                    group['total_cost'], group['min_order']
                ))
                
                delivery_cost_json[group['lsd_name']] = delivery_cost
                delivery_topup_json[group['lsd_name']] = topup
                total_delivery += delivery_cost  # БЕЗ топапа
            
            # basket_analyses
            # ИСПРАВЛЕНО: total_cost и total_loss_and_delivery должны включать топап
            total_topup = sum(delivery_topup_json.values())
            corrected_total_cost = basket['total_goods_cost'] + total_topup + total_delivery
            corrected_total_loss_and_delivery = basket['total_loss'] + total_topup + total_delivery
            
            ba_rows.append((
                order_id, basket_id, basket['total_loss'], basket['total_goods_cost'],
                json.dumps(delivery_cost_json), json.dumps(delivery_topup_json),
                total_delivery,  # БЕЗ топапа
                corrected_total_cost,  # total_goods_cost + topup + delivery
                corrected_total_loss_and_delivery,  # loss + topup + delivery
                basket['rank'],
                basket.get('is_mono_basket', False)  # Добавляем флаг моно-корзины
            ))
        
        # Вставляем данные
        with self.conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO basket_combinations (
                    basket_id, id, order_id, order_item_id, product_name, lsd_name,
                    base_unit, base_quantity, price, fprice, fprice_min, fprice_diff,
                    loss, order_item_ids_quantity, min_order_amount, lsd_config_id,
                    delivery_cost_model, order_item_ids_cost, fprice_optimizer_id, lsd_stock_id
                ) VALUES %s
            """, bc_rows)
            
            execute_values(cur, """
                INSERT INTO basket_delivery_costs (
                    order_id, basket_id, lsd_config_id, delivery_cost, topup,
                    lsd_total_basket_cost, min_order_amount
                ) VALUES %s
            """, bdc_rows)
            
            execute_values(cur, """
                INSERT INTO basket_analyses (
                    order_id, basket_id, total_loss, total_goods_cost,
                    delivery_cost, delivery_topup, total_delivery_cost,
                    total_cost, total_loss_and_delivery, basket_rank, is_mono_basket
                ) VALUES %s
            """, ba_rows)
        
        self.conn.commit()
        
        elapsed = time.time() - start_time
        logger.info(f"Запись завершена за {elapsed:.2f} сек")
        logger.info(f"  basket_combinations: {len(bc_rows)} строк")
        logger.info(f"  basket_delivery_costs: {len(bdc_rows)} строк")
        logger.info(f"  basket_analyses: {len(ba_rows)} строк")
    
    # =========================================================================
    # ГЛАВНАЯ ФУНКЦИЯ
    # =========================================================================
    
    def optimize_order(self, order_id: int, top_n_final: int = 10, exclusions: dict = None) -> Dict[str, Any]:
        """
        Полная оптимизация заказа с NumPy векторизацией.
        Анализирует ВСЕ комбинации без предфильтрации.

        Args:
            order_id: ID заказа
            top_n_final: Количество финальных корзин для записи
            exclusions: Словарь с исключениями пользователя:
                - keywords: список ключевых слов для исключения
                - products: список названий продуктов из чёрного списка

        Returns:
            Dict с результатами
        """
        total_start = time.time()
        
        logger.info("=" * 80)
        logger.info(f"ОПТИМИЗАЦИЯ ЗАКАЗА #{order_id} (NumPy)")
        logger.info("=" * 80)
        
        # Отключаем GC для ускорения
        gc.disable()
        logger.info("GC отключен для ускорения вычислений")
        
        try:
            # Этап 1: Загрузка данных
            logger.info("\n[1/5] Загрузка данных в NumPy...")
            data = self.load_fprice_data_to_numpy(order_id, exclusions=exclusions)
            if data is None:
                return {"status": "no_data", "elapsed_time": 0}
            
            # Этап 2: Генерация индексной матрицы
            logger.info("\n[2/5] Генерация индексной матрицы комбинаций...")
            combo_indices = self.generate_combination_indices(data['n_variants'])
            
            # Этап 3: Расчёт базовых метрик
            logger.info("\n[3/5] Векторный расчёт базовых метрик...")
            total_losses, total_costs = self.calculate_basic_metrics(combo_indices, data)
            
            # Этап 4: Расчёт доставки ДЛЯ ВСЕХ комбинаций (ПОЛНАЯ ВЕКТОРИЗАЦИЯ)
            logger.info("\n[4/5] Расчёт доставки для всех комбинаций...")
            total_delivery, total_topup = self.calculate_delivery_vectorized_v2(combo_indices, data)
            
            # Этап 5: Финальный отбор
            logger.info(f"\n[5/5] Финальный отбор топ-{top_n_final} и запись в БД...")
            top_baskets = self.select_top_baskets(
                combo_indices, total_losses, total_costs, 
                total_delivery, total_topup, data, top_n_final
            )
            
            # Запись в БД
            self.save_to_db(top_baskets, order_id)
            
        finally:
            # Включаем GC обратно
            gc.enable()
            gc.collect()
            logger.info("GC включен обратно")
        
        total_elapsed = time.time() - total_start
        
        # Итоговая статистика
        best = top_baskets[0]
        logger.info("\n" + "=" * 80)
        logger.info("ОПТИМИЗАЦИЯ ЗАВЕРШЕНА")
        logger.info("=" * 80)
        logger.info(f"Всего комбинаций: {data['n_combinations']:,}")
        logger.info(f"Проанализировано: {data['n_combinations']:,} (все)")
        logger.info(f"Сохранено в БД: {len(top_baskets)} корзин")
        logger.info(f"Лучшая корзина: #{best['basket_id']}")
        logger.info(f"  - Потери + доставка: {best['total_loss_and_delivery']:.2f}₽")
        logger.info(f"  - Итого: {best['total_cost']:.2f}₽")
        logger.info(f"Время выполнения: {total_elapsed:.2f} сек")
        logger.info(f"Производительность: {data['n_combinations']/total_elapsed:,.0f} комбинаций/сек")
        logger.info("=" * 80)
        
        return {
            "status": "success",
            "order_id": order_id,
            "total_combinations": data['n_combinations'],
            "saved_baskets": len(top_baskets),
            "best_basket_id": best['basket_id'],
            "best_total_cost": best['total_cost'],
            "best_loss_and_delivery": best['total_loss_and_delivery'],
            "elapsed_time": total_elapsed,
            "performance_comb_per_sec": int(data['n_combinations']/total_elapsed)
        }


def optimize_order_numpy(order_id: int, db_connection_string: str,
                        top_n_final: int = 10, exclusions: dict = None) -> Dict[str, Any]:
    """
    Удобная функция-обёртка для оптимизации с NumPy.
    Анализирует ВСЕ комбинации без предфильтрации.

    Args:
        order_id: ID заказа
        db_connection_string: Строка подключения к PostgreSQL
        top_n_final: Количество финальных корзин для записи
        exclusions: Словарь с исключениями пользователя:
            - keywords: список ключевых слов для исключения
            - products: список названий продуктов из чёрного списка
    """
    with OrderOptimizerNumPy(db_connection_string) as optimizer:
        return optimizer.optimize_order(order_id, top_n_final, exclusions=exclusions)


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("ERROR: DATABASE_URL не найден в .env")
        exit(1)
    
    # Тестируем на заказе #25
    result = optimize_order_numpy(25, db_url, top_n_final=10)
    
    if result['status'] == 'success':
        print(f"\n✅ Заказ #{result['order_id']} успешно оптимизирован!")
        print(f"   Производительность: {result['performance_comb_per_sec']:,} комб/сек")
        print(f"   Время: {result['elapsed_time']:.2f} сек")
