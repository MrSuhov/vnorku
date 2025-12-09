"""
Инициализация пустых сессий перед авторизацией
"""

import logging
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

async def create_initial_session(telegram_id: int, lsd_config_id: int, lsd_name: str) -> bool:
    """
    Создает пустую сессию ДО начала авторизации
    Это позволяет шагу save_address записать адрес в уже существующую сессию
    """
    try:
        from shared.database import get_async_session
        from shared.database.models import UserSession, User
        from sqlalchemy import select
        
        logger.info(f"🔧 Creating initial session for user {telegram_id}, lsd_config_id={lsd_config_id}")
        
        async for db in get_async_session():
            # Проверяем, существует ли уже сессия
            result = await db.execute(
                select(UserSession).where(
                    UserSession.telegram_id == telegram_id,
                    UserSession.lsd_config_id == lsd_config_id
                )
            )
            existing_session = result.scalar_one_or_none()
            
            if existing_session:
                logger.info(f"✅ Session already exists (id={existing_session.id}), skipping creation")
                return True
            
            # Получаем информацию о пользователе
            user_result = await db.execute(
                select(User.first_name, User.last_name, User.address).where(User.telegram_id == telegram_id)
            )
            user_data = user_result.first()
            
            if user_data:
                first_name, last_name, address = user_data
                user_name = f"{first_name or ''} {last_name or ''}".strip() or f"User {telegram_id}"
            else:
                user_name = f"User {telegram_id}"
                address = None
            
            # Создаем сессию с null data - куки будут добавлены позже
            # ВАЖНО: data=None, а не data={} чтобы не создавать пустые записи
            expires_at = datetime.now() + timedelta(days=30)
            
            new_session = UserSession(
                telegram_id=telegram_id,
                lsd_config_id=lsd_config_id,
                data=None,  # None вместо {} - куки будут добавлены после авторизации
                expires_at=expires_at,
                user_name=user_name,
                lsd_name=lsd_name,
                default_delivery_address=address
            )
            
            db.add(new_session)
            await db.commit()
            
            logger.info(f"✅ Created initial empty session (id={new_session.id}) for user {telegram_id}")
            logger.info(f"   user_name='{user_name}', lsd_name='{lsd_name}'")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Error creating initial session: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def update_session_with_cookies(telegram_id: int, lsd_config_id: int, cookies: list, local_storage: dict = None, session_storage: dict = None) -> bool:
    """
    Сохранение cookies + localStorage + sessionStorage после успешной авторизации в файловую систему + обновление БД
    """
    try:
        from shared.database import get_async_session
        from shared.database.models import UserSession, LSDConfig
        from sqlalchemy import select
        
        logger.info(f"🍪 Saving {len(cookies)} cookies for user {telegram_id}")
        
        # Получаем lsd_name
        async for db in get_async_session():
            result = await db.execute(
                select(LSDConfig.name).where(LSDConfig.id == lsd_config_id)
            )
            lsd_name = result.scalar_one_or_none()
        
        if not lsd_name:
            logger.error(f"❌ Cannot save cookies: lsd_name not found for lsd_config_id={lsd_config_id}")
            return False
        
        # Используем функцию сохранения из main.py
        from main import save_user_cookies
        
        success = await save_user_cookies(
            telegram_id=telegram_id,
            lsd_name=lsd_name,
            lsd_config_id=lsd_config_id,
            cookies=cookies,
            local_storage=local_storage,
            session_storage=session_storage,
            metadata={
                'auth_completed': True,
                'auth_timestamp': datetime.now().isoformat()
            }
        )
        
        if success:
            logger.info(f"✅ Session cookies saved for user {telegram_id} @ {lsd_name}")
        else:
            logger.error(f"❌ Failed to save session cookies for user {telegram_id} @ {lsd_name}")
        
        return success
            
    except Exception as e:
        logger.error(f"❌ Error updating session with cookies: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
