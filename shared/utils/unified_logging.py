"""
Унифицированная настройка логирования для всех сервисов Korzinka

КРИТИЧНО: Защита от дублирования логов на всех уровнях
"""
import logging
import sys
import os
from pathlib import Path
from typing import Set

# Единый формат для всех логов
LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Глобальный флаг инициализации логирования (на уровне процесса)
_logging_initialized = False

# Множество настроенных сервисов
_configured_services: Set[str] = set()


class DuplicateFilter(logging.Filter):
    """
    Фильтр для предотвращения дублирования идентичных сообщений
    Блокирует повторные логи с тем же содержимым в течение короткого времени
    """
    def __init__(self):
        super().__init__()
        self.last_log = {}
        self.time_threshold = 0.1  # 100мс - если одно и то же сообщение дважды за 100мс, это дубль
    
    def filter(self, record):
        import time
        
        # Создаём ключ из важных полей записи
        key = (record.levelno, record.msg, record.name, record.funcName, record.lineno)
        current_time = time.time()
        
        # Проверяем, было ли это сообщение недавно
        if key in self.last_log:
            if current_time - self.last_log[key] < self.time_threshold:
                # Дубликат - блокируем
                return False
        
        # Обновляем время последнего лога
        self.last_log[key] = current_time
        
        # Очищаем старые записи (старше 1 секунды)
        self.last_log = {k: v for k, v in self.last_log.items() if current_time - v < 1.0}
        
        return True


def setup_service_logging(service_name: str, level: int = logging.INFO, log_to_file: bool = True):
    """
    Настройка логирования для сервиса с МАКСИМАЛЬНОЙ защитой от дублирования
    
    Args:
        service_name: Имя сервиса (например, 'rpa-service')
        level: Уровень логирования (logging.INFO, logging.DEBUG и т.д.)
        log_to_file: Писать логи в файл
    """
    global _logging_initialized, _configured_services
    
    # === ЗАЩИТА 1: Проверка переменной окружения (защита от uvicorn reload) ===
    env_key = f'_LOGGING_SETUP_{service_name.upper().replace("-", "_")}'
    if os.environ.get(env_key):
        # Логирование уже настроено в этом процессе
        return logging.getLogger()
    
    # === ЗАЩИТА 2: Проверка глобальных флагов ===
    if _logging_initialized and service_name in _configured_services:
        return logging.getLogger()
    
    # Получаем root logger
    root_logger = logging.getLogger()
    
    # === ЗАЩИТА 3: Проверка существующих handlers по имени ===
    console_handler_name = f'{service_name}_console'
    file_handler_name = f'{service_name}_file'
    
    for handler in root_logger.handlers:
        if hasattr(handler, 'name') and handler.name in [console_handler_name, file_handler_name]:
            # Handler этого сервиса уже существует - выход
            os.environ[env_key] = '1'
            return root_logger
    
    # === РАДИКАЛЬНАЯ ОЧИСТКА: Удаляем ВСЕ существующие handlers ===
    handlers_count = len(root_logger.handlers)
    if handlers_count > 0:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            try:
                handler.close()
            except:
                pass
    
    # Устанавливаем уровень логирования
    root_logger.setLevel(level)
    
    # Создаем formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    
    # Создаём фильтр дубликатов
    duplicate_filter = DuplicateFilter()
    
    # === Console handler ===
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    console_handler.name = console_handler_name
    console_handler.addFilter(duplicate_filter)  # Добавляем фильтр дубликатов
    root_logger.addHandler(console_handler)
    
    # === File handler (опционально) ===
    if log_to_file:
        log_dir = Path(__file__).parent.parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f'{service_name}.log'
        
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        file_handler.name = file_handler_name
        file_handler.addFilter(duplicate_filter)  # Добавляем фильтр дубликатов
        root_logger.addHandler(file_handler)
    
    # Настраиваем уровни для внешних библиотек
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('selenium').setLevel(logging.WARNING)
    logging.getLogger('undetected_chromedriver').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Отключаем propagate для SQLAlchemy
    sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')
    sqlalchemy_logger.propagate = False
    
    # Отмечаем сервис как настроенный
    _configured_services.add(service_name)
    _logging_initialized = True
    
    # Устанавливаем переменную окружения
    os.environ[env_key] = '1'
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Получить logger с защитой от дублирования
    
    Используйте эту функцию вместо logging.getLogger(__name__)
    """
    return logging.getLogger(name)
