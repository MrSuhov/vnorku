# Это временный файл с обновлённой функцией extract_delivery_ranges
# После проверки нужно будет заменить в основном файле

async def extract_delivery_ranges(driver, delivery_config: dict, telegram_id: int = None) -> tuple[List[Dict[str, Any]], Optional[float]]:
    """
    Извлечение диапазонов доставки и min_order_amount из модального окна
    
    ОБЯЗАТЕЛЬНЫЕ элементы (ошибка + HTML dump):
    - Первый fee_selector (fee_selectors[0])
    - Первый threshold_selector (threshold_selectors[0])
    - min_order_amount_selector (если указан в конфиге)
    
    ОПЦИОНАЛЬНЫЕ элементы (останавливаем извлечение):
    - Все остальные fee_selectors и threshold_selectors (индексы >= 1)
    
    Args:
        driver: Selenium WebDriver
        delivery_config: Конфигурация delivery_ranges из search_config
        telegram_id: ID пользователя для замены плейсхолдеров в trigger actions
    
    Returns:
        tuple: (Список диапазонов, min_order_amount или None)
    """
    ranges_data = []
    min_order_amount = None
    
    try:
        # Шаг 1: Выполнить trigger (открыть модальное окно)
        trigger_config = delivery_config.get('trigger', {})
        
        # НОВЫЙ ФОРМАТ: Проверяем наличие массива actions (последовательные действия)
        actions = trigger_config.get('actions')
        
        if actions:
            # === НОВАЯ ЛОГИКА: Последовательное выполнение всех actions ===
            logger.info(f"🎯 Sequential trigger mode: {len(actions)} action(s) to execute")
            
            for idx, action_config in enumerate(actions, 1):
                logger.info(f"🔘 [{idx}/{len(actions)}] Executing action: {action_config.get('action', 'unknown')}")
                
                success = await execute_trigger_action(driver, action_config, telegram_id)
                
                if not success:
                    logger.error(f"❌ Action [{idx}] failed, stopping trigger sequence")
                    # Сохраняем HTML для отладки
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    log_file = f"/Users/ss/GenAI/korzinka/logs/page_dump_{timestamp}.html"
                    try:
                        with open(log_file, 'w', encoding='utf-8') as f:
                            f.write(driver.page_source)
                        logger.warning(f"⚠️ Page HTML saved to: {log_file}")
                    except:
                        pass
                    return ranges_data, min_order_amount
                
                logger.info(f"✅ [{idx}/{len(actions)}] Action completed successfully")
            
            logger.info(f"🎉 All {len(actions)} trigger actions completed successfully")
            
        else:
            # === СТАРАЯ ЛОГИКА: Обратная совместимость с selector/selectors ===
            trigger_action = trigger_config.get('action', 'click')
            
            # Поддержка массива селекторов (fallback) и одиночного селектора
            trigger_selectors = trigger_config.get('selectors')
            if not trigger_selectors:
                # Fallback на старый формат с одним селектором
                single_selector = trigger_config.get('selector')
                if single_selector:
                    trigger_selectors = [single_selector]
                else:
                    logger.error("❌ No trigger selector(s) in delivery_ranges config")
                    return ranges_data, min_order_amount
            
            wait_after = trigger_config.get('wait_after', 500) / 1000  # конвертируем в секунды
            
            logger.info(f"🔘 Fallback trigger mode: {trigger_action} with {len(trigger_selectors)} selector(s)")
            
            # Пробуем каждый селектор по очереди (FALLBACK логика)
            trigger_found = False
            last_error = None
            
            for idx, trigger_selector in enumerate(trigger_selectors, 1):
                logger.info(f"🔍 Trying selector [{idx}/{len(trigger_selectors)}]: '{trigger_selector}'")
                
                try:
                    # Выполняем действие trigger
                    if trigger_action == 'click':
                        if trigger_selector.startswith('//'):
                            trigger_element = driver.find_element(By.XPATH, trigger_selector)
                        else:
                            trigger_element = driver.find_element(By.CSS_SELECTOR, trigger_selector)
                        trigger_element.click()
                        logger.info(f"✅ Trigger clicked successfully with selector [{idx}]")
                        trigger_found = True
                        break
                        
                    elif trigger_action == 'hover':
                        from selenium.webdriver.common.action_chains import ActionChains
                        if trigger_selector.startswith('//'):
                            trigger_element = driver.find_element(By.XPATH, trigger_selector)
                        else:
                            trigger_element = driver.find_element(By.CSS_SELECTOR, trigger_selector)
                        ActionChains(driver).move_to_element(trigger_element).perform()
                        logger.info(f"✅ Trigger hovered successfully with selector [{idx}]")
                        trigger_found = True
                        break
                        
                except Exception as e:
                    logger.debug(f"⚠️ Selector [{idx}] failed: {e}")
                    last_error = e
                    continue
            
            # Если ни один селектор не сработал
            if not trigger_found:
                # Сохраняем HTML страницы для анализа
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                log_file = f"/Users/ss/GenAI/korzinka/logs/page_dump_{timestamp}.html"
                
                try:
                    html_content = driver.page_source
                    with open(log_file, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    logger.warning(f"⚠️ None of {len(trigger_selectors)} trigger selector(s) found. Page HTML saved to: {log_file}")
                    logger.warning(f"⚠️ Current URL: {driver.current_url}")
                    logger.warning(f"⚠️ Tried selectors: {trigger_selectors}")
                except Exception as save_error:
                    logger.error(f"❌ Failed to save page HTML: {save_error}")
                
                # Возвращаем пустые данные вместо исключения
                return ranges_data, min_order_amount
            
            # Пауза после trigger
            await asyncio.sleep(wait_after)
        
        # Шаг 1.5: Извлечь min_order_amount (если есть в конфиге) - ОБЯЗАТЕЛЬНЫЙ если указан
        min_order_config_selector = delivery_config.get('min_order_amount_selector')
        
        if min_order_config_selector:
            logger.info(f"💰 Found min_order_amount_selector in config (MANDATORY): {min_order_config_selector}")
            
            extraction_failed = False
            
            if isinstance(min_order_config_selector, dict):
                # Извлечение через селектор (формат {"selector": "...", "fallback": ...})
                selector = min_order_config_selector.get('selector')
                fallback = min_order_config_selector.get('fallback')
                
                if selector:
                    logger.info(f"🔍 Extracting min_order_amount via selector: {selector}")
                    try:
                        extracted_value = extract_numeric_value(driver, selector)
                        if extracted_value is not None:
                            min_order_amount = extracted_value
                            logger.info(f"✅ Extracted min_order_amount: {min_order_amount}₽")
                        elif fallback is not None:
                            min_order_amount = float(fallback)
                            logger.info(f"🔄 Using fallback min_order_amount: {min_order_amount}₽")
                        else:
                            extraction_failed = True
                            logger.error("❌ Failed to extract min_order_amount and no fallback provided")
                    except Exception as e:
                        logger.error(f"❌ Error extracting min_order_amount via selector: {e}")
                        if fallback is not None:
                            min_order_amount = float(fallback)
                            logger.info(f"🔄 Using fallback due to error: {min_order_amount}₽")
                        else:
                            extraction_failed = True
                else:
                    logger.warning("⚠️ min_order_amount_selector config has no selector")
                    if fallback is not None:
                        min_order_amount = float(fallback)
                        logger.info(f"🔄 Using fallback (no selector): {min_order_amount}₽")
                    else:
                        extraction_failed = True
                        
            elif isinstance(min_order_config_selector, str):
                # Это селектор напрямую (строка с XPath или CSS) - ОБЯЗАТЕЛЬНЫЙ
                logger.info(f"🔍 Extracting MANDATORY min_order_amount via selector string: {min_order_config_selector}")
                try:
                    extracted_value = extract_numeric_value(driver, min_order_config_selector)
                    if extracted_value is not None:
                        min_order_amount = extracted_value
                        logger.info(f"✅ Extracted min_order_amount: {min_order_amount}₽")
                    else:
                        extraction_failed = True
                        logger.error(f"❌ Failed to extract MANDATORY min_order_amount from selector string")
                except Exception as e:
                    extraction_failed = True
                    logger.error(f"❌ Error extracting MANDATORY min_order_amount via selector string: {e}")
                        
            elif isinstance(min_order_config_selector, (int, float)):
                # Статичное значение
                min_order_amount = float(min_order_config_selector)
                logger.info(f"💰 Using static min_order_amount: {min_order_amount}₽")
            else:
                logger.warning(f"⚠️ Unknown min_order_amount_selector config format: {type(min_order_config_selector)}")
            
            # Если извлечение обязательного min_order_amount failed - сохраняем HTML и возвращаем пустые данные
            if extraction_failed:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                log_file = f"/Users/ss/GenAI/korzinka/logs/min_order_error_{timestamp}.html"
                
                try:
                    with open(log_file, 'w', encoding='utf-8') as f:
                        f.write(driver.page_source)
                    logger.error(f"💾 Page HTML saved to: {log_file}")
                except Exception as save_error:
                    logger.error(f"❌ Failed to save HTML dump: {save_error}")
                
                logger.error("❌ MANDATORY min_order_amount extraction failed - returning empty data")
                return [], None
        else:
            logger.debug("📝 No min_order_amount_selector in config")
        
        # Шаг 2: Извлечь диапазоны по массивам селекторов
        ordered_extraction = delivery_config.get('ordered_extraction', {})
        fee_selectors = ordered_extraction.get('fee_selectors', [])
        threshold_selectors = ordered_extraction.get('threshold_selectors', [])
        
        if not fee_selectors or not threshold_selectors:
            logger.error("❌ Missing fee_selectors or threshold_selectors in ordered_extraction")
            return ranges_data, min_order_amount
        
        # Проверка: количество селекторов должно совпадать
        if len(fee_selectors) != len(threshold_selectors):
            logger.error(f"❌ Mismatch: {len(fee_selectors)} fee_selectors vs {len(threshold_selectors)} threshold_selectors")
            return ranges_data, min_order_amount
        
        logger.info(f"📋 Extracting up to {len(fee_selectors)} delivery ranges")
        
        # === ИЗВЛЕЧЕНИЕ ПЕРВОГО ДИАПАЗОНА (ОБЯЗАТЕЛЬНЫЙ) ===
        if len(fee_selectors) == 0 or len(threshold_selectors) == 0:
            logger.error("❌ No selectors provided for extraction")
            return [], min_order_amount
        
        # Первый диапазон - ОБЯЗАТЕЛЬНЫЙ
        first_fee_sel = fee_selectors[0]
        first_threshold_sel = threshold_selectors[0]
        
        try:
            logger.info(f"🔍 [1] Extracting MANDATORY first range")
            logger.debug(f"🔍 [1] Fee selector: '{first_fee_sel}'")
            logger.debug(f"🔍 [1] Threshold selector: '{first_threshold_sel}'")
            
            # Извлекаем fee (если селектор не null)
            if first_fee_sel is None or first_fee_sel == 'null':
                fee = 0.0
                fee_text = "Бесплатная доставка"
                logger.debug(f"📝 [1] Fee selector is null, using fee=0.0")
            else:
                if first_fee_sel.startswith('//'):
                    fee_element = driver.find_element(By.XPATH, first_fee_sel)
                else:
                    fee_element = driver.find_element(By.CSS_SELECTOR, first_fee_sel)
                fee_text = fee_element.text.strip()
                fee = parse_delivery_fee(fee_text)
            
            # Извлекаем threshold (ОБЯЗАТЕЛЬНЫЙ)
            if first_threshold_sel.startswith('//'):
                threshold_element = driver.find_element(By.XPATH, first_threshold_sel)
            else:
                threshold_element = driver.find_element(By.CSS_SELECTOR, first_threshold_sel)
            threshold_text = threshold_element.text.strip()
            threshold = parse_delivery_info(threshold_text)
            
            logger.debug(f"📝 [1] Fee text: '{fee_text}', Threshold text: '{threshold_text}'")
            
            ranges_data.append({
                'fee': fee,
                'threshold': threshold,
                'fee_text': fee_text,
                'threshold_text': threshold_text
            })
            
            logger.info(f"✅ [1] Extracted MANDATORY first range: fee={fee}₽, threshold={threshold}₽")
            
        except Exception as first_range_error:
            logger.error(f"❌ [1] MANDATORY first range extraction failed: {first_range_error}")
            
            # Сохраняем HTML для отладки
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = f"/Users/ss/GenAI/korzinka/logs/delivery_range_error_{timestamp}.html"
            
            try:
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
                logger.error(f"💾 Page HTML saved to: {log_file}")
            except Exception as save_error:
                logger.error(f"❌ Failed to save HTML dump: {save_error}")
            
            # Возвращаем пустые данные при ошибке обязательного элемента
            return [], min_order_amount
        
        # === ИЗВЛЕЧЕНИЕ ОСТАЛЬНЫХ ДИАПАЗОНОВ (ОПЦИОНАЛЬНЫЕ) ===
        if len(fee_selectors) > 1:
            logger.info(f"🔍 Extracting optional ranges [2..{len(fee_selectors)}]")
            
            for i in range(1, len(fee_selectors)):
                fee_sel = fee_selectors[i]
                threshold_sel = threshold_selectors[i]
                range_num = i + 1  # Нумерация с 1
                
                try:
                    logger.debug(f"🔍 [{range_num}] Fee selector: '{fee_sel}'")
                    logger.debug(f"🔍 [{range_num}] Threshold selector: '{threshold_sel}'")
                    
                    # Извлекаем fee (если селектор не null)
                    fee = None
                    if fee_sel is None or fee_sel == 'null':
                        fee = 0.0
                        fee_text = "Бесплатная доставка"
                        logger.debug(f"📝 [{range_num}] Fee selector is null, using fee=0.0")
                    else:
                        try:
                            if fee_sel.startswith('//'):
                                fee_element = driver.find_element(By.XPATH, fee_sel)
                            else:
                                fee_element = driver.find_element(By.CSS_SELECTOR, fee_sel)
                            fee_text = fee_element.text.strip()
                            fee = parse_delivery_fee(fee_text)
                        except Exception as fee_error:
                            logger.info(f"ℹ️ [{range_num}] Fee element not found (optional): {fee_error}")
                            fee = None
                    
                    # Если fee не найден - останавливаемся
                    if fee is None:
                        logger.info(f"🛑 Stopped at range [{range_num}] - fee element not found. Extracted {len(ranges_data)} ranges total.")
                        break
                    
                    # Извлекаем threshold
                    threshold = None
                    try:
                        if threshold_sel.startswith('//'):
                            threshold_element = driver.find_element(By.XPATH, threshold_sel)
                        else:
                            threshold_element = driver.find_element(By.CSS_SELECTOR, threshold_sel)
                        threshold_text = threshold_element.text.strip()
                        threshold = parse_delivery_info(threshold_text)
                    except Exception as threshold_error:
                        logger.info(f"ℹ️ [{range_num}] Threshold element not found (optional): {threshold_error}")
                        threshold = None
                    
                    # Если threshold не найден - останавливаемся
                    if threshold is None:
                        logger.info(f"🛑 Stopped at range [{range_num}] - threshold element not found. Extracted {len(ranges_data)} ranges total.")
                        break
                    
                    logger.debug(f"📝 [{range_num}] Fee text: '{fee_text}', Threshold text: '{threshold_text}'")
                    
                    ranges_data.append({
                        'fee': fee,
                        'threshold': threshold,
                        'fee_text': fee_text,
                        'threshold_text': threshold_text
                    })
                    
                    logger.info(f"✅ [{range_num}] Extracted optional range: fee={fee}₽, threshold={threshold}₽")
                    
                except Exception as item_error:
                    logger.info(f"ℹ️ [{range_num}] Optional range extraction failed (stopping): {item_error}")
                    logger.info(f"🛑 Stopped at range [{range_num}]. Extracted {len(ranges_data)} ranges total.")
                    break
        else:
            logger.info(f"ℹ️ Only 1 range selector provided - no optional ranges to extract")
        
        # Шаг 3: Закрыть модальное окно (если указан close_trigger)
        close_trigger = delivery_config.get('close_trigger', {})
        if close_trigger and close_trigger.get('selector'):
            try:
                close_selector = close_trigger['selector']
                logger.info(f"🔘 Closing modal with: {close_selector}")
                
                if close_selector.startswith('//'):
                    close_element = driver.find_element(By.XPATH, close_selector)
                else:
                    close_element = driver.find_element(By.CSS_SELECTOR, close_selector)
                close_element.click()
                
                logger.info(f"✅ Modal closed successfully")
                await asyncio.sleep(0.5)  # Пауза после закрытия
                
            except Exception as close_error:
                if not close_trigger.get('optional', False):
                    logger.error(f"❌ Error closing modal: {close_error}")
                else:
                    logger.debug(f"⚠️ Optional close trigger failed: {close_error}")
        
        logger.info(f"🎉 Successfully extracted {len(ranges_data)} delivery ranges")
        if min_order_amount is not None:
            logger.info(f"💰 Extracted min_order_amount: {min_order_amount}₽")
        return ranges_data, min_order_amount
        
    except Exception as e:
        logger.error(f"❌ Error extracting delivery ranges: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return ranges_data, min_order_amount
