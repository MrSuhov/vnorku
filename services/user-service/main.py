import asyncio
import sys
import os
import logging

# Добавляем корневую папку проекта в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from config.settings import settings
from shared.utils.unified_logging import setup_service_logging
from shared.database import get_async_session, User as DBUser
from shared.database.models import LSDAccount, UserSession, UserExclusion, ExclusionCategory, ExclusionKeyword, DietType
from shared.models.base import User, UserStatus, APIResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from sqlalchemy import select, update, func
from datetime import datetime, timedelta
import uvicorn
import httpx

setup_service_logging('user-service', level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Korzinka User Service",
    description="Сервис управления пользователями",
    version="1.0.0"
)


# Модели запросов
class CreateUserRequest(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UpdateUserRequest(BaseModel):
    phone: Optional[str] = None
    address: Optional[str] = None
    apartment: Optional[str] = None
    delivery_details: Optional[str] = None
    status: Optional[UserStatus] = None


@app.post("/users/pre-register")
async def pre_register_user(
    request: CreateUserRequest,
    db: AsyncSession = Depends(get_async_session)
):
    """Предрегистрация пользователя после команды /initiate"""
    try:
        # Проверяем, существует ли пользователь
        existing_user = await db.execute(
            select(DBUser).where(DBUser.telegram_id == request.telegram_id)
        )
        user = existing_user.scalar_one_or_none()
        
        if user:
            return APIResponse(
                success=False,
                message="Пользователь уже существует"
            )
        
        # Создаем нового пользователя
        new_user = DBUser(
            telegram_id=request.telegram_id,
            username=request.username,
            first_name=request.first_name,
            last_name=request.last_name,
            status=UserStatus.WAITING_CONTACT
        )
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        logger.info(f"Pre-registered user {request.telegram_id}")
        
        return APIResponse(
            success=True,
            data={"id": new_user.id, "status": new_user.status},
            message="Пользователь предварительно зарегистрирован"
        )
        
    except Exception as e:
        logger.error(f"Error pre-registering user {request.telegram_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка регистрации"
        )


@app.get("/users/{telegram_id}")
async def get_user(telegram_id: int, db: AsyncSession = Depends(get_async_session)):
    """Получение информации о пользователе"""
    try:
        result = await db.execute(
            select(DBUser).where(DBUser.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден"
            )
        
        user_data = {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "address": user.address,
            "delivery_details": user.delivery_details,
            "status": user.status,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None
        }
        
        return APIResponse(success=True, data=user_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user {telegram_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения пользователя"
        )



# Модели запросов
class CreateLSDAccountRequest(BaseModel):
    lsd_config_id: int
    phone: str
    session_data: Dict[str, Any]


@app.post("/users/{telegram_id}/lsd-accounts/complete-auth")
async def complete_lsd_auth(
    telegram_id: int,
    request: Dict[str, Any],
    db: AsyncSession = Depends(get_async_session)
):
    """Завершение RPA авторизации - ожидание, сохранение куки"""
    try:
        lsd_config_id = request.get("lsd_config_id")
        if not lsd_config_id:
            raise HTTPException(status_code=400, detail="lsd_config_id обязателен")
        
        # Получаем пользователя
        result = await db.execute(
            select(DBUser).where(DBUser.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Получаем конфигурацию ЛСД
        from shared.database.models import LSDConfig
        lsd_result = await db.execute(
            select(LSDConfig).where(LSDConfig.id == lsd_config_id)
        )
        lsd_config = lsd_result.scalar_one_or_none()
        if not lsd_config:
            raise HTTPException(status_code=404, detail="Конфигурация ЛСД не найдена")
        
        # 🔄 Завершаем RPA авторизацию с ожиданием и сохранением куки
        from shared.rpa.lsd_authenticator import LSDAuthenticatorFactory
        import os
        
        # Параметры RPA из переменных окружения
        rpa_headless = os.getenv("RPA_HEADLESS", "false").lower() == "true"
        rpa_debug = os.getenv("RPA_DEBUG", "true").lower() == "true"
        
        authenticator = LSDAuthenticatorFactory.create(
            lsd_config.name, 
            {
                "id": lsd_config.id,
                "name": lsd_config.name,
                "display_name": lsd_config.display_name,
                "base_url": lsd_config.base_url,
                "rpa_config": lsd_config.rpa_config or {}
            },
            headless=rpa_headless,
            debug=rpa_debug
        )
        
        # 🔄 Завершаем авторизацию (ожидание + сохранение куки + закрытие браузера)
        completion_result = await authenticator.complete_authentication(user.id)
        
        logger.info(f"Completed LSD auth for user {telegram_id}, LSD {lsd_config_id}")
        
        return APIResponse(
            success=completion_result.get("success", False),
            data=completion_result,
            message=completion_result.get("message", "Завершение авторизации")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing LSD auth for user {telegram_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Ошибка завершения авторизации"
        )

@app.post("/users/{telegram_id}/lsd-accounts/start-auth")
async def start_lsd_auth(
    telegram_id: int,
    request: Dict[str, Any],
    db: AsyncSession = Depends(get_async_session)
):
    """Запуск RPA авторизации в ЛСД"""
    try:
        lsd_config_id = request.get("lsd_config_id")
        if not lsd_config_id:
            raise HTTPException(status_code=400, detail="lsd_config_id обязателен")
        # Находим пользователя
        result = await db.execute(
            select(DBUser).where(DBUser.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Получаем конфигурацию ЛСД
        from shared.database.models import LSDConfig
        lsd_result = await db.execute(
            select(LSDConfig).where(LSDConfig.id == lsd_config_id)
        )
        lsd_config = lsd_result.scalar_one_or_none()
        
        if not lsd_config:
            raise HTTPException(status_code=404, detail="Конфигурация ЛСД не найдена")
        
        # Запускаем RPA авторизацию
        from shared.rpa.lsd_authenticator import LSDAuthenticatorFactory
        import os
        
        # Параметры RPA из переменных окружения
        rpa_headless = os.getenv("RPA_HEADLESS", "false").lower() == "true"  # По умолчанию ВИЗУАЛЬНЫЙ
        rpa_debug = os.getenv("RPA_DEBUG", "true").lower() == "true"        # По умолчанию DEBUG
        
        logger.info(f"RPA config: headless={rpa_headless}, debug={rpa_debug}")
        
        authenticator = LSDAuthenticatorFactory.create(
            lsd_config.name, 
            {
                "id": lsd_config.id,
                "name": lsd_config.name,
                "display_name": lsd_config.display_name,
                "base_url": lsd_config.base_url,
                "rpa_config": lsd_config.rpa_config or {}
            },
            headless=rpa_headless,
            debug=rpa_debug
        )
        
        # Проверяем, есть ли телефон у пользователя
        if not user.phone:
            raise HTTPException(
                status_code=400, 
                detail="У пользователя не указан номер телефона. Сначала завершите регистрацию."
            )
        
        # Запускаем RPA авторизацию - ТОЛЬКО генерируем QR, НЕ ждем завершения
        auth_result = await authenticator.authenticate(user.phone, user_id=user.id)
        
        if not auth_result.get("success"):
            logger.error(f"Failed to generate QR for user {telegram_id}, LSD {lsd_config_id}")
            return APIResponse(
                success=False,
                message="Ошибка генерации QR кода"
            )
        
        # 🔄 В фоновом режиме запускаем ожидание авторизации и сохранение кук
        if auth_result.get("auth_type") != "qr_code_mock":
            # Для реального RPA запускаем completion в фоне
            import asyncio
            asyncio.create_task(
                authenticator.complete_authentication(user.id, telegram_id=telegram_id)
            )
            logger.info(f"🔄 Background authentication completion started for user {telegram_id}")
        
        logger.info(f"Started LSD auth for user {telegram_id}, LSD {lsd_config_id}")
        
        return APIResponse(
            success=auth_result.get("success", False),
            data=auth_result,
            message=auth_result.get("message", "Ошибка авторизации")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting LSD auth for user {telegram_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Ошибка запуска авторизации"
        )


@app.post("/users/{telegram_id}/lsd-accounts")
async def create_lsd_account(
    telegram_id: int,
    request: CreateLSDAccountRequest,
    db: AsyncSession = Depends(get_async_session)
):
    """Создание LSD аккаунта для пользователя"""
    try:
        # Находим пользователя
        result = await db.execute(
            select(DBUser).where(DBUser.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Проверяем, нет ли уже такого аккаунта
        existing_result = await db.execute(
            select(LSDAccount).where(
                LSDAccount.user_id == user.id,
                LSDAccount.lsd_config_id == request.lsd_config_id
            )
        )
        existing_account = existing_result.scalar_one_or_none()
        
        if existing_account:
            # Обновляем существующий
            existing_account.phone = request.phone
            existing_account.session_data = request.session_data
            existing_account.is_active = True
            # updated_at обновляется автоматически через триггер БД
        else:
            # Создаём новый
            new_account = LSDAccount(
                user_id=user.id,
                lsd_config_id=request.lsd_config_id,
                phone=request.phone,
                session_data=request.session_data,
                is_active=True
            )
            db.add(new_account)
        
        await db.commit()
        
        logger.info(f"Created/updated LSD account for user {telegram_id}, LSD {request.lsd_config_id}")
        
        return APIResponse(
            success=True,
            data={
                "lsd_config_id": request.lsd_config_id,
                "phone": request.phone,
                "is_active": True
            },
            message="LSD аккаунт создан/обновлён"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating LSD account for user {telegram_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Ошибка создания LSD аккаунта"
        )


@app.patch("/users/{telegram_id}")
async def update_user(
    telegram_id: int,
    request: UpdateUserRequest,
    db: AsyncSession = Depends(get_async_session)
):
    """Обновление информации о пользователе"""
    try:
        # Получаем пользователя
        result = await db.execute(
            select(DBUser).where(DBUser.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден"
            )
        
        # Подготавливаем данные для обновления
        update_data = {}
        if request.phone is not None:
            update_data["phone"] = request.phone
        if request.address is not None:
            # Валидируем адрес через DaData если он указан
            if request.address.strip():
                is_valid = await validate_address(request.address)
                if not is_valid:
                    return APIResponse(
                        success=False,
                        message="Адрес не найден. Уточните адрес."
                    )
            update_data["address"] = request.address
        if request.apartment is not None:
            update_data["apartment"] = request.apartment
        if request.delivery_details is not None:
            update_data["delivery_details"] = request.delivery_details
        if request.status is not None:
            update_data["status"] = request.status
        
        # Обновляем пользователя
        if update_data:
            await db.execute(
                update(DBUser)
                .where(DBUser.telegram_id == telegram_id)
                .values(**update_data)
            )
            await db.commit()
        
        logger.info(f"Updated user {telegram_id} with data: {update_data}")
        
        return APIResponse(
            success=True,
            message="Пользователь обновлен"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user {telegram_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка обновления пользователя"
        )


async def validate_address(address: str) -> bool:
    """Валидация адреса через DaData API"""
    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Token {settings.dadata_api_key}",
                "X-Secret": settings.dadata_secret_key,
                "Content-Type": "application/json"
            }
            
            data = {"query": address}
            
            response = await client.post(
                "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address",
                json=data,
                headers=headers,
                timeout=10.0
            )
            
            if response.status_code == 200:
                result = response.json()
                suggestions = result.get("suggestions", [])
                
                # Считаем адрес валидным, если DaData нашел хотя бы одно предложение
                return len(suggestions) > 0
            else:
                logger.error(f"DaData API error: {response.status_code}")
                return True  # В случае ошибки API считаем адрес валидным
                
    except Exception as e:
        logger.error(f"Error validating address: {e}")
        return True  # В случае ошибки считаем адрес валидным


# ============================================================================
# ЭНДПОИНТЫ ИСКЛЮЧЕНИЙ ПРОДУКТОВ
# ============================================================================

class UpdateExclusionsRequest(BaseModel):
    """Модель запроса для обновления исключений пользователя"""
    diet_type_code: Optional[str] = None
    excluded_categories: Optional[List[str]] = None
    excluded_products: Optional[List[str]] = None


@app.get("/exclusions/categories")
async def get_exclusion_categories(db: AsyncSession = Depends(get_async_session)):
    """Получить список всех категорий исключений с ключевыми словами"""
    try:
        result = await db.execute(
            select(ExclusionCategory)
            .where(ExclusionCategory.is_active == True)
            .order_by(ExclusionCategory.sort_order)
        )
        categories = result.scalars().all()

        categories_data = []
        for cat in categories:
            # Получаем ключевые слова для категории
            keywords_result = await db.execute(
                select(ExclusionKeyword)
                .where(
                    ExclusionKeyword.category_id == cat.id,
                    ExclusionKeyword.is_active == True
                )
            )
            keywords = [kw.keyword for kw in keywords_result.scalars().all()]

            categories_data.append({
                "code": cat.code,
                "name": cat.name,
                "icon": cat.icon,
                "keywords": keywords
            })

        return APIResponse(success=True, data=categories_data)

    except Exception as e:
        logger.error(f"Error getting exclusion categories: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения категорий")


@app.get("/exclusions/diet-types")
async def get_diet_types(db: AsyncSession = Depends(get_async_session)):
    """Получить список всех типов диет"""
    try:
        result = await db.execute(
            select(DietType)
            .where(DietType.is_active == True)
            .order_by(DietType.sort_order)
        )
        diet_types = result.scalars().all()

        diet_types_data = [
            {
                "code": dt.code,
                "name": dt.name,
                "description": dt.description,
                "icon": dt.icon,
                "excluded_categories": dt.excluded_categories or []
            }
            for dt in diet_types
        ]

        return APIResponse(success=True, data=diet_types_data)

    except Exception as e:
        logger.error(f"Error getting diet types: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения типов диет")


@app.get("/users/{telegram_id}/exclusions")
async def get_user_exclusions(telegram_id: int, db: AsyncSession = Depends(get_async_session)):
    """Получить исключения пользователя"""
    try:
        # Находим пользователя
        user_result = await db.execute(
            select(DBUser).where(DBUser.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Получаем исключения
        exclusion_result = await db.execute(
            select(UserExclusion).where(UserExclusion.user_id == user.id)
        )
        exclusion = exclusion_result.scalar_one_or_none()

        if not exclusion:
            # Возвращаем пустые исключения
            return APIResponse(
                success=True,
                data={
                    "diet_type_code": None,
                    "diet_type_name": None,
                    "excluded_categories": [],
                    "excluded_products": [],
                    "all_excluded_categories": []  # Объединенные категории (диета + доп. категории)
                }
            )

        # Если есть тип диеты, получаем его данные
        diet_type_name = None
        diet_excluded_categories = []
        if exclusion.diet_type_code:
            diet_result = await db.execute(
                select(DietType).where(DietType.code == exclusion.diet_type_code)
            )
            diet = diet_result.scalar_one_or_none()
            if diet:
                diet_type_name = diet.name
                diet_excluded_categories = diet.excluded_categories or []

        # Объединяем категории от диеты и дополнительные
        user_categories = exclusion.excluded_categories or []
        all_categories = list(set(diet_excluded_categories + user_categories))

        return APIResponse(
            success=True,
            data={
                "diet_type_code": exclusion.diet_type_code,
                "diet_type_name": diet_type_name,
                "excluded_categories": user_categories,
                "excluded_products": exclusion.excluded_products or [],
                "all_excluded_categories": all_categories
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user exclusions for {telegram_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения исключений")


@app.put("/users/{telegram_id}/exclusions")
async def update_user_exclusions(
    telegram_id: int,
    request: UpdateExclusionsRequest,
    db: AsyncSession = Depends(get_async_session)
):
    """Обновить исключения пользователя"""
    try:
        # Находим пользователя
        user_result = await db.execute(
            select(DBUser).where(DBUser.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Проверяем существующие исключения
        exclusion_result = await db.execute(
            select(UserExclusion).where(UserExclusion.user_id == user.id)
        )
        exclusion = exclusion_result.scalar_one_or_none()

        if exclusion:
            # Обновляем существующую запись
            if request.diet_type_code is not None:
                exclusion.diet_type_code = request.diet_type_code if request.diet_type_code != "" else None
            if request.excluded_categories is not None:
                exclusion.excluded_categories = request.excluded_categories
            if request.excluded_products is not None:
                exclusion.excluded_products = request.excluded_products
        else:
            # Создаём новую запись
            exclusion = UserExclusion(
                user_id=user.id,
                diet_type_code=request.diet_type_code if request.diet_type_code != "" else None,
                excluded_categories=request.excluded_categories or [],
                excluded_products=request.excluded_products or []
            )
            db.add(exclusion)

        await db.commit()

        logger.info(f"Updated exclusions for user {telegram_id}: diet={request.diet_type_code}, categories={request.excluded_categories}, products={request.excluded_products}")

        return APIResponse(
            success=True,
            message="Исключения обновлены"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user exclusions for {telegram_id}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка обновления исключений")


@app.post("/users/{telegram_id}/exclusions/products")
async def add_excluded_product(
    telegram_id: int,
    request: Dict[str, str],
    db: AsyncSession = Depends(get_async_session)
):
    """Добавить продукт в черный список"""
    try:
        product_name = request.get("product_name", "").strip()
        if not product_name:
            raise HTTPException(status_code=400, detail="Название продукта обязательно")

        # Находим пользователя
        user_result = await db.execute(
            select(DBUser).where(DBUser.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Получаем или создаём запись исключений
        exclusion_result = await db.execute(
            select(UserExclusion).where(UserExclusion.user_id == user.id)
        )
        exclusion = exclusion_result.scalar_one_or_none()

        if not exclusion:
            exclusion = UserExclusion(
                user_id=user.id,
                excluded_products=[product_name.lower()]
            )
            db.add(exclusion)
        else:
            products = exclusion.excluded_products or []
            product_lower = product_name.lower()
            if product_lower not in products:
                products.append(product_lower)
                exclusion.excluded_products = products

        await db.commit()

        logger.info(f"Added excluded product '{product_name}' for user {telegram_id}")

        return APIResponse(
            success=True,
            message=f"Продукт '{product_name}' добавлен в исключения"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding excluded product for {telegram_id}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка добавления продукта")


@app.delete("/users/{telegram_id}/exclusions/products/{product_name}")
async def remove_excluded_product(
    telegram_id: int,
    product_name: str,
    db: AsyncSession = Depends(get_async_session)
):
    """Удалить продукт из черного списка"""
    try:
        # Находим пользователя
        user_result = await db.execute(
            select(DBUser).where(DBUser.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Получаем исключения
        exclusion_result = await db.execute(
            select(UserExclusion).where(UserExclusion.user_id == user.id)
        )
        exclusion = exclusion_result.scalar_one_or_none()

        if not exclusion:
            raise HTTPException(status_code=404, detail="Исключения не найдены")

        products = exclusion.excluded_products or []
        product_lower = product_name.lower()

        if product_lower in products:
            products.remove(product_lower)
            exclusion.excluded_products = products
            await db.commit()
            logger.info(f"Removed excluded product '{product_name}' for user {telegram_id}")
            return APIResponse(success=True, message=f"Продукт '{product_name}' удалён из исключений")
        else:
            return APIResponse(success=False, message=f"Продукт '{product_name}' не найден в исключениях")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing excluded product for {telegram_id}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка удаления продукта")


@app.get("/users/{telegram_id}/exclusions/keywords")
async def get_user_exclusion_keywords(telegram_id: int, db: AsyncSession = Depends(get_async_session)):
    """
    Получить все ключевые слова для фильтрации продуктов пользователя.
    Используется оптимизатором для фильтрации товаров.
    """
    try:
        # Находим пользователя
        user_result = await db.execute(
            select(DBUser).where(DBUser.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Получаем исключения
        exclusion_result = await db.execute(
            select(UserExclusion).where(UserExclusion.user_id == user.id)
        )
        exclusion = exclusion_result.scalar_one_or_none()

        if not exclusion:
            return APIResponse(
                success=True,
                data={
                    "keywords": [],
                    "products": []
                }
            )

        # Собираем все коды категорий (от диеты + дополнительные)
        all_category_codes = set(exclusion.excluded_categories or [])

        if exclusion.diet_type_code:
            diet_result = await db.execute(
                select(DietType).where(DietType.code == exclusion.diet_type_code)
            )
            diet = diet_result.scalar_one_or_none()
            if diet and diet.excluded_categories:
                all_category_codes.update(diet.excluded_categories)

        # Получаем ключевые слова для всех категорий
        keywords = set()
        if all_category_codes:
            # Получаем ID категорий по кодам
            categories_result = await db.execute(
                select(ExclusionCategory)
                .where(ExclusionCategory.code.in_(all_category_codes))
            )
            categories = categories_result.scalars().all()
            category_ids = [cat.id for cat in categories]

            if category_ids:
                keywords_result = await db.execute(
                    select(ExclusionKeyword)
                    .where(
                        ExclusionKeyword.category_id.in_(category_ids),
                        ExclusionKeyword.is_active == True
                    )
                )
                keywords = {kw.keyword.lower() for kw in keywords_result.scalars().all()}

        return APIResponse(
            success=True,
            data={
                "keywords": list(keywords),
                "products": [p.lower() for p in (exclusion.excluded_products or [])]
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting exclusion keywords for {telegram_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения ключевых слов")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "user-service"}


async def run_service():
    """Запуск User Service"""
    logger.info(f"🚀 Starting User Service on port {settings.user_service_port}")
    
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=settings.user_service_port,
        log_config=None,  # Используем наш логгер
        access_log=settings.debug
    )
    
    server = uvicorn.Server(config)
    await server.serve()



@app.post("/users/{telegram_id}/cookies")
async def save_user_cookies(
    telegram_id: int,
    request: Dict[str, Any],
    db: AsyncSession = Depends(get_async_session)
):
    """Сохранение куки пользователя в базу данных"""
    try:
        # Получаем данные из запроса
        lsd_name = request.get("lsd_name")
        cookies = request.get("cookies")
        timestamp = request.get("timestamp")
        
        if not lsd_name:
            raise HTTPException(status_code=400, detail="lsd_name обязателен")
        
        # Проверяем что cookies не пустые (не None, не [], не {})
        if not cookies or (isinstance(cookies, (list, dict)) and len(cookies) == 0):
            logger.warning(f"⚠️ Attempted to save empty cookies for user {telegram_id}, LSD {lsd_name}")
            raise HTTPException(status_code=400, detail="cookies не могут быть пустыми")
        
        # Логируем количество cookies
        cookies_count = len(cookies) if isinstance(cookies, (list, dict)) else 0
        logger.info(f"💾 Saving {cookies_count} cookies for user {telegram_id}, LSD {lsd_name}")
        
        # Находим пользователя
        result = await db.execute(
            select(DBUser).where(DBUser.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # 💾 Сохраняем куки в таблицу user_sessions
        session_result = await db.execute(
            select(UserSession).where(
                UserSession.telegram_id == telegram_id,
                UserSession.lsd_name == lsd_name,
                UserSession.session_type == "cookies"
            )
        )
        existing_session = session_result.scalar_one_or_none()
        
        if existing_session:
            # Обновляем существующую сессию
            existing_session.data = cookies
            existing_session.expires_at = datetime.utcnow() + timedelta(days=30)
            # updated_at обновляется автоматически через триггер БД
            logger.info(f"🔄 Updated existing session {existing_session.id} for user {telegram_id}")
        else:
            # Создаем новую сессию
            new_session = UserSession(
                telegram_id=telegram_id,
                lsd_name=lsd_name,
                session_type="cookies",
                data=cookies,
                expires_at=datetime.utcnow() + timedelta(days=30)
            )
            db.add(new_session)
            logger.info(f"🆕 Created new session for user {telegram_id}")
        
        # Коммитим изменения в БД
        await db.commit()
        
        logger.info(f"💾 Cookies for user {telegram_id} saved to user_sessions table")
        
        # Дополнительно сохраняем в файл для отладки (для совместимости)
        import json
        cookies_json = json.dumps(cookies, ensure_ascii=False, indent=2)
        cookies_file = f"logs/db_cookies_{lsd_name}_{telegram_id}_{timestamp}.json"
        with open(cookies_file, "w", encoding="utf-8") as f:
            f.write(cookies_json)
        
        logger.info(f"📁 Debug file also saved: {cookies_file}")
        
        return {
            "success": True,
            "message": f"Куки для {lsd_name} сохранены в user_sessions",
            "cookies_count": len(cookies),
            "lsd_name": lsd_name,
            "session_type": "cookies"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving cookies for user {telegram_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Ошибка сохранения куки"
        )


@app.get("/users/{telegram_id}/cookies/{lsd_name}")
async def get_user_cookies(
    telegram_id: int,
    lsd_name: str,
    db: AsyncSession = Depends(get_async_session)
):
    """Получение сохраненных куки пользователя для ЛСД"""
    try:
        # Находим пользователя
        result = await db.execute(
            select(DBUser).where(DBUser.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # 🍪 Читаем из таблицы user_sessions
        session_result = await db.execute(
            select(UserSession).where(
                UserSession.telegram_id == telegram_id,
                UserSession.lsd_name == lsd_name,
                UserSession.session_type == "cookies"
            ).order_by(UserSession.updated_at.desc())
        )
        session = session_result.scalar_one_or_none()
        
        if not session:
            return {
                "success": False,
                "message": f"Сохраненные куки для {lsd_name} не найдены в user_sessions"
            }
        
        # Проверяем срок действия
        if session.expires_at < datetime.utcnow():
            logger.warning(f"⚠️ Session {session.id} expired at {session.expires_at}")
            return {
                "success": False,
                "message": "Сохраненные куки устарели"
            }
        
        logger.info(f"✅ Found valid cookies for user {telegram_id}, LSD {lsd_name}")
        
        return {
            "success": True,
            "data": {
                "session_id": session.id,
                "lsd_name": lsd_name,
                "cookies": session.data,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                "expires_at": session.expires_at.isoformat()
            },
            "message": f"Куки для {lsd_name} найдены в user_sessions"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cookies for user {telegram_id}, LSD {lsd_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Ошибка получения куки"
        )


if __name__ == "__main__":
    asyncio.run(run_service())
