import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from typing import Optional
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from shared.database.connection import sync_engine
from shared.database.models import LSDConfig
from shared.utils.logging import get_logger

logger = get_logger(__name__)


class LSDService:
    """Сервис для работы с конфигурациями ЛСД"""
    

    @staticmethod
    async def get_lsd_by_name(name: str) -> Optional[LSDConfig]:
        """Получение ЛСД по имени"""
        try:
            Session = sessionmaker(bind=sync_engine)
            session = Session()
            
            try:
                lsd = session.query(LSDConfig).filter_by(name=name).first()
                return lsd
                
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Error getting LSD by name {name}: {e}")
            return None
