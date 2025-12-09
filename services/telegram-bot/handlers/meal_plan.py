"""
Обработчик планов питания и логирования приёмов пищи.
"""
import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload

from shared.database import get_async_session
from shared.database.models import (
    User, FoodCategory, FoodProduct, MealPlan, MealDailyLog, MealEntry
)
from shared.utils.logging import get_logger

logger = get_logger(__name__)


async def get_or_create_user(db, telegram_user) -> int:
    """
    Получает или создаёт пользователя в БД по telegram_id.

    Args:
        db: Async database session
        telegram_user: Telegram user object (from update.effective_user or query.from_user)

    Returns:
        int: Внутренний ID пользователя в БД (users.id)
    """
    telegram_id = telegram_user.id

    # Ищем пользователя по telegram_id
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if user:
        return user.id

    # Создаём нового пользователя
    new_user = User(
        telegram_id=telegram_id,
        username=telegram_user.username,
        first_name=telegram_user.first_name,
        last_name=telegram_user.last_name
    )
    db.add(new_user)
    await db.flush()  # Получаем ID без коммита
    logger.info(f"Created new user: telegram_id={telegram_id}, db_id={new_user.id}")
    return new_user.id


# Типы приёмов пищи
MEAL_TYPES = {
    'breakfast': '🌅 Завтрак',
    'lunch': '☀️ Обед',
    'dinner': '🌙 Ужин',
    'snack': '🍎 Перекус'
}


def calculate_bmr(weight: float, height: float, age: int, gender: str) -> int:
    """
    Расчёт базового метаболизма по формуле Миффлина-Сан Жеора.

    Args:
        weight: Вес в кг
        height: Рост в см
        age: Возраст в годах
        gender: 'male' или 'female'

    Returns:
        BMR в ккал/день
    """
    if gender == 'male':
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    return int(bmr)


def calculate_tdee(bmr: int, activity_level: str) -> int:
    """
    Расчёт суточной нормы калорий с учётом активности.

    Args:
        bmr: Базовый метаболизм
        activity_level: Уровень активности

    Returns:
        TDEE в ккал/день
    """
    multipliers = {
        'sedentary': 1.2,      # Сидячий образ жизни
        'light': 1.375,        # Лёгкие тренировки 1-3 раза/неделю
        'moderate': 1.55,      # Умеренные тренировки 3-5 раз/неделю
        'active': 1.725,       # Интенсивные тренировки 6-7 раз/неделю
        'very_active': 1.9     # Очень интенсивные тренировки или физ. работа
    }
    return int(bmr * multipliers.get(activity_level, 1.55))


def calculate_macros(calories: int, goal: str) -> Dict[str, int]:
    """
    Расчёт макронутриентов на основе калорий и цели.

    Args:
        calories: Целевые калории
        goal: 'lose' (похудение), 'maintain' (поддержание), 'gain' (набор)

    Returns:
        Dict с protein, fat, carbs в граммах
    """
    if goal == 'lose':
        # Высокобелковая диета для похудения
        protein_ratio = 0.30  # 30% от калорий
        fat_ratio = 0.30      # 30% от калорий
        carb_ratio = 0.40     # 40% от калорий
    elif goal == 'gain':
        # Для набора массы
        protein_ratio = 0.25
        fat_ratio = 0.25
        carb_ratio = 0.50
    else:
        # Поддержание
        protein_ratio = 0.25
        fat_ratio = 0.30
        carb_ratio = 0.45

    return {
        'protein': int((calories * protein_ratio) / 4),  # 4 ккал/г
        'fat': int((calories * fat_ratio) / 9),          # 9 ккал/г
        'carbs': int((calories * carb_ratio) / 4)        # 4 ккал/г
    }


class MealPlanHandler:
    """Обработчик команд планов питания"""

    def __init__(self):
        pass

    async def meal_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Главное меню планов питания /meal"""
        telegram_id = update.effective_user.id
        print(f"🍽️ /meal from {telegram_id}")

        # Проверяем есть ли активный план
        async for db in get_async_session():
            # Получаем или создаём пользователя
            user_id = await get_or_create_user(db, update.effective_user)

            result = await db.execute(
                select(MealPlan)
                .where(and_(
                    MealPlan.user_id == user_id,
                    MealPlan.is_active == True
                ))
                .order_by(MealPlan.created_at.desc())
                .limit(1)
            )
            active_plan = result.scalar_one_or_none()

            if active_plan:
                # Показываем меню с активным планом
                await self._show_active_plan_menu(update, context, active_plan, db)
            else:
                # Предлагаем создать план
                await self._show_create_plan_menu(update, context)
            break

    async def _show_create_plan_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Меню создания нового плана"""
        keyboard = [
            [InlineKeyboardButton("📊 Рассчитать норму КБЖУ", callback_data="meal_calc_start")],
            [InlineKeyboardButton("✍️ Ввести вручную", callback_data="meal_manual_input")],
            [InlineKeyboardButton("📚 Готовые планы", callback_data="meal_templates")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "🍽️ *План питания*\n\n"
            "У вас пока нет активного плана питания.\n"
            "Выберите способ создания:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    async def _show_active_plan_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                      plan: MealPlan, db):
        """Меню с активным планом"""
        # Получаем статистику за сегодня
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        result = await db.execute(
            select(MealDailyLog)
            .where(and_(
                MealDailyLog.meal_plan_id == plan.id,
                MealDailyLog.log_date >= today
            ))
        )
        today_log = result.scalar_one_or_none()

        # Формируем статистику
        if today_log:
            calories_eaten = float(today_log.actual_calories or 0)
            protein_eaten = float(today_log.actual_protein or 0)
            fat_eaten = float(today_log.actual_fat or 0)
            carbs_eaten = float(today_log.actual_carbs or 0)
        else:
            calories_eaten = protein_eaten = fat_eaten = carbs_eaten = 0

        calories_left = plan.target_calories - calories_eaten
        calories_percent = int((calories_eaten / plan.target_calories) * 100) if plan.target_calories > 0 else 0

        # Прогресс-бар
        progress_filled = min(calories_percent // 10, 10)
        progress_bar = "▓" * progress_filled + "░" * (10 - progress_filled)

        text = (
            f"🍽️ *{plan.name or 'План питания'}*\n\n"
            f"📅 Сегодня:\n"
            f"[{progress_bar}] {calories_percent}%\n\n"
            f"🔥 Калории: {int(calories_eaten)} / {plan.target_calories} ккал\n"
            f"   Осталось: {int(calories_left)} ккал\n\n"
            f"🥩 Белки: {int(protein_eaten)} / {int(plan.target_protein or 0)} г\n"
            f"🧈 Жиры: {int(fat_eaten)} / {int(plan.target_fat or 0)} г\n"
            f"🍞 Углеводы: {int(carbs_eaten)} / {int(plan.target_carbs or 0)} г"
        )

        keyboard = [
            [InlineKeyboardButton("➕ Добавить приём пищи", callback_data="meal_add")],
            [
                InlineKeyboardButton("📋 История", callback_data="meal_history"),
                InlineKeyboardButton("📊 Статистика", callback_data="meal_stats")
            ],
            [InlineKeyboardButton("⚙️ Настройки плана", callback_data="meal_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    async def handle_meal_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик callback'ов для планов питания"""
        query = update.callback_query
        await query.answer()

        data = query.data
        user_id = query.from_user.id

        print(f"🍽️ Meal callback: {data} from {user_id}")

        if data == "meal_calc_start":
            await self._start_calculator(query, context)
        elif data == "meal_manual_input":
            await self._start_manual_input(query, context)
        elif data == "meal_templates":
            await self._show_templates(query, context)
        elif data == "meal_add":
            await self._show_meal_type_selection(query, context)
        elif data.startswith("meal_type_"):
            meal_type = data.replace("meal_type_", "")
            await self._show_product_search(query, context, meal_type)
        elif data.startswith("meal_cat_"):
            category_id = int(data.replace("meal_cat_", ""))
            await self._show_category_products(query, context, category_id)
        elif data.startswith("meal_prod_"):
            parts = data.split("_")
            product_id = int(parts[2])
            meal_type = parts[3] if len(parts) > 3 else "snack"
            await self._show_portion_input(query, context, product_id, meal_type)
        elif data == "meal_history":
            await self._show_history(query, context)
        elif data == "meal_stats":
            await self._show_stats(query, context)
        elif data == "meal_settings":
            await self._show_settings(query, context)
        elif data.startswith("meal_activity_"):
            activity = data.replace("meal_activity_", "")
            await self._process_activity_selection(query, context, activity)
        elif data.startswith("meal_goal_"):
            goal = data.replace("meal_goal_", "")
            await self._create_plan_from_calculator(query, context, goal)
        elif data.startswith("meal_gender_"):
            await self.handle_gender_callback(update, context)
        elif data == "meal_back":
            await self._show_main_menu(query, context)
        elif data == "meal_deactivate":
            await self._deactivate_plan(query, context)
        elif data.startswith("meal_tpl_"):
            calories = int(data.replace("meal_tpl_", ""))
            await self._create_plan_from_template(query, context, calories)

    async def _start_calculator(self, query, context):
        """Начало калькулятора КБЖУ"""
        context.user_data['meal_calc'] = {}

        await query.edit_message_text(
            "📊 *Калькулятор нормы КБЖУ*\n\n"
            "Для расчёта мне нужны ваши данные.\n\n"
            "Введите ваш *вес* в кг (например: 70):",
            parse_mode="Markdown"
        )
        context.user_data['meal_calc_step'] = 'weight'

    async def process_calc_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """
        Обработка ввода данных для калькулятора.
        Возвращает True если сообщение обработано.
        """
        step = context.user_data.get('meal_calc_step')
        if not step:
            return False

        text = update.message.text.strip()

        if step == 'weight':
            try:
                weight = float(text.replace(',', '.'))
                if weight < 30 or weight > 300:
                    raise ValueError("Invalid weight")
                context.user_data['meal_calc']['weight'] = weight
                context.user_data['meal_calc_step'] = 'height'
                await update.message.reply_text(
                    f"✅ Вес: {weight} кг\n\n"
                    "Введите ваш *рост* в см (например: 175):",
                    parse_mode="Markdown"
                )
            except ValueError:
                await update.message.reply_text("❌ Введите корректный вес (30-300 кг)")
            return True

        elif step == 'height':
            try:
                height = float(text.replace(',', '.'))
                if height < 100 or height > 250:
                    raise ValueError("Invalid height")
                context.user_data['meal_calc']['height'] = height
                context.user_data['meal_calc_step'] = 'age'
                await update.message.reply_text(
                    f"✅ Рост: {int(height)} см\n\n"
                    "Введите ваш *возраст* в годах:",
                    parse_mode="Markdown"
                )
            except ValueError:
                await update.message.reply_text("❌ Введите корректный рост (100-250 см)")
            return True

        elif step == 'age':
            try:
                age = int(text)
                if age < 14 or age > 100:
                    raise ValueError("Invalid age")
                context.user_data['meal_calc']['age'] = age
                context.user_data['meal_calc_step'] = 'gender'

                keyboard = [
                    [
                        InlineKeyboardButton("👨 Мужской", callback_data="meal_gender_male"),
                        InlineKeyboardButton("👩 Женский", callback_data="meal_gender_female")
                    ]
                ]
                await update.message.reply_text(
                    f"✅ Возраст: {age} лет\n\n"
                    "Выберите *пол*:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            except ValueError:
                await update.message.reply_text("❌ Введите корректный возраст (14-100 лет)")
            return True

        elif step == 'portion':
            # Обработка ввода порции
            try:
                portion = float(text.replace(',', '.'))
                if portion <= 0 or portion > 2000:
                    raise ValueError("Invalid portion")

                product_id = context.user_data.get('meal_product_id')
                meal_type = context.user_data.get('meal_type', 'snack')

                await self._log_meal_entry(update, context, product_id, portion, meal_type)

                # Очищаем контекст
                context.user_data.pop('meal_calc_step', None)
                context.user_data.pop('meal_product_id', None)
                context.user_data.pop('meal_type', None)

            except ValueError:
                await update.message.reply_text("❌ Введите корректный размер порции (1-2000)")
            return True

        return False

    async def handle_gender_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора пола"""
        query = update.callback_query
        await query.answer()

        gender = query.data.replace("meal_gender_", "")
        context.user_data['meal_calc']['gender'] = gender
        context.user_data['meal_calc_step'] = 'activity'

        keyboard = [
            [InlineKeyboardButton("🪑 Сидячий", callback_data="meal_activity_sedentary")],
            [InlineKeyboardButton("🚶 Лёгкая активность", callback_data="meal_activity_light")],
            [InlineKeyboardButton("🏃 Умеренная", callback_data="meal_activity_moderate")],
            [InlineKeyboardButton("💪 Высокая", callback_data="meal_activity_active")],
            [InlineKeyboardButton("🏋️ Очень высокая", callback_data="meal_activity_very_active")]
        ]

        await query.edit_message_text(
            f"✅ Пол: {'Мужской' if gender == 'male' else 'Женский'}\n\n"
            "Выберите *уровень активности*:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    async def _process_activity_selection(self, query, context, activity: str):
        """Обработка выбора активности и показ цели"""
        context.user_data['meal_calc']['activity'] = activity

        # Рассчитываем TDEE
        calc = context.user_data['meal_calc']
        bmr = calculate_bmr(calc['weight'], calc['height'], calc['age'], calc['gender'])
        tdee = calculate_tdee(bmr, activity)
        context.user_data['meal_calc']['tdee'] = tdee

        activity_names = {
            'sedentary': 'Сидячий',
            'light': 'Лёгкая активность',
            'moderate': 'Умеренная',
            'active': 'Высокая',
            'very_active': 'Очень высокая'
        }

        keyboard = [
            [InlineKeyboardButton("📉 Похудение (-500 ккал)", callback_data="meal_goal_lose")],
            [InlineKeyboardButton("⚖️ Поддержание веса", callback_data="meal_goal_maintain")],
            [InlineKeyboardButton("📈 Набор массы (+300 ккал)", callback_data="meal_goal_gain")]
        ]

        await query.edit_message_text(
            f"📊 *Ваши данные:*\n"
            f"• Вес: {calc['weight']} кг\n"
            f"• Рост: {int(calc['height'])} см\n"
            f"• Возраст: {calc['age']} лет\n"
            f"• Пол: {'Мужской' if calc['gender'] == 'male' else 'Женский'}\n"
            f"• Активность: {activity_names[activity]}\n\n"
            f"🔥 *Базовый обмен (BMR):* {bmr} ккал\n"
            f"🔥 *Суточная норма (TDEE):* {tdee} ккал\n\n"
            "Выберите *цель*:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    async def _create_plan_from_calculator(self, query, context, goal: str):
        """Создание плана из калькулятора"""
        calc = context.user_data.get('meal_calc', {})
        tdee = calc.get('tdee', 2000)

        # Корректируем калории по цели
        if goal == 'lose':
            target_calories = tdee - 500
        elif goal == 'gain':
            target_calories = tdee + 300
        else:
            target_calories = tdee

        # Рассчитываем макросы
        macros = calculate_macros(target_calories, goal)

        goal_names = {
            'lose': 'Похудение',
            'maintain': 'Поддержание веса',
            'gain': 'Набор массы'
        }

        # Создаём план в БД
        async for db in get_async_session():
            # Получаем или создаём пользователя
            user_id = await get_or_create_user(db, query.from_user)

            # Деактивируем старые планы
            result = await db.execute(
                select(MealPlan).where(and_(
                    MealPlan.user_id == user_id,
                    MealPlan.is_active == True
                ))
            )
            for old_plan in result.scalars():
                old_plan.is_active = False

            # Создаём новый план
            new_plan = MealPlan(
                user_id=user_id,
                target_calories=target_calories,
                target_protein=macros['protein'],
                target_fat=macros['fat'],
                target_carbs=macros['carbs'],
                start_date=datetime.now(),
                is_active=True,
                name=f"План: {goal_names[goal]}"
            )
            db.add(new_plan)
            await db.commit()

            await query.edit_message_text(
                f"✅ *План питания создан!*\n\n"
                f"📋 *{goal_names[goal]}*\n\n"
                f"🎯 Ваши дневные цели:\n"
                f"🔥 Калории: *{target_calories}* ккал\n"
                f"🥩 Белки: *{macros['protein']}* г\n"
                f"🧈 Жиры: *{macros['fat']}* г\n"
                f"🍞 Углеводы: *{macros['carbs']}* г\n\n"
                f"Используйте /meal для добавления приёмов пищи.",
                parse_mode="Markdown"
            )

            # Очищаем контекст
            context.user_data.pop('meal_calc', None)
            context.user_data.pop('meal_calc_step', None)
            break

    async def _show_meal_type_selection(self, query, context):
        """Выбор типа приёма пищи"""
        keyboard = [
            [InlineKeyboardButton(name, callback_data=f"meal_type_{key}")]
            for key, name in MEAL_TYPES.items()
        ]
        keyboard.append([InlineKeyboardButton("« Назад", callback_data="meal_back")])

        await query.edit_message_text(
            "➕ *Добавить приём пищи*\n\n"
            "Выберите тип:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    async def _show_product_search(self, query, context, meal_type: str):
        """Показ категорий продуктов для поиска"""
        context.user_data['meal_type'] = meal_type

        async for db in get_async_session():
            result = await db.execute(
                select(FoodCategory)
                .where(FoodCategory.is_active == True)
                .order_by(FoodCategory.sort_order)
            )
            categories = result.scalars().all()

            keyboard = []
            for cat in categories:
                icon = cat.icon or '📦'
                keyboard.append([
                    InlineKeyboardButton(
                        f"{icon} {cat.name}",
                        callback_data=f"meal_cat_{cat.id}"
                    )
                ])
            keyboard.append([InlineKeyboardButton("« Назад", callback_data="meal_add")])

            await query.edit_message_text(
                f"🍽️ *{MEAL_TYPES.get(meal_type, 'Приём пищи')}*\n\n"
                "Выберите категорию продуктов:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            break

    async def _show_category_products(self, query, context, category_id: int):
        """Показ продуктов в категории"""
        meal_type = context.user_data.get('meal_type', 'snack')

        async for db in get_async_session():
            # Получаем категорию
            cat_result = await db.execute(
                select(FoodCategory).where(FoodCategory.id == category_id)
            )
            category = cat_result.scalar_one_or_none()

            # Получаем продукты
            result = await db.execute(
                select(FoodProduct)
                .where(and_(
                    FoodProduct.category_id == category_id,
                    FoodProduct.is_active == True
                ))
                .order_by(FoodProduct.name)
            )
            products = result.scalars().all()

            if not products:
                await query.edit_message_text(
                    "❌ В этой категории пока нет продуктов.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("« Назад", callback_data=f"meal_type_{meal_type}")]
                    ])
                )
                return

            keyboard = []
            for prod in products[:15]:  # Ограничиваем 15 продуктами
                cal = int(prod.calories)
                keyboard.append([
                    InlineKeyboardButton(
                        f"{prod.name} ({cal} ккал)",
                        callback_data=f"meal_prod_{prod.id}_{meal_type}"
                    )
                ])
            keyboard.append([InlineKeyboardButton("« Назад", callback_data=f"meal_type_{meal_type}")])

            cat_name = category.name if category else "Продукты"
            await query.edit_message_text(
                f"📦 *{cat_name}*\n\n"
                "Выберите продукт:\n"
                "(калории указаны на 100г)",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            break

    async def _show_portion_input(self, query, context, product_id: int, meal_type: str):
        """Запрос размера порции"""
        async for db in get_async_session():
            result = await db.execute(
                select(FoodProduct).where(FoodProduct.id == product_id)
            )
            product = result.scalar_one_or_none()

            if not product:
                await query.answer("❌ Продукт не найден", show_alert=True)
                return

            context.user_data['meal_product_id'] = product_id
            context.user_data['meal_type'] = meal_type
            context.user_data['meal_calc_step'] = 'portion'

            serving = int(product.serving_size)
            cal_per_serving = int(float(product.calories) * serving / 100)

            await query.edit_message_text(
                f"🍽️ *{product.name}*\n\n"
                f"На 100г: {int(product.calories)} ккал\n"
                f"• Белки: {float(product.protein):.1f}г\n"
                f"• Жиры: {float(product.fat):.1f}г\n"
                f"• Углеводы: {float(product.carbs):.1f}г\n\n"
                f"💡 Типичная порция: {serving}{product.unit} ({cal_per_serving} ккал)\n\n"
                f"Введите размер вашей порции в {product.unit}:",
                parse_mode="Markdown"
            )
            break

    async def _log_meal_entry(self, update: Update, context, product_id: int,
                              portion: float, meal_type: str):
        """Сохранение записи о приёме пищи"""
        async for db in get_async_session():
            # Получаем или создаём пользователя
            user_id = await get_or_create_user(db, update.effective_user)

            # Получаем продукт
            result = await db.execute(
                select(FoodProduct).where(FoodProduct.id == product_id)
            )
            product = result.scalar_one_or_none()
            if not product:
                await update.message.reply_text("❌ Продукт не найден")
                return

            # Получаем активный план
            plan_result = await db.execute(
                select(MealPlan).where(and_(
                    MealPlan.user_id == user_id,
                    MealPlan.is_active == True
                ))
            )
            plan = plan_result.scalar_one_or_none()
            if not plan:
                await update.message.reply_text(
                    "❌ У вас нет активного плана питания.\n"
                    "Создайте его командой /meal"
                )
                return

            # Получаем или создаём дневной лог
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            log_result = await db.execute(
                select(MealDailyLog).where(and_(
                    MealDailyLog.meal_plan_id == plan.id,
                    MealDailyLog.log_date >= today
                ))
            )
            daily_log = log_result.scalar_one_or_none()

            if not daily_log:
                daily_log = MealDailyLog(
                    meal_plan_id=plan.id,
                    log_date=today,
                    actual_calories=0,
                    actual_protein=0,
                    actual_fat=0,
                    actual_carbs=0
                )
                db.add(daily_log)
                await db.flush()

            # Рассчитываем КБЖУ для порции
            multiplier = Decimal(str(portion)) / Decimal('100')
            entry_calories = float(product.calories) * float(multiplier)
            entry_protein = float(product.protein) * float(multiplier)
            entry_fat = float(product.fat) * float(multiplier)
            entry_carbs = float(product.carbs) * float(multiplier)

            # Создаём запись
            entry = MealEntry(
                daily_log_id=daily_log.id,
                food_product_id=product_id,
                meal_type=meal_type,
                product_name=product.name,
                portion_size=portion,
                portion_unit=product.unit,
                calories=entry_calories,
                protein=entry_protein,
                fat=entry_fat,
                carbs=entry_carbs,
                is_custom=False
            )
            db.add(entry)

            # Обновляем дневной лог
            daily_log.actual_calories = float(daily_log.actual_calories or 0) + entry_calories
            daily_log.actual_protein = float(daily_log.actual_protein or 0) + entry_protein
            daily_log.actual_fat = float(daily_log.actual_fat or 0) + entry_fat
            daily_log.actual_carbs = float(daily_log.actual_carbs or 0) + entry_carbs

            # Рассчитываем процент
            if plan.target_calories > 0:
                daily_log.calories_percent = (float(daily_log.actual_calories) / plan.target_calories) * 100

            await db.commit()

            # Формируем ответ
            calories_left = plan.target_calories - float(daily_log.actual_calories)
            progress_percent = int(daily_log.calories_percent)
            progress_filled = min(progress_percent // 10, 10)
            progress_bar = "▓" * progress_filled + "░" * (10 - progress_filled)

            await update.message.reply_text(
                f"✅ *Добавлено!*\n\n"
                f"🍽️ {MEAL_TYPES.get(meal_type, 'Приём пищи')}\n"
                f"📦 {product.name}\n"
                f"⚖️ Порция: {int(portion)}{product.unit}\n"
                f"🔥 +{int(entry_calories)} ккал\n\n"
                f"📊 *Прогресс за день:*\n"
                f"[{progress_bar}] {progress_percent}%\n"
                f"Осталось: {int(calories_left)} ккал",
                parse_mode="Markdown"
            )
            break

    async def _show_history(self, query, context):
        """Показ истории питания"""
        async for db in get_async_session():
            # Получаем или создаём пользователя
            user_id = await get_or_create_user(db, query.from_user)

            # Получаем активный план
            plan_result = await db.execute(
                select(MealPlan).where(and_(
                    MealPlan.user_id == user_id,
                    MealPlan.is_active == True
                ))
            )
            plan = plan_result.scalar_one_or_none()

            if not plan:
                await query.edit_message_text("❌ Нет активного плана питания")
                return

            # Получаем записи за сегодня
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            result = await db.execute(
                select(MealDailyLog)
                .options(selectinload(MealDailyLog.entries))
                .where(and_(
                    MealDailyLog.meal_plan_id == plan.id,
                    MealDailyLog.log_date >= today
                ))
            )
            daily_log = result.scalar_one_or_none()

            if not daily_log or not daily_log.entries:
                await query.edit_message_text(
                    "📋 *История за сегодня*\n\n"
                    "Пока нет записей. Добавьте первый приём пищи!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("➕ Добавить", callback_data="meal_add")],
                        [InlineKeyboardButton("« Назад", callback_data="meal_back")]
                    ]),
                    parse_mode="Markdown"
                )
                return

            # Группируем по типам приёмов
            entries_by_type = {}
            for entry in daily_log.entries:
                if entry.meal_type not in entries_by_type:
                    entries_by_type[entry.meal_type] = []
                entries_by_type[entry.meal_type].append(entry)

            text = "📋 *История за сегодня*\n\n"
            for meal_type, entries in entries_by_type.items():
                text += f"*{MEAL_TYPES.get(meal_type, meal_type)}*\n"
                for e in entries:
                    text += f"  • {e.product_name} ({int(e.portion_size)}г) - {int(e.calories)} ккал\n"
                text += "\n"

            text += f"📊 *Итого:* {int(daily_log.actual_calories)} / {plan.target_calories} ккал"

            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Добавить", callback_data="meal_add")],
                    [InlineKeyboardButton("« Назад", callback_data="meal_back")]
                ]),
                parse_mode="Markdown"
            )
            break

    async def _show_stats(self, query, context):
        """Показ статистики за неделю"""
        async for db in get_async_session():
            # Получаем или создаём пользователя
            user_id = await get_or_create_user(db, query.from_user)

            plan_result = await db.execute(
                select(MealPlan).where(and_(
                    MealPlan.user_id == user_id,
                    MealPlan.is_active == True
                ))
            )
            plan = plan_result.scalar_one_or_none()

            if not plan:
                await query.edit_message_text("❌ Нет активного плана питания")
                return

            # Статистика за 7 дней
            week_ago = datetime.now() - timedelta(days=7)
            result = await db.execute(
                select(MealDailyLog)
                .where(and_(
                    MealDailyLog.meal_plan_id == plan.id,
                    MealDailyLog.log_date >= week_ago
                ))
                .order_by(MealDailyLog.log_date.desc())
            )
            logs = result.scalars().all()

            if not logs:
                await query.edit_message_text(
                    "📊 *Статистика за неделю*\n\n"
                    "Пока нет данных. Начните вести дневник питания!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("« Назад", callback_data="meal_back")]
                    ]),
                    parse_mode="Markdown"
                )
                return

            # Средние значения
            avg_calories = sum(float(l.actual_calories or 0) for l in logs) / len(logs)
            avg_protein = sum(float(l.actual_protein or 0) for l in logs) / len(logs)
            avg_fat = sum(float(l.actual_fat or 0) for l in logs) / len(logs)
            avg_carbs = sum(float(l.actual_carbs or 0) for l in logs) / len(logs)

            # Дни в цели (±10%)
            days_on_target = sum(
                1 for l in logs
                if 0.9 * plan.target_calories <= float(l.actual_calories or 0) <= 1.1 * plan.target_calories
            )

            text = (
                f"📊 *Статистика за неделю*\n\n"
                f"📅 Записей: {len(logs)} дней\n"
                f"🎯 В цели: {days_on_target} дней\n\n"
                f"*Средние значения:*\n"
                f"🔥 Калории: {int(avg_calories)} ккал/день\n"
                f"🥩 Белки: {int(avg_protein)}г\n"
                f"🧈 Жиры: {int(avg_fat)}г\n"
                f"🍞 Углеводы: {int(avg_carbs)}г\n\n"
                f"*Цели:*\n"
                f"🎯 {plan.target_calories} ккал/день"
            )

            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« Назад", callback_data="meal_back")]
                ]),
                parse_mode="Markdown"
            )
            break

    async def _show_settings(self, query, context):
        """Настройки плана"""
        telegram_id = query.from_user.id
        keyboard = [
            [InlineKeyboardButton("📊 Пересчитать КБЖУ", callback_data="meal_calc_start")],
            [InlineKeyboardButton("🚫 Исключения продуктов", callback_data=f"excl_menu_{telegram_id}")],
            [InlineKeyboardButton("❌ Деактивировать план", callback_data="meal_deactivate")],
            [InlineKeyboardButton("« Назад", callback_data="meal_back")]
        ]

        await query.edit_message_text(
            "⚙️ *Настройки плана*\n\n"
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    async def _start_manual_input(self, query, context):
        """Ручной ввод целевых значений"""
        context.user_data['meal_manual'] = {}
        context.user_data['meal_calc_step'] = 'manual_calories'

        await query.edit_message_text(
            "✍️ *Ручной ввод*\n\n"
            "Введите целевое количество *калорий* в день:",
            parse_mode="Markdown"
        )

    async def _show_templates(self, query, context):
        """Готовые шаблоны планов"""
        keyboard = [
            [InlineKeyboardButton("🏃 Похудение (1500 ккал)", callback_data="meal_tpl_1500")],
            [InlineKeyboardButton("⚖️ Поддержание (2000 ккал)", callback_data="meal_tpl_2000")],
            [InlineKeyboardButton("💪 Набор массы (2500 ккал)", callback_data="meal_tpl_2500")],
            [InlineKeyboardButton("🏋️ Спорт (3000 ккал)", callback_data="meal_tpl_3000")],
            [InlineKeyboardButton("« Назад", callback_data="meal_back")]
        ]

        await query.edit_message_text(
            "📚 *Готовые планы*\n\n"
            "Выберите подходящий шаблон:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    async def _show_main_menu(self, query, context):
        """Показ главного меню питания"""
        async for db in get_async_session():
            # Получаем или создаём пользователя
            user_id = await get_or_create_user(db, query.from_user)

            result = await db.execute(
                select(MealPlan)
                .where(and_(
                    MealPlan.user_id == user_id,
                    MealPlan.is_active == True
                ))
                .order_by(MealPlan.created_at.desc())
                .limit(1)
            )
            active_plan = result.scalar_one_or_none()

            if active_plan:
                # Показываем меню с активным планом (как в meal_command, но для query)
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

                log_result = await db.execute(
                    select(MealDailyLog)
                    .where(and_(
                        MealDailyLog.meal_plan_id == active_plan.id,
                        MealDailyLog.log_date >= today
                    ))
                )
                today_log = log_result.scalar_one_or_none()

                if today_log:
                    calories_eaten = float(today_log.actual_calories or 0)
                    protein_eaten = float(today_log.actual_protein or 0)
                    fat_eaten = float(today_log.actual_fat or 0)
                    carbs_eaten = float(today_log.actual_carbs or 0)
                else:
                    calories_eaten = protein_eaten = fat_eaten = carbs_eaten = 0

                calories_left = active_plan.target_calories - calories_eaten
                calories_percent = int((calories_eaten / active_plan.target_calories) * 100) if active_plan.target_calories > 0 else 0

                progress_filled = min(calories_percent // 10, 10)
                progress_bar = "▓" * progress_filled + "░" * (10 - progress_filled)

                text = (
                    f"🍽️ *{active_plan.name or 'План питания'}*\n\n"
                    f"📅 Сегодня:\n"
                    f"[{progress_bar}] {calories_percent}%\n\n"
                    f"🔥 Калории: {int(calories_eaten)} / {active_plan.target_calories} ккал\n"
                    f"   Осталось: {int(calories_left)} ккал\n\n"
                    f"🥩 Белки: {int(protein_eaten)} / {int(active_plan.target_protein or 0)} г\n"
                    f"🧈 Жиры: {int(fat_eaten)} / {int(active_plan.target_fat or 0)} г\n"
                    f"🍞 Углеводы: {int(carbs_eaten)} / {int(active_plan.target_carbs or 0)} г"
                )

                keyboard = [
                    [InlineKeyboardButton("➕ Добавить приём пищи", callback_data="meal_add")],
                    [
                        InlineKeyboardButton("📋 История", callback_data="meal_history"),
                        InlineKeyboardButton("📊 Статистика", callback_data="meal_stats")
                    ],
                    [InlineKeyboardButton("⚙️ Настройки плана", callback_data="meal_settings")]
                ]

                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            else:
                # Предлагаем создать план
                keyboard = [
                    [InlineKeyboardButton("📊 Рассчитать норму КБЖУ", callback_data="meal_calc_start")],
                    [InlineKeyboardButton("✍️ Ввести вручную", callback_data="meal_manual_input")],
                    [InlineKeyboardButton("📚 Готовые планы", callback_data="meal_templates")]
                ]

                await query.edit_message_text(
                    "🍽️ *План питания*\n\n"
                    "У вас пока нет активного плана питания.\n"
                    "Выберите способ создания:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            break

    async def _deactivate_plan(self, query, context):
        """Деактивация плана питания"""
        async for db in get_async_session():
            # Получаем или создаём пользователя
            user_id = await get_or_create_user(db, query.from_user)

            result = await db.execute(
                select(MealPlan).where(and_(
                    MealPlan.user_id == user_id,
                    MealPlan.is_active == True
                ))
            )
            for plan in result.scalars():
                plan.is_active = False
                plan.end_date = datetime.now()

            await db.commit()

            await query.edit_message_text(
                "✅ *План питания деактивирован*\n\n"
                "Вы можете создать новый план командой /meal",
                parse_mode="Markdown"
            )
            break

    async def _create_plan_from_template(self, query, context, calories: int):
        """Создание плана из шаблона"""
        # Определяем цель по калориям
        if calories <= 1500:
            goal = 'lose'
            goal_name = 'Похудение'
        elif calories <= 2200:
            goal = 'maintain'
            goal_name = 'Поддержание веса'
        else:
            goal = 'gain'
            goal_name = 'Набор массы'

        macros = calculate_macros(calories, goal)

        async for db in get_async_session():
            # Получаем или создаём пользователя
            user_id = await get_or_create_user(db, query.from_user)

            # Деактивируем старые планы
            result = await db.execute(
                select(MealPlan).where(and_(
                    MealPlan.user_id == user_id,
                    MealPlan.is_active == True
                ))
            )
            for old_plan in result.scalars():
                old_plan.is_active = False

            # Создаём новый план
            new_plan = MealPlan(
                user_id=user_id,
                target_calories=calories,
                target_protein=macros['protein'],
                target_fat=macros['fat'],
                target_carbs=macros['carbs'],
                start_date=datetime.now(),
                is_active=True,
                name=f"План: {goal_name} ({calories} ккал)"
            )
            db.add(new_plan)
            await db.commit()

            await query.edit_message_text(
                f"✅ *План питания создан!*\n\n"
                f"📋 *{goal_name}*\n\n"
                f"🎯 Ваши дневные цели:\n"
                f"🔥 Калории: *{calories}* ккал\n"
                f"🥩 Белки: *{macros['protein']}* г\n"
                f"🧈 Жиры: *{macros['fat']}* г\n"
                f"🍞 Углеводы: *{macros['carbs']}* г\n\n"
                f"Используйте /meal для добавления приёмов пищи.",
                parse_mode="Markdown"
            )
            break
