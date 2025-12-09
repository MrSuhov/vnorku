#!/usr/bin/env python3
"""
Unified Optimizer - единая точка входа для оптимизации заказов.
Автоматически выбирает между NumPy (быстрый) и Legacy (старый) оптимизаторами.
"""

import os
import sys
import argparse
from dotenv import load_dotenv
import logging

# Добавляем текущую директорию в sys.path для импортов
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def optimize_order_unified(order_id: int, db_connection_string: str,
                           engine: str = "auto",
                           exclusions: dict = None,
                           **kwargs) -> dict:
    """
    Универсальная функция оптимизации заказа.

    Args:
        order_id: ID заказа
        db_connection_string: PostgreSQL connection string
        engine: Движок оптимизации - "numpy", "legacy", или "auto" (по умолчанию)
        exclusions: Словарь с исключениями пользователя:
            - keywords: список ключевых слов категорий для исключения
            - products: список названий продуктов из чёрного списка
        **kwargs: Дополнительные параметры для оптимизатора

    Returns:
        Dict с результатами оптимизации
    """

    # Логируем исключения если они есть
    if exclusions:
        kw_count = len(exclusions.get('keywords', []))
        prod_count = len(exclusions.get('products', []))
        logger.info(f"🚫 Исключения: {kw_count} ключевых слов, {prod_count} продуктов")

    # Автоматический выбор движка
    if engine == "auto":
        try:
            import numpy
            engine = "numpy"
            logger.info("✓ NumPy доступен, используем NumPy оптимизатор")
        except ImportError:
            engine = "legacy"
            logger.info("⚠ NumPy недоступен, используем Legacy оптимизатор")

    # Запускаем соответствующий оптимизатор
    if engine == "numpy":
        try:
            # Импортируем из той же директории
            from order_optimizer_numpy import optimize_order_numpy

            logger.info(f"🚀 Запуск NumPy оптимизатора для заказа #{order_id}")

            # Параметры для NumPy версии
            top_n_final = kwargs.get('top_n_final', kwargs.get('top_n', 10))

            result = optimize_order_numpy(
                order_id=order_id,
                db_connection_string=db_connection_string,
                top_n_final=top_n_final,
                exclusions=exclusions
            )

            result['engine'] = 'numpy'
            return result

        except Exception as e:
            logger.error(f"❌ NumPy оптимизатор завершился с ошибкой: {e}")
            logger.info("⤷ Переключаемся на Legacy оптимизатор...")
            engine = "legacy"

    if engine == "legacy":
        # Импортируем из той же директории
        from order_optimizer import optimize_order

        logger.info(f"⚙️  Запуск Legacy оптимизатора для заказа #{order_id}")

        # Параметры для Legacy версии
        top_n = kwargs.get('top_n', 10)

        result = optimize_order(
            order_id=order_id,
            db_connection_string=db_connection_string,
            top_n=top_n,
            exclusions=exclusions
        )

        result['engine'] = 'legacy'
        return result

    raise ValueError(f"Неизвестный движок: {engine}. Доступны: numpy, legacy, auto")


def main():
    """CLI интерфейс для оптимизатора."""
    
    parser = argparse.ArgumentParser(
        description="Оптимизация заказа - поиск лучших корзин по ЛСД"
    )
    
    parser.add_argument(
        "order_id",
        type=int,
        help="ID заказа для оптимизации"
    )
    
    parser.add_argument(
        "--engine",
        type=str,
        choices=["numpy", "legacy", "auto"],
        default="auto",
        help="Движок оптимизации (по умолчанию: auto)"
    )
    
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Количество лучших корзин для сохранения (по умолчанию: 10)"
    )
    
    parser.add_argument(
        "--top-k-prefilter",
        type=int,
        default=100000,
        help="Количество комбинаций для предфильтрации в NumPy (по умолчанию: 100000)"
    )
    
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="PostgreSQL connection string (по умолчанию: из .env)"
    )
    
    args = parser.parse_args()
    
    # Загружаем DATABASE_URL
    load_dotenv()
    db_url = args.db_url or os.getenv("DATABASE_URL")
    
    if not db_url:
        print("❌ ERROR: DATABASE_URL не найден. Укажите --db-url или создайте .env")
        return 1
    
    # Запускаем оптимизацию
    print("=" * 80)
    print(f"ОПТИМИЗАЦИЯ ЗАКАЗА #{args.order_id}")
    print("=" * 80)
    print(f"Движок: {args.engine}")
    print(f"Топ-N: {args.top_n}")
    if args.engine in ["numpy", "auto"]:
        print(f"Предфильтрация: {args.top_k_prefilter:,}")
    print("-" * 80)
    
    try:
        result = optimize_order_unified(
            order_id=args.order_id,
            db_connection_string=db_url,
            engine=args.engine,
            top_n=args.top_n,
            top_k_prefilter=args.top_k_prefilter
        )
        
        if result['status'] == 'success':
            print("\n" + "=" * 80)
            print("✅ ОПТИМИЗАЦИЯ ЗАВЕРШЕНА")
            print("=" * 80)
            print(f"Движок: {result['engine'].upper()}")
            print(f"Всего комбинаций: {result.get('total_combinations', 'N/A'):,}")
            if 'prefiltered' in result:
                print(f"Предфильтровано: {result['prefiltered']:,}")
            print(f"Сохранено корзин: {result.get('saved_baskets', 'N/A')}")
            print(f"\nЛучшая корзина: #{result.get('best_basket_id', 'N/A')}")
            print(f"  Стоимость: {result.get('best_total_cost', 0):.2f}₽")
            print(f"  Потери+доставка: {result.get('best_loss_and_delivery', 0):.2f}₽")
            print(f"\nВремя выполнения: {result.get('elapsed_time', 0):.2f} сек")
            
            if 'performance_comb_per_sec' in result:
                print(f"Производительность: {result['performance_comb_per_sec']:,} комб/сек")
            
            if result.get('missing_mono_lsds'):
                print(f"\n⚠️  ЛСД без моно-корзин: {', '.join(result['missing_mono_lsds'])}")
            
            print("=" * 80)
            return 0
        else:
            print(f"\n❌ Оптимизация завершилась с ошибкой: {result.get('status')}")
            return 1
            
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
