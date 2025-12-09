#!/usr/bin/env python3
"""
Скрипт для создания и применения миграций базы данных
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic.config import Config
from alembic import command
from shared.database.connection import sync_engine, Base
from shared.utils.logging import setup_logging, get_logger

logger = setup_logging()


def create_migration(message: str):
    """Создание новой миграции"""
    alembic_cfg = Config("alembic.ini")
    command.revision(alembic_cfg, message=message, autogenerate=True)
    logger.info(f"Created migration: {message}")


def apply_migrations():
    """Применение всех миграций"""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    logger.info("Applied all migrations")


def create_all_tables():
    """Создание всех таблиц (для разработки)"""
    Base.metadata.create_all(bind=sync_engine)
    logger.info("Created all tables")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python migrate.py create 'migration message'")
        print("  python migrate.py apply")
        print("  python migrate.py create-tables")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "create":
        if len(sys.argv) < 3:
            print("Please provide migration message")
            sys.exit(1)
        create_migration(sys.argv[2])
    elif command == "apply":
        apply_migrations()
    elif command == "create-tables":
        create_all_tables()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
