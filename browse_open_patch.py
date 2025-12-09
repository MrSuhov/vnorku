"""
Патч для /browse/open - добавление поддержки cdp_enabled

Заменить функцию browse_open (строка 4085) в main.py
"""

@app.post("/browse/open")
async def browse_open(request: BrowseRequest):
    """
    Открывает браузер для ручного взаимодействия
    Поддерживает два режима:
    - cdp_enabled=true: CDP браузер с JSON куками (как в поиске)
    - cdp_enabled=false: Persistent profile с SQLite куками
    """
    logger.info(f"🌐 Opening browser for user {request.telegram_id} @ {request.lsd_name} (timeout: {request.auto_close_timeout}s)")

    driver = None
    cdp_manager = None
    profile_dir = None

    try:
        # Получаем конфигурацию ЛСД
        lsd_config = await get_lsd_config(request.lsd_name)
        if not lsd_config:
            raise HTTPException(
                status_code=404,
                detail=f"Конфигурация для {request.lsd_name} не найдена."
            )

        # Проверяем cdp_enabled в rpa_config
        rpa_config = lsd_config.rpa_config or {}
        cdp_enabled = rpa_config.get('cdp_enabled', False)
        
        logger.info(f"🔍 cdp_enabled={cdp_enabled} for {lsd_config.display_name}")
        
        base_url = lsd_config.base_url

        # ==================== РЕЖИМ 1: CDP БРАУЗЕР ====================
        if cdp_enabled:
            logger.info(f"🔧 Using CDP browser mode (cdp_enabled=true)")
            logger.info(f"💉 Will inject cookies from JSON files")
            
            # Получаем куки из JSON файлов
            cookies_data = await get_user_cookies(request.telegram_id, request.lsd_name)
            if not cookies_data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Куки для {request.lsd_name} не найдены. Сначала выполните авторизацию."
                )
            
            logger.info(f"📦 Loaded {len(cookies_data['cookies'])} cookies from JSON")
            
            # Создаём CDP браузер
            from cdp_cookie_manager import CDPCookieManager
            
            logger.info(f"🚀 Creating CDP browser...")
            cdp_manager = CDPCookieManager()
            
            # Открываем браузер с CDP
            driver = cdp_manager.create_browser(
                headless=False,  # Видимый режим для /browse
                block_media=False  # Разрешаем все медиа для полного UX
            )
            
            logger.info(f"✅ CDP browser created")
            
            # Инжектим куки через CDP
            logger.info(f"💉 Injecting cookies via CDP...")
            cdp_manager.inject_cookies(
                cookies=cookies_data['cookies'],
                local_storage=cookies_data.get('localStorage', {}),
                session_storage=cookies_data.get('sessionStorage', {}),
                base_url=base_url
            )
            
            logger.info(f"✅ Cookies injected successfully")
            
            # Навигация
            logger.info(f"📍 Navigating to {base_url}...")
            driver.get(base_url)
            await asyncio.sleep(2)
            
            logger.info(f"✅ Browser ready with CDP cookies")
            
        # ==================== РЕЖИМ 2: PERSISTENT PROFILE ====================
        else:
            logger.info(f"🔧 Using persistent profile mode (cdp_enabled=false)")
            logger.info(f"💾 Cookies stored in SQLite database")
            
            # Путь к персистентному профилю
            from pathlib import Path
            profile_dir = Path(__file__).parent / "browser_profiles" / f"user_{request.telegram_id}_lsd_{request.lsd_name}"

            # Проверяем, есть ли профиль
            profile_exists = (profile_dir / "Default" / "Cookies").exists()

            if profile_exists:
                logger.info(f"📁 Using existing persistent profile: {profile_dir}")
            else:
                logger.info(f"📁 Profile doesn't exist yet: {profile_dir}")
                logger.info(f"⚠️ User needs to authenticate first via /auth command")
                raise HTTPException(
                    status_code=400,
                    detail=f"Профиль не найден. Сначала выполните авторизацию через /auth {request.lsd_name}"
                )

            # Убиваем существующие Chrome процессы с этим профилем
            logger.info(f"🔪 Killing any existing Chrome processes...")
            import subprocess
            profile_dir_str = str(profile_dir)
            
            try:
                result = subprocess.run(['ps', 'aux'], capture_output=True, text=True, timeout=5)
                killed_count = 0
                for line in result.stdout.split('\n'):
                    if 'Chrome' in line and profile_dir_str in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            try:
                                pid = int(parts[1])
                                subprocess.run(['kill', '-9', str(pid)], timeout=2)
                                killed_count += 1
                            except:
                                continue
                
                if killed_count > 0:
                    logger.info(f"✅ Killed {killed_count} Chrome processes")
                    import time
                    time.sleep(1)
                else:
                    logger.info(f"ℹ️ No Chrome processes found")
                    
            except Exception as kill_error:
                logger.warning(f"⚠️ Failed to kill Chrome processes: {kill_error}")

            # Открываем браузер с persistent profile
            from simple_browser_manager import SimpleUndetectedBrowser
            
            driver = SimpleUndetectedBrowser.create_simple_browser(
                headless=False,
                user_data_dir=str(profile_dir),
                block_media=False
            )

            logger.info(f"✅ Browser opened with profile")

            # Навигация
            logger.info(f"📍 Navigating to {base_url}...")
            driver.get(base_url)
            await asyncio.sleep(1)

            logger.info(f"✅ Browser ready - cookies loaded from profile")

        # ==================== ОБЩАЯ ЧАСТЬ ====================
        
        logger.info(f"⏳ Browser will stay open for {request.auto_close_timeout} seconds...")
        logger.info(f"🖱️ You can interact with the browser during this time")
        
        if cdp_enabled:
            logger.info(f"💾 Cookies will be saved automatically when you close the browser")
        else:
            logger.info(f"💾 All changes will be saved to the persistent profile automatically")

        # Фоновая задача для автозакрытия
        async def auto_close_browser():
            try:
                await asyncio.sleep(request.auto_close_timeout)
                logger.info(f"🚪 Auto-closing browser for user {request.telegram_id}...")
                
                if cdp_enabled and cdp_manager:
                    cdp_manager.cleanup()
                elif driver:
                    try:
                        driver.quit()
                        logger.info(f"✅ Browser closed successfully")
                    except:
                        pass
                
                if profile_dir:
                    logger.info(f"💾 Profile preserved at: {profile_dir}")
                    
            except Exception as e:
                logger.error(f"❌ Error in auto_close_browser: {e}")

        # Запускаем фоновую задачу
        asyncio.create_task(auto_close_browser())

        # Немедленно возвращаем ответ
        return {
            "success": True,
            "data": {
                "message": f"Browser opened for {lsd_config.display_name}. Will auto-close in {request.auto_close_timeout}s",
                "mode": "cdp" if cdp_enabled else "persistent_profile",
                "cookies_loaded": len(cookies_data['cookies']) if cdp_enabled else 0,
                "auto_close_timeout": request.auto_close_timeout
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in browse_open: {e}")
        import traceback
        logger.error(traceback.format_exc())

        # Cleanup при ошибке
        if cdp_enabled and cdp_manager:
            try:
                logger.info(f"🧹 Cleaning up CDP browser due to error...")
                cdp_manager.cleanup()
            except:
                pass
        elif driver:
            try:
                logger.info(f"🧹 Cleaning up browser due to error...")
                driver.quit()
            except:
                pass

        raise HTTPException(status_code=500, detail=str(e))
