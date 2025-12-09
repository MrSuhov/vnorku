import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from typing import Optional, Tuple
from telegram import Update
from config.settings import settings
from shared.utils.logging import get_logger

logger = get_logger(__name__)


class TelegramSecurityUtils:
    """Утилиты безопасности для Telegram бота"""
    
    @staticmethod
    def is_authorized_group(chat_id: int) -> bool:
        """Проверка, авторизована ли группа"""
        if not settings.authorized_telegram_groups:
            # Если список пуст, разрешаем все группы (для разработки)
            logger.warning("No authorized groups configured - allowing all groups")
            return True
        
        is_authorized = chat_id in settings.authorized_telegram_groups
        
        if not is_authorized:
            logger.warning(f"Unauthorized group access attempt: {chat_id}")
        
        return is_authorized
    
    @staticmethod
    def is_order_message(message_text: str) -> Tuple[bool, Optional[str]]:
        """
        Проверяет, является ли сообщение заказом
        
        Returns:
            (is_order, cleaned_text): кортеж из булевого значения и очищенного текста
        """
        if not message_text or not message_text.strip():
            return False, None
        
        lines = message_text.strip().split('\n')
        
        # Проверяем, что первая строка содержит "Заказ"
        if not lines or not lines[0].strip().lower().startswith('заказ'):
            return False, None
        
        # Убираем первую строку с "Заказ"
        if len(lines) <= 1:
            logger.warning("Order message contains only header, no products")
            return False, None
        
        # Склеиваем остальные строки
        cleaned_text = '\n'.join(lines[1:]).strip()
        
        if not cleaned_text:
            logger.warning("Order message is empty after removing header")
            return False, None
        
        logger.info(f"Valid order message detected, products: {len(lines[1:])} lines")
        return True, cleaned_text
    



class NGrokUtils:
    """Утилиты для работы с ngrok"""
    
    @staticmethod
    def setup_ngrok_tunnel(port: int = 8001) -> Optional[str]:
        """
        Настройка ngrok туннеля для webhook
        
        Returns:
            URL туннеля или None в случае ошибки
        """
        try:
            from pyngrok import ngrok, conf
            
            # Настройка ngrok если есть auth token
            if settings.ngrok_auth_token:
                ngrok.set_auth_token(settings.ngrok_auth_token)
                logger.info("Ngrok auth token configured")
            
            # Создание туннеля
            tunnel = ngrok.connect(port, "http")
            public_url = tunnel.public_url
            
            logger.info(f"Ngrok tunnel created: {public_url}")
            return public_url
            
        except ImportError:
            logger.error("pyngrok not installed. Install with: pip install pyngrok")
            return None
        except Exception as e:
            logger.error(f"Error setting up ngrok tunnel: {e}")
            return None
    
    @staticmethod
    def get_webhook_url(bot_token: str, ngrok_url: str) -> str:
        """
        Формирование URL для webhook
        
        Args:
            bot_token: токен бота
            ngrok_url: URL ngrok туннеля
            
        Returns:
            Полный URL для webhook
        """
        # Убираем префикс токена для безопасности в URL
        bot_id = bot_token.split(':')[0]
        webhook_path = f"/webhook/{bot_id}"
        
        return f"{ngrok_url}{webhook_path}"
    
    @staticmethod
    def close_tunnels():
        """Закрытие всех ngrok туннелей"""
        try:
            from pyngrok import ngrok
            ngrok.kill()
            logger.info("All ngrok tunnels closed")
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"Error closing ngrok tunnels: {e}")
