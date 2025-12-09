import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType
from shared.utils.logging import get_logger
from shared.models.base import UserStatus
from shared.database import get_async_session
from shared.database.models import LSDConfig
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx

logger = get_logger(__name__)

# ⚠️ ЭТОТ ФАЙЛ УСТАРЕЛ И НЕ ИСПОЛЬЗУЕТСЯ
# Используется handlers/registration_mock.py
# Оставлен для совместимости, но код закомментирован

"""
class RegistrationHandler:
    # ... старый код закомментирован ...
    pass
"""
