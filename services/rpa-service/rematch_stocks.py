#!/usr/bin/env python3
"""
Утилита для пересчета match_score в существующих записях lsd_stocks
Использует обновленный алгоритм v5.3 с поддержкой штрафа за незапрошенную обработку
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Загружаем .env ПЕРЕД импортом settings
from dotenv import load_dotenv
load_dotenv()

import asyncio
import logging
from decimal import Decimal
from sqlalchemy import select, update
from shared.database import get_async_session
from shared.database.models import LSDStock, OrderItem
from shared.utils.text_normalizer import normalize_product_name
from shared.utils.text_processing import normalize_and_extract_keywords, detect_processing_modifiers

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============= КОПИЯ АЛГОРИТМА v5.3 =============

def levenshtein_distance(s1: str, s2: str) -> int:
    """Вычисление расстояния Левенштейна между двумя строками"""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]

def fuzzy_word_similarity(word1: str, word2: str) -> float:
    """Вычисление нечёткой схожести между словами (0.0 - 1.0)"""
    if word1 == word2:
        return 1.0
    
    # Если одно слово содержится в другом
    if word1 in word2 or word2 in word1:
        shorter = min(len(word1), len(word2))
        longer = max(len(word1), len(word2))
        return shorter / longer * 0.9
    
    # Используем расстояние Левенштейна
    max_len = max(len(word1), len(word2))
    if max_len == 0:
        return 1.0
    
    distance = levenshtein_distance(word1, word2)
    similarity = 1.0 - (distance / max_len)
    
    return similarity if similarity >= 0.7 else 0.0

def calculate_match_score_v53(search_query: str, found_name: str, verbose: bool = False) -> tuple[float, bool]:
    """Алгоритм match_score v5.3 с штрафом за незапрошенную обработку продуктов"""
    if not search_query or not found_name:
        return 0.0, False
    
    # Нормализуем названия товаров
    normalized_search_query = normalize_product_name(search_query)
    normalized_found_name = normalize_product_name(found_name)
    
    search_words = normalize_and_extract_keywords(normalized_search_query)
    found_words = normalize_and_extract_keywords(normalized_found_name)
    
    if verbose:
        logger.debug(f"  Search words: {search_words}")
        logger.debug(f"  Found words: {found_words}")
    
    if not search_words:
        return 0.3, False
    
    if set(search_words) == set(found_words):
        return 1.0, True
    
    # Подсчёт совпадений
    total_search_words = len(search_words)
    total_found_words = len(found_words)
    match_score = 0.0
    exact_matches = 0
    fuzzy_matches = 0
    
    for search_word in search_words:
        best_match_score = 0.0
        found_exact = False
        
        for found_word in found_words:
            similarity = fuzzy_word_similarity(search_word, found_word)
            
            if similarity == 1.0:
                best_match_score = 1.0
                found_exact = True
                break
            elif similarity >= 0.95:
                best_match_score = max(best_match_score, 0.95)
            elif similarity >= 0.7:
                best_match_score = max(best_match_score, similarity * 0.8)
        
        if found_exact:
            exact_matches += 1
            match_score += 1.0
        elif best_match_score >= 0.7:
            fuzzy_matches += 1
            match_score += best_match_score
    
    base_score = match_score / total_search_words
    bonus = 0.0
    penalty = 0.0
    
    has_full_coverage = (exact_matches + fuzzy_matches) >= total_search_words
    
    # Штраф за длину
    word_count_ratio = total_found_words / total_search_words
    if word_count_ratio > 2.0:
        length_penalty = min(0.3, (word_count_ratio - 2.0) * 0.1)
        penalty += length_penalty
        if verbose:
            logger.debug(f"  ⚠️ Length penalty: -{length_penalty:.2f}")
    
    # Критический штраф за несовпадение первого слова
    if search_words and found_words:
        first_search_word = search_words[0]
        first_found_word = found_words[0]
        
        first_word_similarity = fuzzy_word_similarity(first_search_word, first_found_word)
        
        if first_word_similarity < 0.7:
            found_in_top3 = False
            top3_position = -1
            for i, found_word in enumerate(found_words[:3]):
                if fuzzy_word_similarity(first_search_word, found_word) >= 0.8:
                    found_in_top3 = True
                    top3_position = i
                    break
            
            if not found_in_top3:
                if has_full_coverage:
                    first_word_mismatch_penalty = 0.25
                    penalty += first_word_mismatch_penalty
                    if verbose:
                        logger.debug(f"  ⚠️ First word not in top-3, BUT full coverage (-0.25)")
                else:
                    first_word_mismatch_penalty = 0.45
                    penalty += first_word_mismatch_penalty
                    if verbose:
                        logger.debug(f"  ❌ CRITICAL: First word not in top-3 AND incomplete (-0.45)")
            else:
                coverage_ratio = (exact_matches + fuzzy_matches) / total_search_words
                if coverage_ratio >= 0.9:
                    first_word_mismatch_penalty = 0.15
                    if verbose:
                        logger.debug(f"  ⚠️ First word at pos {top3_position+1} but high coverage (-0.15)")
                else:
                    first_word_mismatch_penalty = 0.25
                    if verbose:
                        logger.debug(f"  ⚠️ First word at pos {top3_position+1} with low coverage (-0.25)")
                penalty += first_word_mismatch_penalty
        else:
            if first_word_similarity >= 0.95:
                bonus += 0.2
                if verbose:
                    logger.debug(f"  ✅ First word high similarity: +0.2")
            elif first_word_similarity >= 0.7:
                bonus += 0.1
                if verbose:
                    logger.debug(f"  ✅ First word medium similarity: +0.1")
    
    # ШТРАФ ЗА НЕЗАПРОШЕННУЮ ОБРАБОТКУ ПРОДУКТА (v5.3)
    search_modifiers = detect_processing_modifiers(normalized_search_query)
    found_modifiers = detect_processing_modifiers(normalized_found_name)
    
    # Модификаторы, которые есть в найденном, но НЕТ в запросе
    unrequested_modifiers = found_modifiers - search_modifiers
    
    if unrequested_modifiers:
        # Есть незапрошенная обработка
        processing_penalty = 0.40  # Сильный штраф
        penalty += processing_penalty
        if verbose:
            logger.debug(f"  ❌ Unrequested processing: {unrequested_modifiers} (-{processing_penalty:.2f})")
    
    # Бонусы даются при penalty < 0.5
    if total_search_words <= 2 and has_full_coverage:
        if penalty < 0.5:
            full_coverage_bonus = 0.15
            bonus += full_coverage_bonus
            if verbose:
                logger.debug(f"  ✅ Full coverage bonus: +{full_coverage_bonus:.2f}")
    
    exact_ratio = exact_matches / total_search_words
    if exact_ratio >= 0.5:
        if penalty < 0.5:
            exact_match_bonus = exact_ratio * 0.1
            bonus += exact_match_bonus
            if verbose:
                logger.debug(f"  ✅ Exact ratio bonus: +{exact_match_bonus:.2f}")
    
    # Минимальный порог при penalty < 0.3
    if has_full_coverage and penalty < 0.3:
        min_score_for_full_coverage = 0.7
        if (base_score + bonus - penalty) < min_score_for_full_coverage:
            coverage_adjustment = min_score_for_full_coverage - (base_score + bonus - penalty)
            bonus += coverage_adjustment
            if verbose:
                logger.debug(f"  ✅ Coverage floor: +{coverage_adjustment:.2f}")
    
    final_score = base_score + bonus - penalty
    final_score = max(0.0, min(1.0, final_score))
    final_score = round(final_score, 3)
    
    is_exact = (exact_matches >= total_search_words or 
               (final_score >= 0.95 and exact_matches + fuzzy_matches >= total_search_words))
    
    if verbose:
        logger.debug(f"  📊 base={base_score:.3f} + bonus={bonus:.3f} - penalty={penalty:.3f} = {final_score:.3f}")
    
    return final_score, is_exact

# ============= ОСНОВНАЯ ЛОГИКА РЕМЭТЧИНГА =============

async def rematch_all_stocks(order_id: int = None, dry_run: bool = False, verbose: bool = False):
    """
    Пересчет match_score для всех записей lsd_stocks
    
    Args:
        order_id: Опционально - пересчитать только для конкретного заказа
        dry_run: Если True - только показать изменения, не сохранять в БД
        verbose: Подробный вывод для каждой записи
    """
    logger.info("=" * 80)
    logger.info("🔄 REMATCH UTILITY v5.3 - Пересчет match_score для lsd_stocks")
    logger.info("=" * 80)
    
    if dry_run:
        logger.info("🧪 DRY RUN MODE - изменения НЕ будут сохранены в БД")
    
    if order_id:
        logger.info(f"🎯 Фильтр: только order_id={order_id}")
    
    logger.info("")
    
    try:
        async for db in get_async_session():
            # Получаем все записи lsd_stocks с их оригинальными запросами
            query = select(LSDStock, OrderItem.product_name).join(
                OrderItem, LSDStock.order_item_id == OrderItem.id
            )
            
            if order_id:
                query = query.where(LSDStock.order_id == order_id)
            
            result = await db.execute(query)
            stocks_with_names = result.all()
            
            if not stocks_with_names:
                logger.warning("⚠️ Не найдено записей для обработки")
                return
            
            total_records = len(stocks_with_names)
            logger.info(f"📦 Найдено записей для обработки: {total_records}")
            logger.info("")
            
            updated_count = 0
            no_change_count = 0
            significant_changes = []
            
            for i, (stock, product_name) in enumerate(stocks_with_names, 1):
                # Используем search_query если есть, иначе product_name
                search_query = stock.search_query or product_name
                found_name = stock.found_name
                
                # Пересчитываем match_score
                new_score, new_is_exact = calculate_match_score_v53(
                    search_query=search_query,
                    found_name=found_name,
                    verbose=verbose
                )
                
                old_score = float(stock.match_score) if stock.match_score else 0.0
                score_diff = new_score - old_score
                
                # Логируем прогресс
                if i % 10 == 0 or verbose:
                    logger.info(f"[{i}/{total_records}] Обработано...")
                
                # Если изменение значительное (>0.1), показываем детали
                if abs(score_diff) > 0.1:
                    significant_changes.append({
                        'stock_id': stock.id,
                        'search': search_query,
                        'found': found_name,
                        'old_score': old_score,
                        'new_score': new_score,
                        'diff': score_diff
                    })
                    
                    if verbose:
                        logger.info(f"\n📝 Значительное изменение:")
                        logger.info(f"  ID: {stock.id}")
                        logger.info(f"  Запрос: '{search_query}'")
                        logger.info(f"  Найдено: '{found_name}'")
                        logger.info(f"  Было: {old_score:.3f} → Стало: {new_score:.3f} (Δ {score_diff:+.3f})")
                
                # Обновляем в БД (если не dry_run)
                if not dry_run:
                    if abs(score_diff) > 0.001:  # Обновляем только если есть изменение
                        await db.execute(
                            update(LSDStock)
                            .where(LSDStock.id == stock.id)
                            .values(
                                match_score=Decimal(str(new_score)),
                                is_exact_match=new_is_exact
                            )
                        )
                        updated_count += 1
                    else:
                        no_change_count += 1
                else:
                    if abs(score_diff) > 0.001:
                        updated_count += 1
                    else:
                        no_change_count += 1
            
            if not dry_run:
                await db.commit()
                logger.info("\n✅ Изменения сохранены в БД")
            
            # Итоговая статистика
            logger.info("")
            logger.info("=" * 80)
            logger.info("📊 ИТОГОВАЯ СТАТИСТИКА")
            logger.info("=" * 80)
            logger.info(f"Всего записей обработано: {total_records}")
            logger.info(f"Обновлено (изменение score): {updated_count}")
            logger.info(f"Без изменений: {no_change_count}")
            logger.info(f"Значительных изменений (|Δ| > 0.1): {len(significant_changes)}")
            
            if significant_changes:
                logger.info("")
                logger.info("🔍 ТОП-10 ЗНАЧИТЕЛЬНЫХ ИЗМЕНЕНИЙ:")
                logger.info("-" * 80)
                
                # Сортируем по абсолютному изменению
                significant_changes.sort(key=lambda x: abs(x['diff']), reverse=True)
                
                for change in significant_changes[:10]:
                    logger.info(f"\nID {change['stock_id']}:")
                    logger.info(f"  '{change['search'][:50]}...' vs '{change['found'][:50]}...'")
                    logger.info(f"  {change['old_score']:.3f} → {change['new_score']:.3f} ({change['diff']:+.3f})")
            
            logger.info("")
            logger.info("=" * 80)
            logger.info("✅ Rematch completed successfully!")
            logger.info("=" * 80)
            
    except Exception as e:
        logger.error(f"❌ Ошибка при rematch: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

async def show_stats(order_id: int = None):
    """Показать статистику по match_score в БД"""
    logger.info("=" * 80)
    logger.info("📊 СТАТИСТИКА MATCH_SCORE")
    logger.info("=" * 80)
    
    try:
        async for db in get_async_session():
            query = select(LSDStock)
            
            if order_id:
                query = query.where(LSDStock.order_id == order_id)
            
            result = await db.execute(query)
            stocks = result.scalars().all()
            
            if not stocks:
                logger.info("⚠️ Нет записей в lsd_stocks")
                return
            
            total = len(stocks)
            scores = [float(s.match_score) if s.match_score else 0.0 for s in stocks]
            
            logger.info(f"\nВсего записей: {total}")
            logger.info(f"Средний score: {sum(scores)/len(scores):.3f}")
            logger.info(f"Минимальный: {min(scores):.3f}")
            logger.info(f"Максимальный: {max(scores):.3f}")
            
            # Распределение по диапазонам
            ranges = {
                '0.0-0.3': sum(1 for s in scores if s < 0.3),
                '0.3-0.5': sum(1 for s in scores if 0.3 <= s < 0.5),
                '0.5-0.7': sum(1 for s in scores if 0.5 <= s < 0.7),
                '0.7-0.9': sum(1 for s in scores if 0.7 <= s < 0.9),
                '0.9-1.0': sum(1 for s in scores if 0.9 <= s <= 1.0)
            }
            
            logger.info("\nРаспределение по диапазонам:")
            for range_name, count in ranges.items():
                pct = (count / total * 100) if total > 0 else 0
                logger.info(f"  {range_name}: {count} ({pct:.1f}%)")
            
            logger.info("")
            logger.info("=" * 80)
            
    except Exception as e:
        logger.error(f"❌ Ошибка при получении статистики: {e}")
        raise

# ============= CLI INTERFACE =============

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Утилита для пересчета match_score в lsd_stocks (v5.3 с поддержкой модификаторов обработки)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

  # Показать статистику
  python rematch_stocks.py --stats

  # Пересчитать все записи (с сохранением)
  python rematch_stocks.py

  # Пересчитать только для заказа #123
  python rematch_stocks.py --order-id 123

  # Dry run (без сохранения в БД)
  python rematch_stocks.py --dry-run

  # Подробный вывод
  python rematch_stocks.py --verbose

  # Dry run + verbose для заказа #123
  python rematch_stocks.py --order-id 123 --dry-run --verbose
        """
    )
    
    parser.add_argument('--order-id', type=int, help='Пересчитать только для конкретного заказа')
    parser.add_argument('--dry-run', action='store_true', help='Показать изменения без сохранения в БД')
    parser.add_argument('--verbose', '-v', action='store_true', help='Подробный вывод')
    parser.add_argument('--stats', action='store_true', help='Показать статистику match_score')
    
    args = parser.parse_args()
    
    if args.stats:
        await show_stats(order_id=args.order_id)
    else:
        await rematch_all_stocks(
            order_id=args.order_id,
            dry_run=args.dry_run,
            verbose=args.verbose
        )

if __name__ == "__main__":
    asyncio.run(main())
