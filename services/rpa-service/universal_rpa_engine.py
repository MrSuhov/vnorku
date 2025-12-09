#!/usr/bin/env python3
"""
Универсальный RPA движок с единой функцией extract_qr()
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Union

logger = logging.getLogger(__name__)

async def extract_qr(
    driver_or_page: Union[Any, Any],  # Selenium WebDriver или Playwright Page
    step: Dict[str, Any] = None,
    step_id: str = "qr_extraction",
    telegram_id: int = None,
    **kwargs
) -> Dict[str, Any]:
    """
    🚀 УНИВЕРСАЛЬНАЯ функция извлечения QR кодов
    
    Автоматически определяет тип движка и использует соответствующий метод:
    - Selenium WebDriver → UniversalQRExtractor.extract_qr_link_universal()
    - Playwright Page → UniversalQRExtractor.extract_qr_link_universal()
    
    Args:
        driver_or_page: Selenium WebDriver или Playwright Page объект
        step: Конфигурация шага (опционально)
        step_id: Идентификатор шага для логирования
        telegram_id: ID пользователя в Telegram
        **kwargs: Дополнительные параметры
    
    Returns:
        Dict с результатом: {'status': 'success'|'error'|'no_qr_found', 'message': str, ...}
    """
    try:
        logger.info(f"🎯 Universal extract_qr() called for step '{step_id}'")
        
        # Автоматическое определение типа движка
        engine_type = detect_engine_type(driver_or_page)
        logger.info(f"🔍 Detected engine type: {engine_type}")
        
        # Подготовка параметров
        if step is None:
            step = {}
        
        # Используем универсальный экстрактор из существующего модуля
        from universal_qr_extractor import UniversalQRExtractor
        
        result = await UniversalQRExtractor.extract_qr_link_universal(
            driver_or_page=driver_or_page,
            step=step,
            step_id=step_id,
            telegram_id=telegram_id,
            engine_type=engine_type
        )
        
        logger.info(f"✅ Universal extract_qr() completed: {result.get('status')}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error in universal extract_qr(): {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'status': 'error',
            'message': f'Universal QR extraction failed: {str(e)}'
        }

def detect_engine_type(driver_or_page) -> str:
    """
    🔍 Автоматическое определение типа браузерного движка
    
    Returns:
        'selenium' | 'playwright' | 'unknown'
    """
    try:
        # Проверяем Selenium WebDriver
        if hasattr(driver_or_page, 'find_elements') and hasattr(driver_or_page, 'get'):
            return 'selenium'
        
        # Проверяем Playwright Page
        if hasattr(driver_or_page, 'query_selector') and hasattr(driver_or_page, 'screenshot'):
            return 'playwright'
        
        # Дополнительные проверки по типу класса
        driver_class_name = driver_or_page.__class__.__name__
        
        if 'webdriver' in driver_class_name.lower() or 'chrome' in driver_class_name.lower():
            return 'selenium'
        
        if 'page' in driver_class_name.lower() and 'playwright' in str(type(driver_or_page)):
            return 'playwright'
        
        logger.warning(f"⚠️ Unknown engine type for class: {driver_class_name}")
        return 'unknown'
        
    except Exception as e:
        logger.error(f"❌ Error detecting engine type: {e}")
        return 'unknown'

# Обратная совместимость: алиасы удалены, используйте extract_qr() напрямую

logger.info("🚀 Universal RPA Engine loaded with unified extract_qr() function!")
