from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal


class UserStatus(str, Enum):
    WAITING_CONTACT = "waiting_contact"
    WAITING_ADDRESS = "waiting_address"
    WAITING_APARTMENT = "waiting_apartment"
    ACTIVE = "active"
    BLOCKED = "blocked"


class OrderStatus(str, Enum):
    NEW = "new"
    ANALYZING = "analyzing"
    ANALYSIS_COMPLETE = "analysis_complete"
    OPTIMIZING = "optimizing"  # Оптимизация запущена
    OPTIMIZED = "optimized"  # Оптимизация завершена
    RESULTS_SENT = "results_sent"  # Результаты отправлены пользователю
    CONFIRMED = "confirmed"  # Пользователь подтвердил заказ
    CREATING_ORDERS = "creating_orders"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Модель для конфигурации ЛСД
class LSDConfigModel(BaseModel):
    id: Optional[int] = None
    name: str  # samokat, yandex_lavka, etc.
    display_name: str  # "Самокат", "Яндекс Лавка"
    base_url: str
    rpa_config: Optional[Dict[str, Any]] = None
    is_active: bool = False
    is_mvp: bool = False
    min_order_amount: Decimal = Decimal("0")
    delivery_fixed_fee: Decimal = Decimal("0")  # Фиксированная доплата за доставку
    regions: List[str] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# Base models
class User(BaseModel):
    id: Optional[int] = None
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    delivery_details: Optional[str] = None
    region: str = "moscow"  # Добавляем регион
    status: UserStatus = UserStatus.WAITING_CONTACT
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Product(BaseModel):
    name: str
    quantity: float
    unit: str  # кг, л, шт, упак
    original_text: str  # оригинальный текст из сообщения


class NormalizedOrder(BaseModel):
    products: List[Product]
    original_text: str
    confidence_score: float = 0.0  # насколько уверены в парсинге


class Order(BaseModel):
    id: Optional[int] = None
    user_id: int
    telegram_message_id: Optional[int] = None
    original_list: str
    normalized_list: Optional[NormalizedOrder] = None
    status: OrderStatus = OrderStatus.NEW
    total_cost: Optional[Decimal] = None
    analysis_result: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LSDAccount(BaseModel):
    id: Optional[int] = None
    user_id: int
    lsd_config_id: int  # Ссылка на конфиг ЛСД вместо enum
    auth_data: Dict[str, Any]  # зашифрованные cookies/tokens
    is_active: bool = True
    last_auth_check: Optional[datetime] = None
    created_at: Optional[datetime] = None


class Promotion(BaseModel):
    id: Optional[int] = None
    lsd_config_id: int  # Ссылка на конфиг ЛСД
    code: str
    description: str
    conditions: Dict[str, Any]  # минимальная сумма, категории товаров и т.д.
    discount_type: str  # percentage, fixed_amount, free_delivery
    discount_value: float
    valid_from: datetime
    valid_until: datetime
    is_active: bool = True
    usage_limit: Optional[int] = None
    current_usage: int = 0
    created_at: Optional[datetime] = None


class ProductPrice(BaseModel):
    lsd_config_id: int  # Ссылка на конфиг ЛСД
    product_name: str
    normalized_name: str
    price: Decimal
    unit: str
    quantity_per_unit: float
    fprice: Decimal  # цена за кг/л
    in_stock: bool = True
    collected_at: datetime


class BasketItem(BaseModel):
    product: Product
    lsd_config_id: int  # Ссылка на конфиг ЛСД
    price: Decimal
    fprice: Decimal
    tprice: Decimal  # цена после применения промокода
    promotion_applied: Optional[str] = None


class BasketAnalysis(BaseModel):
    id: Optional[int] = None
    order_id: int
    lsd_breakdown: Dict[int, List[BasketItem]]  # lsd_config_id -> items
    total_cost: Decimal
    total_savings: Decimal
    delivery_costs: Dict[int, Decimal]  # lsd_config_id -> cost
    applied_promotions: List[str]
    created_at: Optional[datetime] = None


# API Response models
class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    message: Optional[str] = None
    error: Optional[str] = None


class TelegramCallbackData(BaseModel):
    action: str
    order_id: Optional[int] = None
    user_id: Optional[int] = None
    data: Optional[Dict[str, Any]] = None


# Дополнительные модели для новых таблиц
class OrderItem(BaseModel):
    id: Optional[int] = None
    order_id: int
    original_text: str
    product_name: str
    requested_quantity: Decimal
    requested_unit: str
    normalized_name: str
    processing_status: str = "pending"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LSDStock(BaseModel):
    id: Optional[int] = None
    order_item_id: int
    lsd_config_id: int
    found_name: str
    found_unit: str
    found_quantity: Decimal
    price: Decimal
    fprice: Decimal
    tprice: Optional[Decimal] = None
    available_stock: Optional[int] = None
    product_url: Optional[str] = None
    product_id_in_lsd: Optional[str] = None
    search_query: Optional[str] = None
    search_result_position: Optional[int] = None
    is_exact_match: bool = False
    match_score: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OrderBasket(BaseModel):
    id: Optional[int] = None
    order_id: int
    lsd_config_id: int
    subtotal: Decimal = Decimal("0")
    delivery_cost: Decimal = Decimal("0")
    min_order_amount: Optional[Decimal] = None
    total_before_promo: Decimal
    promocode_discount: Decimal = Decimal("0")
    total_after_promo: Optional[Decimal] = None
    applied_promocodes: List[str] = []
    status: str = "draft"
    promo_verification_status: Optional[str] = None
    delivery_address: Optional[str] = None
    delivery_time_slot: Optional[str] = None
    cart_url: Optional[str] = None
    order_id_in_lsd: Optional[str] = None
    optimization_score: Optional[Decimal] = None
    savings_amount: Decimal = Decimal("0")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OrderBasketItem(BaseModel):
    id: Optional[int] = None
    order_basket_id: int
    lsd_stock_id: int
    quantity_to_order: Decimal
    unit_price: Decimal
    total_price: Decimal
    is_priority: bool = False
    substitution_reason: Optional[str] = None
    added_to_lsd_cart: bool = False
    add_to_cart_error: Optional[str] = None
    lsd_cart_item_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PromocodeVerification(BaseModel):
    id: Optional[int] = None
    order_basket_id: int
    promotion_id: Optional[int] = None
    promocode: str
    expected_discount: Decimal
    actual_discount: Optional[Decimal] = None
    price_difference_percent: Optional[Decimal] = None
    verification_status: str
    error_message: Optional[str] = None
    retry_count: int = 0
    marked_problematic: bool = False
    verification_details: Optional[Dict[str, Any]] = None
    applied_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
