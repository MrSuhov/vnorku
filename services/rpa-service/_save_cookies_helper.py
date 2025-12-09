"""
Вспомогательная функция для сохранения кук перед досрочным выходом
"""


async def _save_cookies_before_return(
    cdp_manager,
    driver,
    telegram_id: int,
    lsd_config,
    products: list,
    save_user_cookies_func
):
    """
    Извлекает и сохраняет куки + localStorage + sessionStorage перед возвратом результатов.
    Используется для гарантии сохранения кук при любом сценарии выхода из функции.
    
    Args:
        cdp_manager: CDPCookieManager instance или None (для SimpleUndetectedBrowser)
        driver: Selenium WebDriver instance
        telegram_id: ID пользователя в Telegram
        lsd_config: Конфигурация ЛСД
        products: Список продуктов (для метаданных)
        save_user_cookies_func: Функция save_user_cookies для сохранения кук
    
    Returns:
        None (логирует успех/ошибку)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"💾 Saving cookies before return...")
    
    try:
        if cdp_manager:
            # Извлекаем cookies + localStorage + sessionStorage
            session_data = cdp_manager.extract_cookies_and_storage()
            updated_cookies = session_data['cookies']
            updated_local_storage = session_data['localStorage']
            updated_session_storage = session_data['sessionStorage']
            
            if updated_cookies:
                logger.info(f"🔄 Saving {len(updated_cookies)} cookies + "
                          f"{len(updated_local_storage)} localStorage + "
                          f"{len(updated_session_storage)} sessionStorage items...")
                cookies_saved = await save_user_cookies_func(
                    telegram_id=telegram_id,
                    lsd_name=lsd_config.name,
                    lsd_config_id=lsd_config.id,
                    cookies=updated_cookies,
                    local_storage=updated_local_storage,
                    session_storage=updated_session_storage,
                    metadata={
                        'last_search_count': len(products),
                        'last_url': driver.current_url if hasattr(driver, 'current_url') else 'N/A'
                    }
                )
                if cookies_saved:
                    logger.info(f"✅ Cookies saved successfully before return")
                else:
                    logger.warning(f"⚠️ Failed to save cookies before return")
            else:
                logger.warning(f"⚠️ No cookies extracted from CDP before return")
        else:
            # SimpleUndetectedBrowser
            from simple_browser_manager import SimpleUndetectedBrowser
            updated_cookies = SimpleUndetectedBrowser.extract_cookies(driver)
            if updated_cookies:
                logger.info(f"🔄 Saving {len(updated_cookies)} cookies...")
                cookies_saved = await save_user_cookies_func(
                    telegram_id=telegram_id,
                    lsd_name=lsd_config.name,
                    lsd_config_id=lsd_config.id,
                    cookies=updated_cookies,
                    metadata={
                        'last_search_count': len(products),
                        'last_url': driver.current_url if hasattr(driver, 'current_url') else 'N/A'
                    }
                )
                if cookies_saved:
                    logger.info(f"✅ Cookies saved successfully before return")
                else:
                    logger.warning(f"⚠️ Failed to save cookies before return")
            else:
                logger.warning(f"⚠️ No cookies extracted from SIMPLE browser before return")
    except Exception as cookie_save_error:
        logger.error(f"❌ Error saving cookies before return: {cookie_save_error}")
        import traceback
        logger.debug(traceback.format_exc())
