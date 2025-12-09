"""
Обработчик настроек исключений продуктов в Telegram-боте.
Позволяет пользователям управлять:
- Типом питания (веган, вегетарианец, кето и т.д.)
- Категориями исключений (молочка, глютен, орехи и т.д.)
- Персональным черным списком продуктов
"""

import logging
import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

USER_SERVICE_URL = "http://localhost:8002"


class ExclusionsHandler:
    """Обработчик исключений продуктов"""

    def __init__(self):
        self.waiting_for_product = {}  # telegram_id -> True если ждём ввода продукта

    async def show_exclusions_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать главное меню исключений"""
        user_id = update.effective_user.id

        # Получаем текущие исключения пользователя
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{USER_SERVICE_URL}/users/{user_id}/exclusions")
                if response.status_code == 200:
                    data = response.json().get("data", {})
                else:
                    data = {}
        except Exception as e:
            logger.error(f"Error getting exclusions: {e}")
            data = {}

        # Формируем текст с текущими настройками
        diet_type_name = data.get("diet_type_name")
        excluded_categories = data.get("excluded_categories", [])
        excluded_products = data.get("excluded_products", [])

        text = "🚫 *Исключения продуктов*\n\n"

        if diet_type_name:
            text += f"🍽 Тип питания: *{diet_type_name}*\n"
        else:
            text += "🍽 Тип питания: _не выбран_\n"

        if excluded_categories:
            text += f"📋 Категории: {len(excluded_categories)} шт.\n"
        else:
            text += "📋 Категории: _не выбраны_\n"

        if excluded_products:
            text += f"🛒 Продукты: {len(excluded_products)} шт.\n"
        else:
            text += "🛒 Продукты: _не добавлены_\n"

        text += "\n_Выберите, что хотите настроить:_"

        keyboard = [
            [InlineKeyboardButton("🍽 Тип питания", callback_data=f"excl_diet_menu_{user_id}")],
            [InlineKeyboardButton("📋 Категории продуктов", callback_data=f"excl_cat_menu_{user_id}")],
            [InlineKeyboardButton("🛒 Мой чёрный список", callback_data=f"excl_products_menu_{user_id}")],
            [InlineKeyboardButton("◀️ Назад к настройкам", callback_data=f"excl_back_settings_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Определяем как отправить сообщение
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

    async def show_diet_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать меню выбора типа питания"""
        user_id = update.effective_user.id
        query = update.callback_query

        # Получаем доступные типы диет
        try:
            async with httpx.AsyncClient() as client:
                # Получаем типы диет
                diet_response = await client.get(f"{USER_SERVICE_URL}/exclusions/diet-types")
                diet_types = diet_response.json().get("data", []) if diet_response.status_code == 200 else []

                # Получаем текущий выбор пользователя
                user_response = await client.get(f"{USER_SERVICE_URL}/users/{user_id}/exclusions")
                user_data = user_response.json().get("data", {}) if user_response.status_code == 200 else {}
                current_diet = user_data.get("diet_type_code")
        except Exception as e:
            logger.error(f"Error getting diet types: {e}")
            await query.answer("Ошибка загрузки данных", show_alert=True)
            return

        text = "🍽 *Выберите тип питания*\n\n"
        text += "_Тип питания автоматически исключает определённые категории продуктов._\n\n"

        keyboard = []

        # Добавляем кнопку "Без ограничений"
        check = "✅ " if not current_diet else ""
        keyboard.append([InlineKeyboardButton(
            f"{check}🍴 Без ограничений",
            callback_data=f"excl_diet_set_none_{user_id}"
        )])

        # Добавляем типы диет
        for dt in diet_types:
            check = "✅ " if current_diet == dt["code"] else ""
            icon = dt.get("icon", "")
            keyboard.append([InlineKeyboardButton(
                f"{check}{icon} {dt['name']}",
                callback_data=f"excl_diet_set_{dt['code']}_{user_id}"
            )])

        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"excl_menu_{user_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception as e:
            # Игнорируем ошибку "Message is not modified"
            if "Message is not modified" not in str(e):
                logger.error(f"Error editing diet menu: {e}")

    async def set_diet_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE, diet_code: str):
        """Установить тип питания"""
        user_id = update.effective_user.id
        query = update.callback_query

        logger.info(f"Setting diet type '{diet_code}' for user {user_id}")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Сначала проверяем текущий тип диеты
                current_response = await client.get(f"{USER_SERVICE_URL}/users/{user_id}/exclusions")
                if current_response.status_code == 200:
                    current_data = current_response.json().get("data", {})
                    current_diet = current_data.get("diet_type_code")

                    # Если уже выбран этот тип — просто показываем уведомление
                    if (diet_code == "none" and not current_diet) or (diet_code == current_diet):
                        await query.answer("Этот тип питания уже выбран", show_alert=False)
                        return

                # Обновляем тип питания
                response = await client.put(
                    f"{USER_SERVICE_URL}/users/{user_id}/exclusions",
                    json={"diet_type_code": diet_code if diet_code != "none" else ""}
                )

                logger.info(f"User-service response: {response.status_code}")

                if response.status_code == 200:
                    if diet_code == "none":
                        await query.answer("Тип питания сброшен", show_alert=False)
                    else:
                        await query.answer("Тип питания обновлён", show_alert=False)
                    # Возвращаемся к меню выбора диеты
                    await self.show_diet_menu(update, context)
                else:
                    logger.error(f"User-service error: {response.text}")
                    await query.answer("Ошибка сохранения", show_alert=True)

        except Exception as e:
            logger.error(f"Error setting diet type: {e}", exc_info=True)
            await query.answer("Ошибка соединения", show_alert=True)

    async def show_categories_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать меню категорий исключений"""
        user_id = update.effective_user.id
        query = update.callback_query

        try:
            async with httpx.AsyncClient() as client:
                # Получаем все категории
                cat_response = await client.get(f"{USER_SERVICE_URL}/exclusions/categories")
                categories = cat_response.json().get("data", []) if cat_response.status_code == 200 else []

                # Получаем текущие исключения пользователя
                user_response = await client.get(f"{USER_SERVICE_URL}/users/{user_id}/exclusions")
                user_data = user_response.json().get("data", {}) if user_response.status_code == 200 else {}

                # Категории от диеты (нельзя убрать)
                all_excluded = set(user_data.get("all_excluded_categories", []))
                user_categories = set(user_data.get("excluded_categories", []))
                diet_code = user_data.get("diet_type_code")
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            await query.answer("Ошибка загрузки данных", show_alert=True)
            return

        text = "📋 *Категории исключений*\n\n"
        if diet_code:
            text += f"_Некоторые категории исключены из-за типа питания._\n\n"
        text += "_Нажмите на категорию, чтобы добавить/убрать её._\n"

        keyboard = []

        for cat in categories:
            code = cat["code"]
            icon = cat.get("icon", "")

            # Определяем состояние
            if code in all_excluded and code not in user_categories:
                # Исключено из-за диеты - показываем как заблокированное
                status = "🔒"
                callback = f"excl_cat_locked_{code}_{user_id}"
            elif code in user_categories:
                # Выбрано пользователем
                status = "✅"
                callback = f"excl_cat_toggle_{code}_{user_id}"
            else:
                # Не выбрано
                status = "⬜"
                callback = f"excl_cat_toggle_{code}_{user_id}"

            keyboard.append([InlineKeyboardButton(
                f"{status} {icon} {cat['name']}",
                callback_data=callback
            )])

        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"excl_menu_{user_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    async def toggle_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE, category_code: str):
        """Включить/выключить категорию"""
        user_id = update.effective_user.id
        query = update.callback_query

        try:
            async with httpx.AsyncClient() as client:
                # Получаем текущие категории
                response = await client.get(f"{USER_SERVICE_URL}/users/{user_id}/exclusions")
                data = response.json().get("data", {}) if response.status_code == 200 else {}
                current_categories = data.get("excluded_categories", [])

                # Переключаем
                if category_code in current_categories:
                    current_categories.remove(category_code)
                    action = "убрана"
                else:
                    current_categories.append(category_code)
                    action = "добавлена"

                # Сохраняем
                response = await client.put(
                    f"{USER_SERVICE_URL}/users/{user_id}/exclusions",
                    json={"excluded_categories": current_categories}
                )

                if response.status_code == 200:
                    await query.answer(f"Категория {action}", show_alert=False)
                    await self.show_categories_menu(update, context)
                else:
                    await query.answer("Ошибка сохранения", show_alert=True)

        except Exception as e:
            logger.error(f"Error toggling category: {e}")
            await query.answer("Ошибка соединения", show_alert=True)

    async def show_products_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать меню чёрного списка продуктов"""
        user_id = update.effective_user.id
        query = update.callback_query

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{USER_SERVICE_URL}/users/{user_id}/exclusions")
                data = response.json().get("data", {}) if response.status_code == 200 else {}
                products = data.get("excluded_products", [])
        except Exception as e:
            logger.error(f"Error getting products: {e}")
            products = []

        text = "🛒 *Чёрный список продуктов*\n\n"

        if products:
            text += "_Ваши исключённые продукты:_\n\n"
            for i, product in enumerate(products[:15], 1):  # Показываем максимум 15
                text += f"{i}. {product}\n"
            if len(products) > 15:
                text += f"\n_...и ещё {len(products) - 15} продуктов_\n"
        else:
            text += "_Список пуст. Добавьте продукты, которые не хотите видеть в корзине._\n"

        text += "\n_Нажмите на продукт, чтобы удалить его из списка._"

        keyboard = []

        # Кнопки для удаления продуктов (первые 8)
        for product in products[:8]:
            keyboard.append([InlineKeyboardButton(
                f"❌ {product}",
                callback_data=f"excl_prod_del_{hash(product) % 100000}_{user_id}"
            )])
            # Сохраняем маппинг hash -> product в context
            if not context.user_data.get("product_hashes"):
                context.user_data["product_hashes"] = {}
            context.user_data["product_hashes"][hash(product) % 100000] = product

        keyboard.append([InlineKeyboardButton("➕ Добавить продукт", callback_data=f"excl_prod_add_{user_id}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"excl_menu_{user_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    async def start_add_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать добавление продукта"""
        user_id = update.effective_user.id
        query = update.callback_query

        self.waiting_for_product[user_id] = True

        await query.edit_message_text(
            "🛒 *Добавление продукта в чёрный список*\n\n"
            "Отправьте название продукта, который хотите исключить.\n\n"
            "_Примеры: креветки, арахис, соевый соус_\n\n"
            "Для отмены отправьте /cancel",
            parse_mode="Markdown"
        )
        await query.answer()

    async def handle_product_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Обработать ввод продукта. Возвращает True если обработано."""
        user_id = update.effective_user.id

        if not self.waiting_for_product.get(user_id):
            return False

        product_name = update.message.text.strip()

        # Отмена
        if product_name.lower() in ["/cancel", "отмена"]:
            self.waiting_for_product[user_id] = False
            await update.message.reply_text("❌ Добавление отменено")
            return True

        # Добавляем продукт
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{USER_SERVICE_URL}/users/{user_id}/exclusions/products",
                    json={"product_name": product_name}
                )

                if response.status_code == 200:
                    self.waiting_for_product[user_id] = False

                    # Показываем меню продуктов
                    keyboard = [[InlineKeyboardButton(
                        "📋 К списку продуктов",
                        callback_data=f"excl_products_menu_{user_id}"
                    )]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await update.message.reply_text(
                        f"✅ Продукт *{product_name}* добавлен в чёрный список",
                        reply_markup=reply_markup,
                        parse_mode="Markdown"
                    )
                else:
                    await update.message.reply_text("❌ Ошибка добавления. Попробуйте ещё раз.")

        except Exception as e:
            logger.error(f"Error adding product: {e}")
            await update.message.reply_text("❌ Ошибка соединения. Попробуйте позже.")

        return True

    async def delete_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE, product_hash: int):
        """Удалить продукт из чёрного списка"""
        user_id = update.effective_user.id
        query = update.callback_query

        # Получаем название продукта по хешу
        product_name = context.user_data.get("product_hashes", {}).get(product_hash)

        if not product_name:
            await query.answer("Продукт не найден", show_alert=True)
            return

        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{USER_SERVICE_URL}/users/{user_id}/exclusions/products/{product_name}"
                )

                if response.status_code == 200:
                    await query.answer(f"Продукт удалён", show_alert=False)
                    await self.show_products_menu(update, context)
                else:
                    await query.answer("Ошибка удаления", show_alert=True)

        except Exception as e:
            logger.error(f"Error deleting product: {e}")
            await query.answer("Ошибка соединения", show_alert=True)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """
        Обработать callback от исключений.
        Возвращает True если callback обработан.
        """
        query = update.callback_query
        data = query.data

        if not data.startswith("excl_"):
            return False

        user_id = update.effective_user.id
        logger.info(f"Handling exclusion callback: {data} from user {user_id}")

        # Парсим callback
        if data.startswith("excl_menu_"):
            await self.show_exclusions_menu(update, context)

        elif data.startswith("excl_diet_menu_"):
            await self.show_diet_menu(update, context)

        elif data.startswith("excl_diet_set_none_"):
            await self.set_diet_type(update, context, "none")

        elif data.startswith("excl_diet_set_"):
            # excl_diet_set_{code}_{user_id}
            parts = data.split("_")
            diet_code = parts[3]
            await self.set_diet_type(update, context, diet_code)

        elif data.startswith("excl_cat_menu_"):
            await self.show_categories_menu(update, context)

        elif data.startswith("excl_cat_toggle_"):
            # excl_cat_toggle_{code}_{user_id}
            parts = data.split("_")
            category_code = parts[3]
            await self.toggle_category(update, context, category_code)

        elif data.startswith("excl_cat_locked_"):
            await query.answer("Эта категория исключена из-за типа питания", show_alert=True)

        elif data.startswith("excl_products_menu_"):
            await self.show_products_menu(update, context)

        elif data.startswith("excl_prod_add_"):
            await self.start_add_product(update, context)

        elif data.startswith("excl_prod_del_"):
            # excl_prod_del_{hash}_{user_id}
            parts = data.split("_")
            product_hash = int(parts[3])
            await self.delete_product(update, context, product_hash)

        elif data.startswith("excl_back_settings_"):
            # Возвращаемся к основным настройкам
            await query.answer()
            # Вызываем показ основного меню настроек (будет обработано в main.py)
            return False  # Передаём обработку в main.py

        else:
            return False

        return True


# Глобальный экземпляр обработчика
exclusions_handler = ExclusionsHandler()
