from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List
import os


class Settings(BaseSettings):
    # Application
    app_name: str = "Korzinka"
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    environment: str = Field(default="development", env="ENVIRONMENT")
    secret_key: str = Field(..., env="SECRET_KEY")
    encryption_key: str = Field(..., env="ENCRYPTION_KEY")
    
    # Database
    database_url: str = Field(..., env="DATABASE_URL")
    redis_url: str = Field(..., env="REDIS_URL")
    
    # Telegram Bot
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    telegram_webhook_url: Optional[str] = Field(None, env="TELEGRAM_WEBHOOK_URL")
    authorized_telegram_groups: List[int] = Field(default=[], env="AUTHORIZED_TELEGRAM_GROUPS")
    ngrok_auth_token: Optional[str] = Field(None, env="NGROK_AUTH_TOKEN")
    
    # External APIs
    dadata_api_key: str = Field(..., env="DADATA_API_KEY")
    dadata_secret_key: str = Field(..., env="DADATA_SECRET_KEY")
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    
    # RPA
    chrome_binary_path: Optional[str] = Field(None, env="CHROME_BINARY_PATH")
    chromedriver_path: Optional[str] = Field(None, env="CHROMEDRIVER_PATH")
    rpa_headless: bool = Field(default=False, env="RPA_HEADLESS")
    rpa_debug: bool = Field(default=True, env="RPA_DEBUG")
    
    # RPA Parallel Search Settings
    max_concurrent_browsers: int = Field(default=3, env="MAX_CONCURRENT_BROWSERS")
    max_lsd_retries: int = Field(default=3, env="MAX_LSD_RETRIES")
    rpa_search_timeout_sec: int = Field(default=300, env="RPA_SEARCH_TIMEOUT_SEC")
    
    # RPA Search Delays (antibot protection)
    rpa_search_delay_sec: float = Field(default=1.0, env="RPA_SEARCH_DELAY_SEC")
    
    # Weight Product Auto-Detection
    weight_unit_price_threshold: int = Field(default=300, env="WEIGHT_UNIT_PRICE_THRESHOLD")
    weight_keywords: str = Field(default="вес,весовой,весовая", env="WEIGHT_KEYWORDS")
    
    @property
    def weight_keywords_list(self) -> List[str]:
        """Convert comma-separated keywords to list"""
        return [kw.strip() for kw in self.weight_keywords.split(',') if kw.strip()]
    
    # LSD URLs
    yandex_lavka_base_url: str = "https://lavka.yandex.ru"
    sbermarket_base_url: str = "https://sbermarket.ru"
    samokat_base_url: str = "https://samokat.ru"
    
    # Service ports (for microservices)
    telegram_bot_port: int = 8001
    user_service_port: int = 8002
    order_service_port: int = 8003
    rpa_service_port: int = 8004
    promotion_service_port: int = 8005
    
    # Monitoring
    prometheus_port: Optional[int] = Field(None, env="PROMETHEUS_PORT")
    sentry_dsn: Optional[str] = Field(None, env="SENTRY_DSN")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Игнорировать неизвестные переменные окружения


# Global settings instance
settings = Settings()
