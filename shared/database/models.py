from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean, Text, JSON, Numeric, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from shared.database.connection import Base
from shared.models.base import UserStatus, OrderStatus
import enum


# Добавляем новую таблицу для конфигурации ЛСД
class LSDConfig(Base):
    """Конфигурация локальных служб доставки"""
    __tablename__ = "lsd_configs"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)  # samokat, yandex_lavka, etc.
    display_name = Column(String(200), nullable=False)  # "Самокат", "Яндекс Лавка"
    base_url = Column(String(500), nullable=False)
    rpa_config = Column(JSON, nullable=True)  # Конфигурация RPA селекторов
    search_config_rpa = Column(JSON, nullable=True)  # Конфигурация селекторов для поиска товаров
    is_active = Column(Boolean, default=False)  # Включен ли ЛСД для использования
    is_mvp = Column(Boolean, default=False)  # Используется ли в MVP
    min_order_amount = Column(Numeric(10, 2), default=0)  # Минимальная сумма заказа (устарело)
    delivery_fixed_fee = Column(Numeric(10, 2), default=0, nullable=False)  # Фиксированная доплата за доставку
    delivery_cost_model = Column(JSON, nullable=True)  # Эталонная модель стоимости доставки с диапазонами
    regions = Column(JSON, default=list)  # Регионы, где доступен сервис ['moscow', 'spb']
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = "users"
    
    id = Column(BigInteger, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    sms_code = Column(String(10), nullable=True)  # Временное хранение SMS кода для авторизации
    address = Column(Text, nullable=True)
    apartment = Column(String(20), nullable=True)  # Номер квартиры
    delivery_details = Column(Text, nullable=True)
    region = Column(String(50), default='moscow')  # Добавляем регион пользователя
    over_order_percent = Column(Integer, default=50, nullable=False)  # Допустимое превышение заказа в %
    under_order_percent = Column(Integer, default=10, nullable=False)  # Допустимое недополучение заказа в %
    status = Column(Enum(UserStatus, native_enum=True, values_callable=lambda x: [e.value for e in x]), default=UserStatus.WAITING_CONTACT)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    orders = relationship("Order", back_populates="user")
    lsd_accounts = relationship("LSDAccount", back_populates="user")
    exclusion = relationship("UserExclusion", back_populates="user", uselist=False)


class Order(Base):
    __tablename__ = "orders"
    
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    telegram_message_id = Column(BigInteger, nullable=True)
    tg_group = Column(String(20), nullable=True)  # ID группы Telegram для отправки результатов
    original_list = Column(Text, nullable=False)
    normalized_list = Column(JSON, nullable=True)  # Serialized NormalizedOrder
    status = Column(Enum(OrderStatus, native_enum=True, values_callable=lambda x: [e.value for e in x]), default=OrderStatus.NEW)
    total_cost = Column(Numeric(10, 2), nullable=True)
    analysis_result = Column(JSON, nullable=True)
    failed_promotions = Column(JSON, nullable=True)  # Промокоды, которые не сработали
    
    # Допустимые отклонения заказа (наследуются от пользователя)
    over_order_percent = Column(Integer, nullable=True)  # % превышения от заказанного объема
    under_order_percent = Column(Integer, nullable=True)  # % недополучения от заказанного объема
    
    # Временные метки для отслеживания процесса
    analysis_started_at = Column(DateTime(timezone=True), nullable=True)
    analysis_completed_at = Column(DateTime(timezone=True), nullable=True)
    user_confirmation_at = Column(DateTime(timezone=True), nullable=True)
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    results_sent_at = Column(DateTime(timezone=True), nullable=True)  # Время отправки результатов пользователю
    
    # Обработка ошибок и повторы
    retry_count = Column(Integer, default=0)
    last_retry_reason = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="orders")
    basket_analyses = relationship("BasketAnalysis", back_populates="order")
    order_items = relationship("OrderItem", back_populates="order")
    order_baskets = relationship("OrderBasket", back_populates="order")
    lsd_stocks = relationship("LSDStock", back_populates="order")  # Добавлена связь


class LSDAccount(Base):
    __tablename__ = "lsd_accounts"
    
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    lsd_config_id = Column(BigInteger, ForeignKey("lsd_configs.id"), nullable=False)  # Ссылка на конфиг ЛСД
    auth_data = Column(Text, nullable=False)  # Encrypted JSON
    is_active = Column(Boolean, default=True)
    last_auth_check = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="lsd_accounts")
    lsd_config = relationship("LSDConfig")


class Promotion(Base):
    __tablename__ = "promotions"
    
    id = Column(BigInteger, primary_key=True, index=True)
    lsd_config_id = Column(BigInteger, ForeignKey("lsd_configs.id"), nullable=False)  # Ссылка на конфиг ЛСД
    code = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    conditions = Column(JSON, nullable=True)  # Условия применения
    discount_type = Column(String(50), nullable=False)  # percentage, fixed_amount, free_delivery
    discount_value = Column(Numeric(10, 2), nullable=False)
    valid_from = Column(DateTime(timezone=True), nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True)
    usage_limit = Column(Integer, nullable=True)
    current_usage = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    lsd_config = relationship("LSDConfig")


class ProductPrice(Base):
    __tablename__ = "product_prices"
    
    id = Column(BigInteger, primary_key=True, index=True)
    lsd_config_id = Column(BigInteger, ForeignKey("lsd_configs.id"), nullable=False)  # Ссылка на конфиг ЛСД
    product_name = Column(String(500), nullable=False)
    normalized_name = Column(String(500), nullable=False, index=True)
    price = Column(Numeric(10, 2), nullable=False)
    unit = Column(String(20), nullable=False)
    quantity_per_unit = Column(Numeric(10, 3), nullable=False)
    fprice = Column(Numeric(10, 2), nullable=False)  # цена за кг/л
    in_stock = Column(Boolean, default=True)
    collected_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    lsd_config = relationship("LSDConfig")


class BasketAnalysis(Base):
    __tablename__ = "basket_analyses"
    
    id = Column(BigInteger, primary_key=True, index=True)
    order_id = Column(BigInteger, ForeignKey("orders.id"), nullable=False)
    basket_id = Column(Integer, nullable=False)  # ID корзины
    total_loss = Column(Numeric(10, 2), default=0)
    total_goods_cost = Column(Numeric(10, 2), default=0)
    delivery_cost = Column(JSON, nullable=True)
    delivery_topup = Column(JSON, nullable=True)
    total_delivery_cost = Column(Numeric(10, 2), default=0)
    total_cost = Column(Numeric(10, 2), default=0)
    total_loss_and_delivery = Column(Numeric(10, 2), default=0)
    basket_rank = Column(Integer, nullable=True)
    is_mono_basket = Column(Boolean, default=False)  # Флаг моно-корзины
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    order = relationship("Order", back_populates="basket_analyses")


class UserSession(Base):
    """Хранение сессионных данных: куки для ЛСД и другие временные данные"""
    __tablename__ = "user_sessions"
    
    id = Column(BigInteger, primary_key=True, index=True)
    telegram_id = Column(BigInteger, index=True, nullable=False)
    
    # Прямая ссылка на LSD конфиг (для куки)
    lsd_config_id = Column(BigInteger, ForeignKey("lsd_configs.id"), nullable=True)
    
    # Альтернативное поле - для других типов сессий
    session_type = Column(String(50), nullable=True)  # registration, order_confirmation, etc.
    
    # Данные сессии
    data = Column(JSON, nullable=True)  # Куки, состояния регистрации, другие данные
    expires_at = Column(DateTime(timezone=True), nullable=False)
    user_name = Column(Text, nullable=True)  # Имя пользователя для отображения
    lsd_name = Column(String(100), nullable=True, index=True)  # Имя ЛСД (не display_name)
    default_delivery_address = Column(Text, nullable=True)  # Адрес доставки по умолчанию
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    lsd_config = relationship("LSDConfig")
    
    # Проверка целостности - одно из полей должно быть заполнено
    # __table_args__ = (
    #     CheckConstraint('lsd_config_id IS NOT NULL OR session_type IS NOT NULL'),
    # )


class OrderItem(Base):
    """Элементы заказа - продукты из списка пользователя"""
    __tablename__ = "order_items"
    
    id = Column(BigInteger, primary_key=True, index=True)
    order_id = Column(BigInteger, ForeignKey("orders.id"), nullable=False)
    original_text = Column(String(500), nullable=False)  # Оригинальный текст из сообщения
    product_name = Column(String(500), nullable=False)  # Нормализованное название
    requested_quantity = Column(Numeric(10, 3), nullable=False)  # Запрошенное количество
    requested_unit = Column(String(20), nullable=False)  # Единица измерения
    normalized_name = Column(String(500), nullable=False)  # Имя для поиска
    processing_status = Column(String(50), default='pending')  # pending, processed, failed
    
    # Поддержка альтернативных товаров (форель / семга)
    alternatives = Column(JSON, nullable=True)  # ['семга', 'лосось'] - список альтернатив
    is_alternative_group = Column(Boolean, default=False)  # True если есть альтернативы
    selected_alternative = Column(String(500), nullable=True)  # Выбранная альтернатива после оптимизации
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    order = relationship("Order")
    lsd_stocks = relationship("LSDStock", back_populates="order_item")


class LSDStock(Base):
    """Найденные товары в ЛСД - результаты поиска"""
    __tablename__ = "lsd_stocks"
    
    id = Column(BigInteger, primary_key=True, index=True)
    order_id = Column(BigInteger, ForeignKey("orders.id"), nullable=False, index=True)  # Добавлена прямая ссылка на заказ
    order_item_id = Column(BigInteger, ForeignKey("order_items.id"), nullable=False)
    lsd_config_id = Column(BigInteger, ForeignKey("lsd_configs.id"), nullable=False)
    
    # Найденные данные о товаре
    found_name = Column(String(500), nullable=False)  # Название в ЛСД
    found_unit = Column(String(20), nullable=False)  # Единица измерения в ЛСД
    found_quantity = Column(Numeric(10, 3), nullable=False)  # Количество в упаковке
    
    # Нормализованные единицы измерения
    base_unit = Column(String(20), nullable=False)  # Базовая единица (кг, л, шт)
    base_quantity = Column(Numeric(10, 3), nullable=False)  # Количество в базовых единицах
    
    # Цены
    price = Column(Numeric(10, 2), nullable=False)  # Цена как есть в ЛСД
    fprice = Column(Numeric(10, 2), nullable=False)  # Цена за кг/л/шт
    fprice_calculation = Column(Text, nullable=True)  # Текстовое описание формулы расчета fprice
    tprice = Column(Numeric(10, 2), nullable=True)  # Цена после применения промо
    
    # Условия доставки и заказа
    min_order_amount = Column(Numeric(10, 2), default=0)  # Минимальная сумма заказа (устарело, используется для обратной совместимости)
    delivery_cost = Column(Numeric(10, 2), default=0)  # Стоимость доставки (устарело, используется для обратной совместимости)
    delivery_cost_model = Column(JSON, nullable=True)  # Модель стоимости доставки с диапазонами
    
    # Доступность и мета-данные
    available_stock = Column(Integer, nullable=True)  # Доступное количество
    product_url = Column(String(1000), nullable=True)  # Полная ссылка на товар
    product_id_in_lsd = Column(String(100), nullable=True)  # ID товара в ЛСД
    
    # Данные поиска
    search_query = Column(String(500), nullable=True)  # Поисковый запрос
    search_result_position = Column(Integer, nullable=True)  # Позиция в результатах поиска
    is_exact_match = Column(Boolean, default=False)  # Точное совпадение
    match_score = Column(Numeric(5, 3), nullable=True)  # Оценка соответствия (0-1)
    
    # Поддержка альтернативных товаров
    is_alternative = Column(Boolean, default=False)  # True если это альтернатива
    alternative_for = Column(String(500), nullable=True)  # Для какого основного товара
    
    # Запрошенные данные от пользователя (наследуется от order_items)
    requested_quantity = Column(Numeric(10, 3), nullable=True)  # Запрошенное количество
    requested_unit = Column(String(20), nullable=True)  # Запрошенная единица измерения
    
    # Максимальное количество штук для оптимизации
    max_pieces = Column(Integer, nullable=True)  # Макс. кол-во штук товара для расчета
    
    # Расчетные поля для оптимизации заказа
    order_item_ids_quantity = Column(Integer, nullable=True)  # Сколько штук товара нужно заказать
    order_item_ids_cost = Column(Numeric(10, 2), nullable=True)  # Стоимость этого количества
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    order = relationship("Order", back_populates="lsd_stocks")  # Добавлена связь с заказом
    order_item = relationship("OrderItem", back_populates="lsd_stocks")
    lsd_config = relationship("LSDConfig")
    basket_items = relationship("OrderBasketItem", back_populates="lsd_stock")


class OrderBasket(Base):
    """Корзины заказов для каждого ЛСД"""
    __tablename__ = "order_baskets"
    
    id = Column(BigInteger, primary_key=True, index=True)
    order_id = Column(BigInteger, ForeignKey("orders.id"), nullable=False)
    lsd_config_id = Column(BigInteger, ForeignKey("lsd_configs.id"), nullable=False)
    
    # Финансовые данные
    subtotal = Column(Numeric(10, 2), nullable=False, default=0)  # Сумма товаров
    delivery_cost = Column(Numeric(10, 2), nullable=False, default=0)  # Стоимость доставки
    min_order_amount = Column(Numeric(10, 2), nullable=True)  # Минималка для этого ЛСД
    total_before_promo = Column(Numeric(10, 2), nullable=False)  # Сумма до промо
    promocode_discount = Column(Numeric(10, 2), default=0)  # Скидка по промо
    total_after_promo = Column(Numeric(10, 2), nullable=True)  # Итоговая сумма
    
    # Промокоды
    applied_promocodes = Column(JSON, default=list)  # Список примененных промо
    
    # Статус и мета-данные
    status = Column(String(50), default='draft')  # draft, optimized, confirmed, processing, completed
    promo_verification_status = Column(String(50), nullable=True)  # verified, failed, pending
    
    # Доставка
    delivery_address = Column(Text, nullable=True)
    delivery_time_slot = Column(String(100), nullable=True)
    
    # Интеграция с ЛСД
    cart_url = Column(String(1000), nullable=True)  # Ссылка на корзину в ЛСД
    order_id_in_lsd = Column(String(100), nullable=True)  # ID заказа в ЛСД
    
    # Аналитика
    optimization_score = Column(Numeric(5, 3), nullable=True)  # Оценка оптимальности
    savings_amount = Column(Numeric(10, 2), default=0)  # Сумма экономии
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    order = relationship("Order")
    lsd_config = relationship("LSDConfig")
    basket_items = relationship("OrderBasketItem", back_populates="order_basket")
    promocode_verifications = relationship("PromocodeVerification", back_populates="order_basket")


class OrderBasketItem(Base):
    """Элементы корзин - связка товаров с корзинами"""
    __tablename__ = "order_basket_items"
    
    id = Column(BigInteger, primary_key=True, index=True)
    order_basket_id = Column(BigInteger, ForeignKey("order_baskets.id"), nullable=False)
    lsd_stock_id = Column(BigInteger, ForeignKey("lsd_stocks.id"), nullable=False)
    
    # Заказываемые данные
    quantity_to_order = Column(Numeric(10, 3), nullable=False)  # Сколько заказываем
    unit_price = Column(Numeric(10, 2), nullable=False)  # Цена за единицу
    total_price = Column(Numeric(10, 2), nullable=False)  # Общая стоимость
    
    # Приоритет и замены
    is_priority = Column(Boolean, default=False)  # Приоритетный товар
    substitution_reason = Column(Text, nullable=True)  # Причина замены
    
    # Статус добавления в корзину ЛСД
    added_to_lsd_cart = Column(Boolean, default=False)
    add_to_cart_error = Column(Text, nullable=True)
    lsd_cart_item_id = Column(String(100), nullable=True)  # ID в корзине ЛСД
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    order_basket = relationship("OrderBasket", back_populates="basket_items")
    lsd_stock = relationship("LSDStock", back_populates="basket_items")


class PromocodeVerification(Base):
    """Проверка применения промокодов"""
    __tablename__ = "promocode_verifications"
    
    id = Column(BigInteger, primary_key=True, index=True)
    order_basket_id = Column(BigInteger, ForeignKey("order_baskets.id"), nullable=False)
    promotion_id = Column(BigInteger, ForeignKey("promotions.id"), nullable=True)
    
    # Данные промокода
    promocode = Column(String(100), nullable=False)
    expected_discount = Column(Numeric(10, 2), nullable=False)
    actual_discount = Column(Numeric(10, 2), nullable=True)
    price_difference_percent = Column(Numeric(5, 2), nullable=True)  # Процент расхождения
    
    # Статус проверки
    verification_status = Column(String(50), nullable=False)  # verified, failed, pending
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    marked_problematic = Column(Boolean, default=False)  # Проблемный промо
    
    # Детали проверки
    verification_details = Column(JSON, nullable=True)
    applied_at = Column(DateTime(timezone=True), server_default=func.now())
    verified_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    order_basket = relationship("OrderBasket", back_populates="promocode_verifications")
    promotion = relationship("Promotion")


class FoodCategory(Base):
    """Категории продуктов питания"""
    __tablename__ = "food_categories"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)  # "Молочные продукты"
    name_en = Column(String(100), nullable=True)  # "dairy"
    icon = Column(String(10), nullable=True)  # Emoji иконка
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    products = relationship("FoodProduct", back_populates="category")


class FoodProduct(Base):
    """Продукты питания с КБЖУ"""
    __tablename__ = "food_products"

    id = Column(BigInteger, primary_key=True, index=True)
    category_id = Column(BigInteger, ForeignKey("food_categories.id"), nullable=False)
    name = Column(String(200), nullable=False, index=True)  # "Молоко 2.5%"

    # Пищевая ценность на 100г
    calories = Column(Numeric(8, 2), nullable=False)  # ккал
    protein = Column(Numeric(6, 2), nullable=False)  # белки, г
    fat = Column(Numeric(6, 2), nullable=False)  # жиры, г
    carbs = Column(Numeric(6, 2), nullable=False)  # углеводы, г
    fiber = Column(Numeric(6, 2), default=0)  # клетчатка, г

    # Типичная порция
    unit = Column(String(20), default="г")  # г, мл, шт
    serving_size = Column(Numeric(8, 2), default=100)  # Размер порции

    # Мета
    is_active = Column(Boolean, default=True)
    source = Column(String(100), nullable=True)  # Источник данных
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    category = relationship("FoodCategory", back_populates="products")


class MealPlan(Base):
    """Планы питания пользователей"""
    __tablename__ = "meal_plans"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)

    # Целевые показатели в день
    target_calories = Column(Integer, nullable=False)  # Целевые калории
    target_protein = Column(Numeric(6, 2), nullable=True)  # Целевые белки
    target_fat = Column(Numeric(6, 2), nullable=True)  # Целевые жиры
    target_carbs = Column(Numeric(6, 2), nullable=True)  # Целевые углеводы

    # Период плана
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)  # null = бессрочно

    # Статус
    is_active = Column(Boolean, default=True)
    name = Column(String(200), nullable=True)  # "План на похудение"
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User")
    daily_logs = relationship("MealDailyLog", back_populates="meal_plan")


class MealDailyLog(Base):
    """Дневной журнал питания"""
    __tablename__ = "meal_daily_logs"

    id = Column(BigInteger, primary_key=True, index=True)
    meal_plan_id = Column(BigInteger, ForeignKey("meal_plans.id"), nullable=False, index=True)
    log_date = Column(DateTime(timezone=True), nullable=False, index=True)

    # Фактические показатели за день (рассчитываются автоматически)
    actual_calories = Column(Numeric(8, 2), default=0)
    actual_protein = Column(Numeric(6, 2), default=0)
    actual_fat = Column(Numeric(6, 2), default=0)
    actual_carbs = Column(Numeric(6, 2), default=0)

    # Прогресс
    calories_percent = Column(Numeric(5, 2), default=0)  # % от целевого
    is_completed = Column(Boolean, default=False)  # День завершён

    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    meal_plan = relationship("MealPlan", back_populates="daily_logs")
    entries = relationship("MealEntry", back_populates="daily_log")


class MealEntry(Base):
    """Записи приёмов пищи"""
    __tablename__ = "meal_entries"

    id = Column(BigInteger, primary_key=True, index=True)
    daily_log_id = Column(BigInteger, ForeignKey("meal_daily_logs.id"), nullable=False, index=True)
    food_product_id = Column(BigInteger, ForeignKey("food_products.id"), nullable=True)  # null для custom

    # Тип приёма пищи
    meal_type = Column(String(50), nullable=False)  # breakfast, lunch, dinner, snack

    # Данные о продукте (могут быть кастомные)
    product_name = Column(String(200), nullable=False)
    portion_size = Column(Numeric(8, 2), nullable=False)  # Размер порции
    portion_unit = Column(String(20), default="г")

    # Рассчитанные показатели для этой порции
    calories = Column(Numeric(8, 2), nullable=False)
    protein = Column(Numeric(6, 2), nullable=False)
    fat = Column(Numeric(6, 2), nullable=False)
    carbs = Column(Numeric(6, 2), nullable=False)

    # Мета
    is_custom = Column(Boolean, default=False)  # Кастомный продукт (не из базы)
    logged_at = Column(DateTime(timezone=True), server_default=func.now())

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    daily_log = relationship("MealDailyLog", back_populates="entries")
    food_product = relationship("FoodProduct")


class UserMessage(Base):
    """
    Логирование всех значимых сообщений в Telegram.
    
    Входящие сообщения:
    - Личные: команды, текстовые сообщения, контакты, коды
    - Группы: команды боту, заказы, callback от пользователей
    
    Исходящие сообщения:
    - Все сообщения от бота (в личку и в группы)
    """
    __tablename__ = "user_messages"
    
    id = Column(BigInteger, primary_key=True, index=True)
    
    # Связи
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    order_id = Column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Идентификаторы чата и сообщения
    chat_id = Column(String(50), nullable=False, index=True)  # String для Telegram chat IDs (могут быть отрицательные для групп)
    telegram_message_id = Column(BigInteger, nullable=True, index=True)  # ID сообщения в Telegram
    reply_to_telegram_message_id = Column(BigInteger, nullable=True)  # ID сообщения, на которое отвечаем
    
    # Типы и категории
    message_direction = Column(String(10), nullable=False, index=True)  # 'incoming' | 'outgoing'
    chat_type = Column(String(20), nullable=False, index=True)  # 'private' | 'group' | 'supergroup'
    message_category = Column(String(50), nullable=True, index=True)  # См. docstring для списка категорий
    
    # Содержимое сообщения
    message_text = Column(Text, nullable=True)  # Nullable для документов
    parse_mode = Column(String, nullable=True)
    disable_web_page_preview = Column(Boolean, nullable=True)
    
    # Поля для документов
    is_document = Column(Boolean, default=False)
    filename = Column(String(255), nullable=True)
    file_size = Column(Integer, nullable=True)  # В байтах
    
    # Ответ от Telegram API (для исходящих)
    response_status = Column(Integer, nullable=True)  # HTTP status code
    response_body = Column(JSON, nullable=True)  # Полный ответ от Telegram API
    error_message = Column(Text, nullable=True)
    
    # Дополнительные данные
    raw_update = Column(JSON, nullable=True)  # Полный update от Telegram (для входящих)
    is_significant = Column(Boolean, nullable=False, default=True)  # Значимость сообщения
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    user = relationship("User")
    order = relationship("Order")


class ExclusionCategory(Base):
    """Категории исключений продуктов (молочка, глютен, орехи и т.д.)"""
    __tablename__ = "exclusion_categories"

    id = Column(BigInteger, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)  # dairy, gluten, nuts, meat, etc.
    name = Column(String(100), nullable=False)  # "Молочные продукты", "Глютен"
    icon = Column(String(10), nullable=True)  # Emoji иконка
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    keywords = relationship("ExclusionKeyword", back_populates="category")


class ExclusionKeyword(Base):
    """Ключевые слова для определения категории продукта"""
    __tablename__ = "exclusion_keywords"

    id = Column(BigInteger, primary_key=True, index=True)
    category_id = Column(BigInteger, ForeignKey("exclusion_categories.id"), nullable=False, index=True)
    keyword = Column(String(100), nullable=False, index=True)  # молоко, сыр, творог, etc.
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    category = relationship("ExclusionCategory", back_populates="keywords")


class DietType(Base):
    """Типы диет (веган, вегетарианец, кето и т.д.)"""
    __tablename__ = "diet_types"

    id = Column(BigInteger, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)  # vegan, vegetarian, keto, etc.
    name = Column(String(100), nullable=False)  # "Веган", "Вегетарианец"
    description = Column(Text, nullable=True)
    icon = Column(String(10), nullable=True)  # Emoji иконка
    excluded_categories = Column(JSON, default=list)  # ["meat", "dairy", "eggs"] - коды категорий для исключения
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserExclusion(Base):
    """Настройки исключений пользователя"""
    __tablename__ = "user_exclusions"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # Тип питания (один активный, nullable = без ограничений)
    diet_type_code = Column(String(50), nullable=True)  # vegan, vegetarian, pescatarian, keto

    # Дополнительные категории исключений (JSON массив кодов)
    excluded_categories = Column(JSON, default=list)  # ["dairy", "gluten", "nuts"]

    # Пользовательский черный список продуктов (JSON массив)
    excluded_products = Column(JSON, default=list)  # ["креветки", "арахис"]

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="exclusion")
