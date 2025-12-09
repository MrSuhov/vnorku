#!/usr/bin/env python3
"""Миграция cookies из БД в файлы"""

import sys
import os

# Устанавливаем путь к корню проекта
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

# Загружаем .env из корня проекта
from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, '.env'))

import asyncio
import logging
from sqlalchemy import select
from datetime import datetime
from shared.database import get_async_session
from shared.database.models import UserSession, LSDConfig
from cookie_file_manager import cookie_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_cookies():
    """Миграция всех cookies из БД в файлы"""
    
    logger.info("🚀 Starting cookie migration from DB to files...")
    
    migrated_count = 0
    error_count = 0
    skipped_count = 0
    
    async for db in get_async_session():
        try:
            # Получаем все сессии с cookies
            result = await db.execute(
                select(UserSession, LSDConfig)
                .join(LSDConfig, UserSession.lsd_config_id == LSDConfig.id)
                .where(UserSession.data.isnot(None))
            )
            
            sessions = result.all()
            logger.info(f"📦 Found {len(sessions)} sessions to check")
            
            for session, lsd_config in sessions:
                try:
                    # Проверяем, что это не ссылка на файл (уже мигрировано)
                    if 'cookie_file' in session.data:
                        logger.debug(f"⏭️ Skipping session {session.id}: already migrated")
                        skipped_count += 1
                        continue
                    
                    cookies = session.data.get('cookies', [])
                    if not cookies:
                        logger.debug(f"⏭️ Skipping session {session.id}: no cookies")
                        skipped_count += 1
                        continue
                    
                    # Сохраняем в файл
                    success, cookie_file_path = await cookie_manager.save_cookies(
                        telegram_id=session.telegram_id,
                        lsd_name=lsd_config.name,
                        lsd_config_id=lsd_config.id,
                        cookies=cookies,
                        metadata={
                            'default_delivery_address': session.default_delivery_address,
                            'migrated_from_db': True,
                            'migration_date': datetime.now().isoformat()
                        }
                    )
                    
                    if success:
                        # Обновляем БД - заменяем данные ссылкой на файл
                        session.data = {
                            "cookie_file": cookie_file_path,
                            "cookie_count": len(cookies),
                            "last_updated": datetime.now().isoformat(),
                            "migrated_at": datetime.now().isoformat()
                        }
                        session.updated_at = datetime.now()
                        
                        migrated_count += 1
                        logger.info(f"✅ Migrated session {session.id}: user {session.telegram_id} @ {lsd_config.name} ({len(cookies)} cookies)")
                    else:
                        error_count += 1
                        logger.error(f"❌ Failed to migrate session {session.id}")
                        
                except Exception as e:
                    error_count += 1
                    logger.error(f"❌ Error migrating session {session.id}: {e}")
                    continue
            
            # Сохраняем изменения в БД
            await db.commit()
            
            logger.info(f"""
╔═══════════════════════════════════╗
║   MIGRATION SUMMARY               ║
╠═══════════════════════════════════╣
║ ✅ Migrated:  {migrated_count:3d}               ║
║ ⏭️  Skipped:   {skipped_count:3d}               ║
║ ❌ Errors:    {error_count:3d}               ║
║ 📊 Total:     {len(sessions):3d}               ║
╚═══════════════════════════════════╝
            """)
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            import traceback
            logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(migrate_cookies())
