"""
Генератор PDF-отчетов по заказам
Использует reportlab для создания PDF с поддержкой кириллицы
"""
import io
import json
import logging
from decimal import Decimal
from typing import Dict, Any, List, Optional
from datetime import datetime

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, 
    Spacer, PageBreak, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Цветовая схема (серо-белая)
GREY_BG = HexColor('#4A4A4A')  # Темно-серый фон для заголовков
WHITE = colors.white
LIGHT_GREY = HexColor('#F5F5F5')  # Очень светлый серый для чередующихся строк
DARK_GREY = HexColor('#2C2C2C')  # Темно-серый для текста


class OrderReportGenerator:
    """Генератор PDF-отчетов по заказам"""
    
    def __init__(self, order_id: int, db: AsyncSession):
        self.order_id = order_id
        self.db = db
        self.styles = getSampleStyleSheet()
        self._setup_fonts()
        self._setup_custom_styles()
    
    def _setup_fonts(self):
        """Настройка шрифтов с поддержкой кириллицы"""
        # Список возможных путей к шрифтам DejaVuSans
        possible_font_paths = [
            # macOS (Homebrew) - актуальный путь
            '/opt/homebrew/Caskroom/font-dejavu/2.37/dejavu-fonts-ttf-2.37/ttf/DejaVuSans.ttf',
            # Linux
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/dejavu/DejaVuSans.ttf',
            # macOS (Homebrew) - старые пути
            '/opt/homebrew/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/local/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            # macOS (системные)
            '/Library/Fonts/DejaVuSans.ttf',
            '/System/Library/Fonts/DejaVuSans.ttf',
            # Внутри проекта (если положить туда)
            './fonts/DejaVuSans.ttf',
        ]
        
        font_registered = False
        for font_path in possible_font_paths:
            try:
                import os
                if os.path.exists(font_path):
                    # Находим путь к Bold версии
                    bold_path = font_path.replace('DejaVuSans.ttf', 'DejaVuSans-Bold.ttf')
                    
                    pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
                    if os.path.exists(bold_path):
                        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', bold_path))
                    else:
                        # Используем обычный шрифт для Bold
                        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', font_path))
                    
                    self.font_name = 'DejaVuSans'
                    self.font_name_bold = 'DejaVuSans-Bold'
                    font_registered = True
                    logger.info(f"✅ DejaVuSans fonts registered from: {font_path}")
                    break
            except Exception as e:
                continue
        
        if not font_registered:
            # Fallback: используем Helvetica (стандартный шрифт reportlab)
            # Он поддерживает Latin-1, но может некорректно отображать кириллицу
            logger.warning("⚠️ DejaVuSans not found. Using Helvetica (limited Cyrillic support)")
            logger.warning("   To install DejaVu fonts:")
            logger.warning("   - macOS: brew install font-dejavu")
            logger.warning("   - Linux: sudo apt-get install fonts-dejavu-core")
            logger.warning("   - Or download from: https://dejavu-fonts.github.io/")
            
            self.font_name = 'Helvetica'
            self.font_name_bold = 'Helvetica-Bold'
    
    def _setup_custom_styles(self):
        """Настройка пользовательских стилей"""
        # Заголовок документа
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Title'],
            textColor=DARK_GREY,
            fontSize=18,
            fontName=self.font_name_bold,
            alignment=TA_CENTER,
            spaceAfter=8
        )
        
        # Подзаголовок (дата)
        self.subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=self.styles['Normal'],
            textColor=DARK_GREY,
            fontSize=10,
            fontName=self.font_name,
            alignment=TA_CENTER,
            spaceAfter=20
        )
        
        # Заголовок раздела
        self.section_header_style = ParagraphStyle(
            'SectionHeader',
            parent=self.styles['Heading1'],
            textColor=DARK_GREY,
            fontSize=14,
            fontName=self.font_name_bold,
            spaceAfter=12,
            spaceBefore=12
        )
        
        # Подзаголовок раздела
        self.subsection_header_style = ParagraphStyle(
            'SubsectionHeader',
            parent=self.styles['Heading2'],
            textColor=DARK_GREY,
            fontSize=12,
            fontName=self.font_name_bold,
            spaceAfter=8,
            spaceBefore=8
        )
        
        # Обычный текст
        self.body_style = ParagraphStyle(
            'CustomBody',
            parent=self.styles['Normal'],
            textColor=DARK_GREY,
            fontSize=9,
            fontName=self.font_name,
            spaceAfter=6
        )
        
        # Жирный текст
        self.bold_style = ParagraphStyle(
            'CustomBold',
            parent=self.styles['Normal'],
            textColor=DARK_GREY,
            fontSize=9,
            fontName=self.font_name_bold,
            spaceAfter=6
        )
        
        # Стиль для заголовков таблиц (белый текст)
        self.table_header_style = ParagraphStyle(
            'TableHeader',
            parent=self.styles['Normal'],
            textColor=WHITE,
            fontSize=9,
            fontName=self.font_name_bold,
            alignment=TA_CENTER,
            spaceAfter=0
        )
    
    async def generate_report(self) -> Optional[bytes]:
        """
        Основной метод генерации PDF
        Returns: PDF как bytes или None при ошибке
        """
        try:
            logger.info(f"📄 Starting PDF generation for order {self.order_id}")
            
            # Получаем данные
            best_basket_data = await self._get_best_basket_data()
            min_prices_data = await self._get_min_prices_data()
            mono_baskets_data = await self._get_mono_baskets_data()
            
            if not best_basket_data and not min_prices_data and not mono_baskets_data:
                logger.warning(f"⚠️ No data for PDF generation for order {self.order_id}")
                return None
            
            # Создаем PDF в памяти
            buffer = io.BytesIO()
            
            # Используем альбомную ориентацию для широких таблиц
            doc = SimpleDocTemplate(
                buffer,
                pagesize=landscape(A4),
                rightMargin=1.5*cm,
                leftMargin=1.5*cm,
                topMargin=2*cm,
                bottomMargin=2*cm
            )
            
            # Контент документа
            story = []
            
            # Заголовок
            story.append(Paragraph(f"Отчет по заказу №{self.order_id}", self.title_style))
            story.append(Paragraph(
                f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}", 
                self.subtitle_style
            ))
            story.append(Spacer(1, 0.5*cm))
            
            # Раздел 0: Лучшая корзина
            if best_basket_data:
                self._create_section0_best_basket(story, best_basket_data)
                story.append(PageBreak())
            
            # Раздел 1: Минимальные цены
            if min_prices_data:
                self._create_section1_min_prices(story, min_prices_data)
                story.append(Spacer(1, 1*cm))
            
            # Переход на новую страницу перед разделом 2
            if mono_baskets_data:
                story.append(PageBreak())
            
            # Раздел 2: Монокорзины
            if mono_baskets_data:
                self._create_section2_mono_baskets(story, mono_baskets_data)
            
            # Генерируем PDF
            doc.build(story)
            
            # Получаем bytes
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            logger.info(f"✅ PDF generated successfully: {len(pdf_bytes)} bytes")
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"❌ Error generating PDF for order {self.order_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def _get_best_basket_data(self) -> Optional[Dict]:
        """
        Получение данных лучшей корзины (rank=1)
        
        ВАЖНО: delivery_cost_model берётся из актуальных данных basket_combinations
        (которые копируются из lsd_stocks), а не из устаревших lsd_configs
        """
        try:
            # Запрос лучшей корзины
            query = """
                WITH best_basket AS (
                    SELECT basket_id
                    FROM basket_analyses
                    WHERE order_id = :order_id AND basket_rank = 1
                    LIMIT 1
                )
                SELECT 
                    ba.basket_id,
                    ba.total_cost,
                    ba.total_goods_cost,
                    ba.total_delivery_cost,
                    ba.total_loss,
                    ba.delivery_topup,
                    ba.is_mono_basket,
                    COALESCE(
                        (
                            SELECT json_agg(
                                json_build_object(
                                    'lsd_name', lc.display_name,
                                    'lsd_config_id', bc.lsd_config_id,
                                    'delivery_cost_model', bc.delivery_cost_model
                                )
                            )
                            FROM (
                                SELECT DISTINCT ON (lsd_config_id) 
                                    lsd_config_id,
                                    delivery_cost_model
                                FROM basket_combinations
                                WHERE basket_id = ba.basket_id AND order_id = :order_id
                                ORDER BY lsd_config_id, id DESC
                            ) bc
                            JOIN lsd_configs lc ON lc.id = bc.lsd_config_id
                        ),
                        '[]'::json
                    ) as lsds,
                    COALESCE(
                        (
                            SELECT json_agg(
                                json_build_object(
                                    'product_name', bc.product_name,
                                    'lsd_name', bc.lsd_name,
                                    'base_quantity', bc.base_quantity,
                                    'base_unit', bc.base_unit,
                                    'price', bc.price,
                                    'fprice', bc.fprice,
                                    'fprice_min', bc.fprice_min,
                                    'order_item_ids_cost', bc.order_item_ids_cost,
                                    'order_item_ids_quantity', bc.order_item_ids_quantity,
                                    'loss', bc.loss
                                ) ORDER BY bc.product_name
                            )
                            FROM basket_combinations bc
                            WHERE bc.basket_id = ba.basket_id AND bc.order_id = :order_id
                        ),
                        '[]'::json
                    ) as items
                FROM basket_analyses ba
                JOIN best_basket bb ON bb.basket_id = ba.basket_id
                WHERE ba.order_id = :order_id
            """
            
            result = await self.db.execute(
                text(query),
                {"order_id": self.order_id}
            )
            
            row = result.fetchone()
            if not row:
                logger.info(f"📊 No best basket found for order {self.order_id}")
                return None
            
            row_dict = dict(row._mapping)
            
            # Парсим JSON
            items = row_dict.get('items', '[]')
            if isinstance(items, str):
                items = json.loads(items)
            row_dict['items'] = items
            
            lsds = row_dict.get('lsds', '[]')
            if isinstance(lsds, str):
                lsds = json.loads(lsds)
            row_dict['lsds'] = lsds
            
            # Логируем источник delivery_cost_model
            for lsd in lsds:
                dcm = lsd.get('delivery_cost_model')
                if dcm:
                    logger.info(f"📊 [Best Basket] Using delivery_cost_model from basket_combinations for {lsd.get('lsd_name', 'unknown')}")
                else:
                    logger.warning(f"⚠️ [Best Basket] No delivery_cost_model found for {lsd.get('lsd_name', 'unknown')}")
            
            # Вычисляем total_topup
            delivery_topup = row_dict.get('delivery_topup', {})
            if isinstance(delivery_topup, str):
                delivery_topup = json.loads(delivery_topup)
            elif delivery_topup is None:
                delivery_topup = {}
            
            total_topup = sum(float(v) for v in delivery_topup.values() if v)
            row_dict['total_topup'] = total_topup
            
            # total_loss_and_delivery
            total_loss = float(row_dict.get('total_loss', 0))
            total_delivery = float(row_dict.get('total_delivery_cost', 0))
            row_dict['total_loss_and_delivery'] = total_loss + total_delivery + total_topup
            
            logger.info(f"📊 Found best basket for order {self.order_id}: basket_id={row_dict['basket_id']}")
            return row_dict
            
        except Exception as e:
            logger.error(f"❌ Error getting best basket data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def _get_min_prices_data(self) -> List[Dict]:
        """SQL-запрос для раздела 1: Минимальные цены"""
        try:
            # Читаем SQL-файл
            with open('/Users/ss/GenAI/korzinka/services/order-service/sql/get_min_prices.sql', 'r') as f:
                sql_query = f.read()
            
            result = await self.db.execute(
                text(sql_query),
                {"order_id": self.order_id}
            )
            
            rows = result.fetchall()
            
            data = []
            for row in rows:
                row_dict = dict(row._mapping)
                
                # Вычисляем формулу расчета fprice
                fprice_calculation = self._create_fprice_calculation(
                    price=Decimal(str(row_dict['price'])),
                    found_quantity=Decimal(str(row_dict['base_quantity'])),
                    found_unit=row_dict.get('found_unit', row_dict['base_unit']),
                    base_unit=row_dict['base_unit'],
                    fprice=Decimal(str(row_dict['fprice'])),
                    product_name=row_dict['product_name']
                )
                
                row_dict['fprice_calculation'] = fprice_calculation
                
                # Вычисляем сумму на полке (fprice * requested_quantity в базовых единицах)
                requested_qty = float(row_dict['requested_quantity'])
                requested_unit = row_dict['requested_unit']
                base_unit = row_dict['base_unit']
                
                # Конвертируем requested_quantity в базовые единицы
                base_requested_qty = self._convert_to_base_unit(
                    requested_qty, requested_unit, base_unit
                )
                
                shelf_total = float(row_dict['fprice']) * base_requested_qty
                row_dict['shelf_total'] = shelf_total
                
                data.append(row_dict)
            
            logger.info(f"📊 Found {len(data)} items with min prices for order {self.order_id}")
            return data
            
        except Exception as e:
            logger.error(f"❌ Error getting min prices data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    async def _get_mono_baskets_data(self) -> List[Dict]:
        """SQL-запрос для раздела 2: Все попытки поиска по LSD (с найденными и не найденными товарами)"""
        try:
            # Читаем новый SQL-файл
            with open('/Users/ss/GenAI/korzinka/services/order-service/sql/get_all_lsd_attempts.sql', 'r') as f:
                sql_query = f.read()

            result = await self.db.execute(
                text(sql_query),
                {"order_id": self.order_id}
            )

            rows = result.fetchall()

            data = []
            for row in rows:
                row_dict = dict(row._mapping)

                # Парсим JSON с оптимизированными товарами
                found_items_json = row_dict.get('found_items', '[]')
                if isinstance(found_items_json, str):
                    found_items = json.loads(found_items_json)
                else:
                    found_items = found_items_json
                row_dict['found_items'] = found_items

                # Парсим JSON с найденными, но не выбранными товарами
                found_but_not_optimized_json = row_dict.get('found_but_not_optimized_items', '[]')
                if isinstance(found_but_not_optimized_json, str):
                    found_but_not_optimized = json.loads(found_but_not_optimized_json)
                else:
                    found_but_not_optimized = found_but_not_optimized_json
                row_dict['found_but_not_optimized_items'] = found_but_not_optimized

                # Парсим JSON с не найденными товарами
                not_found_items_json = row_dict.get('not_found_items', '[]')
                if isinstance(not_found_items_json, str):
                    not_found_items = json.loads(not_found_items_json)
                else:
                    not_found_items = not_found_items_json
                row_dict['not_found_items'] = not_found_items

                # Получаем данные о доставке и топапе
                delivery_cost = float(row_dict.get('delivery_cost', 0)) if row_dict.get('delivery_cost') is not None else 0
                topup = float(row_dict.get('topup', 0)) if row_dict.get('topup') is not None else 0
                total_goods = float(row_dict.get('total_goods_cost', 0))
                total_loss = float(row_dict.get('total_loss', 0))

                row_dict['delivery_cost'] = delivery_cost
                row_dict['topup'] = topup

                # Вычисляем общую стоимость
                total_cost = total_goods + delivery_cost + topup
                row_dict['total_cost'] = total_cost

                # Вычисляем "итого потерь и доставок"
                row_dict['total_loss_and_delivery'] = total_loss + delivery_cost + topup

                # Логируем источник delivery_cost_model для отладки
                dcm = row_dict.get('delivery_cost_model')
                lsd_name = row_dict.get('lsd_display_name', 'unknown')
                found_count = row_dict.get('found_count', 0)
                found_but_not_optimized_count = row_dict.get('found_but_not_optimized_count', 0)
                not_found_count = row_dict.get('not_found_count', 0)

                if dcm:
                    logger.info(f"📊 [LSD Attempt] {lsd_name}: {found_count} optimized, {found_but_not_optimized_count} alternatives, {not_found_count} not found")
                else:
                    logger.warning(f"⚠️ [LSD Attempt] {lsd_name}: No delivery_cost_model found")

                data.append(row_dict)

            logger.info(f"📊 Found {len(data)} LSD attempts for order {self.order_id}")
            return data

        except Exception as e:
            logger.error(f"❌ Error getting LSD attempts data: {e}")
            import traceback
            logger.error(traceback.format_exc())

            # КРИТИЧНО: При ошибке SQL делаем rollback транзакции
            try:
                await self.db.rollback()
                logger.info("🔄 Transaction rolled back after SQL error")
            except Exception as rollback_error:
                logger.error(f"❌ Error during rollback: {rollback_error}")

            return []
    
    def _convert_to_base_unit(self, quantity: float, from_unit: str, to_unit: str) -> float:
        """Конвертация количества из одной единицы в другую"""
        # Упрощенная версия - предполагаем что единицы совпадают
        # TODO: Добавить полную логику конвертации
        return quantity
    
    def _create_fprice_calculation(
        self, 
        price: Decimal, 
        found_quantity: Decimal,
        found_unit: str, 
        base_unit: str, 
        fprice: Decimal,
        product_name: str = None
    ) -> str:
        """
        Формирование формулы расчёта fprice
        Примеры:
        - "160 руб / 0.25 кг = 640 руб/кг"
        - "105 руб / 0.93 л = 112.9 руб/л"
        - "119 руб / 10 шт = 11.9 руб/шт"
        """
        try:
            # Извлекаем только единицу измерения из found_unit
            import re
            unit_clean = re.sub(r'[\d\s,\.]+', '', found_unit).strip().lower()
            
            # Проверяем на яйца (если нужен коэффициент)
            from shared.utils.egg_categories import get_egg_category_coefficient
            egg_coef = get_egg_category_coefficient(product_name) if product_name else 1.0
            
            if egg_coef != 1.0:
                # Для яиц: цена / количество / коэффициент
                formula = f"{float(price):.2f} руб / {float(found_quantity):.2f} {unit_clean} / {egg_coef} = {float(fprice):.2f} руб/{base_unit}"
            else:
                # Обычная формула: цена / количество
                formula = f"{float(price):.2f} руб / {float(found_quantity):.2f} {unit_clean} = {float(fprice):.2f} руб/{base_unit}"
            
            return formula

        except Exception as e:
            logger.error(f"❌ Error creating fprice calculation: {e}")
            return f"{float(fprice):.2f} руб/{base_unit}"

    def _format_topup_with_lsd_names(self, data: Dict) -> str:
        """
        Форматирует топап с указанием названий LSD в скобках

        Args:
            data: Данные корзины, содержащие lsds (список LSD с name и lsd_name)
                  и delivery_topup из basket_analyses

        Returns:
            Строка вида "Топап: 22.00 руб (Глобус), 25.00 руб (Пятёрочка)" или "Топап: 0.00 руб"
        """
        try:
            # Получаем delivery_topup из basket_analyses
            # Формат: {"globus": 22.0, "5ka": 25.0} (ключи - это lsd.name из lsd_configs)
            delivery_topup_raw = data.get('delivery_topup')

            # Парсим JSON если нужно
            if isinstance(delivery_topup_raw, str):
                delivery_topup = json.loads(delivery_topup_raw)
            elif delivery_topup_raw is None:
                delivery_topup = {}
            else:
                delivery_topup = delivery_topup_raw

            # Если топапа нет, возвращаем 0.00
            if not delivery_topup or not any(v for v in delivery_topup.values() if v):
                return "Топап: 0.00 руб"

            # Создаем маппинг lsd.name -> lsd.display_name из lsds
            lsds = data.get('lsds', [])
            name_to_display = {}
            for lsd in lsds:
                # Извлекаем name из query результата
                # В SQL используется JOIN lsd_configs lc ON lc.id = bc.lsd_config_id
                # но мы получаем lsd_name (display_name) напрямую
                # Нужно получить и name тоже
                pass

            # ПРОБЛЕМА: В текущем SQL запросе мы не получаем lsd.name (только lsd_name = display_name)
            # Решение: Получить маппинг из базы данных синхронно или добавить в SQL
            # Для быстрого фикса используем хардкод маппинга известных LSD

            # Временный хардкод маппинг (TODO: получать из базы)
            known_lsd_names = {
                'globus': 'Глобус',
                '5ka': 'Пятёрочка',
                'yandex': 'Яндекс Лавка',
                'samokat': 'Самокат',
                'vkusvill': 'ВкусВилл',
                'metro': 'METRO',
                'lenta': 'Лента',
                'perekrestok': 'Перекрёсток',
                'okmarket': 'Окей',
                'magnit': 'Магнит'
            }

            # Формируем список строк вида "22.00 руб (Глобус)"
            topup_parts = []
            for lsd_code, amount in delivery_topup.items():
                if amount and amount > 0:
                    display_name = known_lsd_names.get(lsd_code, lsd_code.title())
                    topup_parts.append(f"{float(amount):.2f} руб ({display_name})")

            if not topup_parts:
                return "Топап: 0.00 руб"

            return "Топап: " + ", ".join(topup_parts)

        except Exception as e:
            logger.error(f"❌ Error formatting topup with LSD names: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Fallback: показываем общую сумму
            total_topup = data.get('total_topup', 0)
            return f"Топап: {float(total_topup):.2f} руб"

    def _create_section0_best_basket(self, story, data: Dict):
        """Создание раздела 0 в PDF: Лучшая корзина"""
        try:
            # Общая информация
            total_cost = float(data['total_cost'])
            total_goods = float(data['total_goods_cost'])
            total_delivery = float(data['total_delivery_cost'])
            total_loss = float(data['total_loss'])
            total_topup = data['total_topup']
            total_loss_and_delivery = data['total_loss_and_delivery']

            is_mono = data.get('is_mono_basket', False)
            lsds = data.get('lsds', [])
            lsd_names = ", ".join([lsd['lsd_name'] for lsd in lsds])

            basket_type = "Моно-корзина" if is_mono else "Комбинированная корзина"

            # Первая строка: Лучшая корзина | Сервисы | ВСЕГО (без упоминания типа корзины)
            header_line = f"<b>Лучшая корзина</b> | Сервисы: {lsd_names} | <b>ВСЕГО к оплате: {total_cost:.2f} руб</b>"
            story.append(Paragraph(header_line, self.section_header_style))
            story.append(Spacer(1, 0.2*cm))

            # Формируем строку топапа с указанием LSD
            topup_str = self._format_topup_with_lsd_names(data)

            # Вторая строка: детали
            details_line = f"Товары: {total_goods:.2f} руб | {topup_str} | Доставка: {total_delivery:.2f} руб | Потери: {total_loss:.2f} руб | Итого потерь и доставок: {total_loss_and_delivery:.2f} руб"
            story.append(Paragraph(details_line, self.body_style))
            story.append(Spacer(1, 0.3*cm))
            
            # Таблица товаров (на всю страницу)
            items = data.get('items', [])
            if items:
                items_table_data = [
                    [
                        Paragraph('Товар', self.table_header_style),
                        Paragraph('Сервис', self.table_header_style),
                        Paragraph('Лучшая цена<br/>(за кг|л)', self.table_header_style),
                        Paragraph('Цена<br/>(за кг|л)', self.table_header_style),
                        Paragraph('Цена<br/>на полке', self.table_header_style),
                        Paragraph('Кол-во<br/>(кг|л)', self.table_header_style),
                        Paragraph('Ед.изм', self.table_header_style),
                        Paragraph('Количество<br/>штук', self.table_header_style),
                        Paragraph('Стоимость<br/>на полке', self.table_header_style),
                        Paragraph('Потери', self.table_header_style)
                    ]
                ]
                
                for item in items:
                    # Первая буква заглавная
                    product_name = item['product_name']
                    if product_name:
                        product_name = product_name[0].upper() + product_name[1:] if len(product_name) > 1 else product_name.upper()
                    
                    loss = float(item.get('loss', 0))
                    
                    items_table_data.append([
                        Paragraph(product_name, self.body_style),
                        Paragraph(item['lsd_name'], self.body_style),
                        Paragraph(f"{float(item.get('fprice_min', 0)):.2f}", self.body_style),
                        Paragraph(f"{float(item['fprice']):.2f}", self.body_style),
                        Paragraph(f"{float(item['price']):.2f}", self.body_style),
                        Paragraph(f"{float(item['base_quantity']):.2f}", self.body_style),
                        Paragraph(item['base_unit'], self.body_style),
                        Paragraph(f"{float(item.get('order_item_ids_quantity', 0)):.2f}", self.body_style),
                        Paragraph(f"{float(item['order_item_ids_cost']):.2f}", self.body_style),
                        Paragraph(f"{loss:.2f}", self.body_style)
                    ])
                
                # Таблица на всю ширину страницы
                page_width = landscape(A4)[0] - 3*cm  # Вычитаем маргины
                items_table = Table(items_table_data, colWidths=[
                    page_width * 0.25,  # Товар (фиксированная ширина)
                    None,  # Сервис (автоматически)
                    None,  # Лучшая цена (за кг|л)
                    None,  # Цена (за кг|л)
                    None,  # Цена на полке
                    None,  # Кол-во (кг|л)
                    None,  # Ед.изм
                    None,  # Количество штук
                    None,  # Стоимость на полке
                    None   # Потери
                ])
                
                items_table.setStyle(TableStyle([
                    # Заголовок
                    ('BACKGROUND', (0, 0), (-1, 0), GREY_BG),
                    ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),  # Белый текст
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, 0), self.font_name_bold),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    
                    # Данные
                    ('ALIGN', (0, 1), (-1, -1), 'CENTER'),  # По центру горизонтально
                    ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),  # По центру вертикально
                    ('FONTNAME', (0, 1), (-1, -1), self.font_name),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_GREY]),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
                ]))
                
                story.append(items_table)
            
            # Добавляем условия доставки в виде горизонтальной таблицы
            lsds = data.get('lsds', [])
            if lsds:
                story.append(Spacer(1, 0.5*cm))
                story.append(Paragraph("<b>Условия доставки по сервисам:</b>", self.bold_style))
                story.append(Spacer(1, 0.2*cm))
                
                delivery_table = self._create_delivery_conditions_table(lsds)
                if delivery_table:
                    story.append(delivery_table)
                else:
                    # Fallback если таблица не создалась
                    story.append(Paragraph("Не удалось загрузить условия доставки", self.body_style))
            
        except Exception as e:
            logger.error(f"❌ Error creating section 0: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _create_section1_min_prices(self, story, data: List[Dict]):
        """Создание раздела 1 в PDF: Минимальные цены"""
        try:
            # Заголовок раздела
            story.append(Paragraph("1. Минимальные цены (без переплат)", self.section_header_style))
            story.append(Spacer(1, 0.3*cm))
            
            # Подготовка данных для таблицы
            table_data = [
                # Заголовки
                [
                    Paragraph('Товар в заказе', self.table_header_style),
                    Paragraph('Сервис', self.table_header_style),
                    Paragraph('Лучшая цена<br/>(за кг|л)', self.table_header_style),
                    Paragraph('Ед.<br/>изм.', self.table_header_style),
                    Paragraph('Кол-во<br/>(кг|л)', self.table_header_style),
                    Paragraph('Цена<br/>на полке', self.table_header_style),
                    Paragraph('Сумма на<br/>полке', self.table_header_style),
                    Paragraph('Кол-во в<br/>заказе', self.table_header_style),
                    Paragraph('Ед. изм.<br/>в заказе', self.table_header_style),
                    Paragraph('Формула расчета<br/>базовой цены', self.table_header_style)
                ]
            ]
            
            # Данные
            for item in data:
                # Первая буква товара заглавная
                product_name = item['product_name']
                if product_name:
                    product_name = product_name[0].upper() + product_name[1:] if len(product_name) > 1 else product_name.upper()
                
                # Используем order_item_ids_cost для суммы на полке
                shelf_total = float(item.get('order_item_ids_cost', 0))
                
                table_data.append([
                    Paragraph(product_name, self.body_style),
                    Paragraph(item['lsd_names'], self.body_style),
                    Paragraph(f"{float(item['fprice']):.2f}", self.body_style),
                    Paragraph(item['base_unit'], self.body_style),
                    Paragraph(f"{float(item['base_quantity']):.2f}", self.body_style),
                    Paragraph(f"{float(item['price']):.2f}", self.body_style),
                    Paragraph(f"{shelf_total:.2f}", self.body_style),
                    Paragraph(f"{float(item['requested_quantity']):.2f}", self.body_style),
                    Paragraph(item['requested_unit'], self.body_style),
                    Paragraph(item['fprice_calculation'], self.body_style)
                ])
            
            # Создаем таблицу на всю ширину страницы
            page_width = landscape(A4)[0] - 3*cm  # Вычитаем маргины
            table = Table(table_data, colWidths=[
                page_width * 0.20,  # Товар в заказе (фиксированная ширина)
                None,  # Сервис (автоматически)
                None,  # Лучшая цена (за кг|л)
                None,  # Ед. изм.
                None,  # Кол-во (кг|л)
                None,  # Цена на полке
                None,  # Сумма на полке
                None,  # Кол-во в заказе
                None,  # Ед. изм. в заказе
                page_width * 0.30   # Формула (фиксированная для читаемости)
            ])
            
            # Стиль таблицы
            table.setStyle(TableStyle([
                # Заголовок
                ('BACKGROUND', (0, 0), (-1, 0), GREY_BG),
                ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),  # Белый текст
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), self.font_name_bold),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                
                # Данные
                ('ALIGN', (0, 1), (-1, -1), 'CENTER'),  # Все ячейки по центру
                ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),  # Вертикально по центру
                ('FONTNAME', (0, 1), (-1, -1), self.font_name),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                
                # Чередующиеся строки
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_GREY]),
                
                # Границы
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            
            story.append(table)
            
        except Exception as e:
            logger.error(f"❌ Error creating section 1: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _create_section2_mono_baskets(self, story, data: List[Dict]):
        """Создание раздела 2 в PDF: Попытки поиска по всем LSD"""
        try:
            # Заголовок раздела
            story.append(Paragraph("2. Монокорзины (детальная информация по сервисам)", self.section_header_style))
            story.append(Spacer(1, 0.1*cm))

            # Если данных нет совсем (не проводился поиск)
            if not data or len(data) == 0:
                story.append(Spacer(1, 0.3*cm))
                story.append(Paragraph(
                    "Данные о поиске товаров отсутствуют.",
                    self.body_style
                ))
                logger.info("ℹ️ [PDF] Mono-baskets section: No LSD search data found")
                return
            
            for idx, lsd_data in enumerate(data, 1):
                # Подзаголовок с названием LSD
                lsd_name = lsd_data['lsd_display_name']
                total_cost = float(lsd_data.get('total_cost', 0))
                can_fulfill = lsd_data.get('can_fulfill_order', False)
                found_count = lsd_data.get('found_count', 0)
                not_found_count = lsd_data.get('not_found_count', 0)

                # Формируем заголовок в зависимости от того, можно ли собрать заказ
                if can_fulfill and found_count > 0:
                    header_text = f"2.{idx}. {lsd_name} - {total_cost:.2f} руб"
                elif found_count > 0:
                    header_text = f"2.{idx}. {lsd_name} - не удалось собрать полный заказ"
                else:
                    header_text = f"2.{idx}. {lsd_name} - товары не найдены"

                story.append(Paragraph(header_text, self.subsection_header_style))

                # Подготовка итогов
                total_goods = float(lsd_data.get('total_goods_cost', 0))
                topup = float(lsd_data.get('topup', 0))
                delivery_cost = float(lsd_data.get('delivery_cost', 0))
                total_loss = float(lsd_data.get('total_loss', 0))
                total_loss_and_delivery = float(lsd_data.get('total_loss_and_delivery', 0))

                # Найденные товары
                found_items = lsd_data.get('found_items', [])
                if found_items:
                    story.append(Paragraph("<b>Найдено:</b>", self.bold_style))
                    story.append(Spacer(1, 0.1*cm))

                    items_table_data = [
                        [
                            Paragraph('Товар', self.table_header_style),
                            Paragraph('Лучшая цена<br/>(за кг|л)', self.table_header_style),
                            Paragraph('Цена<br/>(за кг|л)', self.table_header_style),
                            Paragraph('Кол-во<br/>(кг|л)', self.table_header_style),
                            Paragraph('Ед.изм', self.table_header_style),
                            Paragraph('Кол-во<br/>штук', self.table_header_style),
                            Paragraph('Цена<br/>на полке', self.table_header_style),
                            Paragraph('Стоимость<br/>на полке', self.table_header_style),
                            Paragraph('Потери', self.table_header_style)
                        ]
                    ]

                    for item in found_items:
                        # Первая буква заглавная
                        product_name = item['product_name']
                        if product_name:
                            product_name = product_name[0].upper() + product_name[1:] if len(product_name) > 1 else product_name.upper()

                        # Используем готовое значение loss из SQL-запроса
                        loss = float(item.get('loss', 0))

                        items_table_data.append([
                            Paragraph(product_name, self.body_style),
                            Paragraph(f"{float(item.get('fprice_min', 0)):.2f}", self.body_style),
                            Paragraph(f"{float(item['fprice']):.2f}", self.body_style),
                            Paragraph(f"{float(item['base_quantity']):.2f}", self.body_style),
                            Paragraph(item['base_unit'], self.body_style),
                            Paragraph(f"{float(item.get('order_item_ids_quantity', 0)):.2f}", self.body_style),
                            Paragraph(f"{float(item['price']):.2f}", self.body_style),
                            Paragraph(f"{float(item['order_item_ids_cost']):.2f}", self.body_style),
                            Paragraph(f"{loss:.2f}", self.body_style)
                        ])

                    # Таблица на всю ширину страницы
                    page_width = landscape(A4)[0] - 3*cm
                    items_table = Table(items_table_data, colWidths=[
                        page_width * 0.25,  # Товар (фиксированная ширина)
                        None,  # Лучшая цена (за кг|л)
                        None,  # Цена (за кг|л)
                        None,  # Кол-во (кг|л)
                        None,  # Ед.изм
                        None,  # Кол-во штук
                        None,  # Цена на полке
                        None,  # Стоимость на полке
                        None   # Потери
                    ])

                    items_table.setStyle(TableStyle([
                        # Заголовок
                        ('BACKGROUND', (0, 0), (-1, 0), GREY_BG),
                        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('FONTNAME', (0, 0), (-1, 0), self.font_name_bold),
                        ('FONTSIZE', (0, 0), (-1, 0), 9),

                        # Данные
                        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),  # Все по центру
                        ('FONTNAME', (0, 1), (-1, -1), self.font_name),
                        ('FONTSIZE', (0, 1), (-1, -1), 8),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_GREY]),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                        ('LEFTPADDING', (0, 0), (-1, -1), 4),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                        ('TOPPADDING', (0, 0), (-1, -1), 6),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
                    ]))

                    story.append(items_table)
                    story.append(Spacer(1, 0.3*cm))

                # Найденные, но не выбранные товары (альтернативы)
                found_but_not_optimized = lsd_data.get('found_but_not_optimized_items', [])
                if found_but_not_optimized:
                    story.append(Paragraph("<b>Найдено, но не включено в оптимальную корзину:</b>", self.bold_style))
                    story.append(Spacer(1, 0.1*cm))

                    # Список альтернативных товаров с указанием разницы в цене
                    alternative_lines = []
                    for item in found_but_not_optimized:
                        product_name = item['product_name']
                        if product_name:
                            product_name = product_name[0].upper() + product_name[1:] if len(product_name) > 1 else product_name.upper()

                        fprice = float(item.get('fprice', 0))
                        fprice_min = float(item.get('fprice_min', 0))
                        price_diff = float(item.get('price_diff', 0))
                        requested_qty = item.get('requested_quantity', '')
                        requested_unit = item.get('requested_unit', '')

                        # Формируем строку с указанием, насколько дороже
                        if price_diff > 0:
                            alternative_lines.append(
                                f"• {product_name} ({requested_qty} {requested_unit}) - {fprice:.2f} руб/{item.get('base_unit', 'ед')}, "
                                f"дороже на {price_diff:.2f} руб (оптимум: {fprice_min:.2f} руб/{item.get('base_unit', 'ед')})"
                            )
                        else:
                            # Если нет разницы (например, это и есть минимум)
                            alternative_lines.append(
                                f"• {product_name} ({requested_qty} {requested_unit}) - {fprice:.2f} руб/{item.get('base_unit', 'ед')}"
                            )

                    story.append(Paragraph("<br/>".join(alternative_lines), self.body_style))
                    story.append(Spacer(1, 0.3*cm))

                # Не найденные товары
                not_found_items = lsd_data.get('not_found_items', [])
                if not_found_items:
                    story.append(Paragraph("<b>Не найдено:</b>", self.bold_style))
                    story.append(Spacer(1, 0.1*cm))

                    # Список не найденных товаров
                    not_found_lines = []
                    for item in not_found_items:
                        product_name = item['product_name']
                        if product_name:
                            product_name = product_name[0].upper() + product_name[1:] if len(product_name) > 1 else product_name.upper()

                        requested_qty = item.get('requested_quantity', '')
                        requested_unit = item.get('requested_unit', '')
                        not_found_lines.append(f"• {product_name} ({requested_qty} {requested_unit})")

                    story.append(Paragraph("<br/>".join(not_found_lines), self.body_style))
                    story.append(Spacer(1, 0.3*cm))
                
                # Итоги (только если есть найденные товары)
                if found_count > 0:
                    # Форматируем топап с названием LSD (для монокорзины - это один LSD)
                    topup_str = f"Топап: {topup:.2f} руб ({lsd_name})" if topup > 0 else f"Топап: 0.00 руб"

                    summary_lines = [
                        f"Итого товары: {total_goods:.2f} руб | ",
                        f"{topup_str} | ",
                        f"Доставка: {delivery_cost:.2f} руб | ",
                        f"Потери: {total_loss:.2f} руб"
                    ]
                    story.append(Paragraph("".join(summary_lines), self.body_style))
                    story.append(Paragraph(
                        f"<b>ВСЕГО: {total_cost:.2f} руб</b> | Итого потерь и доставок: {total_loss_and_delivery:.2f} руб",
                        self.bold_style
                    ))

                    # Добавляем условия доставки (компактный формат)
                    story.append(Spacer(1, 0.3*cm))
                    delivery_cost_model = lsd_data.get('delivery_cost_model')
                    delivery_info = self._parse_delivery_model(delivery_cost_model, compact=True)
                    story.append(Paragraph(f"<b>Условия доставки:</b> {delivery_info}", self.body_style))
                else:
                    # Если товары не найдены, показываем примечание
                    story.append(Paragraph(
                        "<i>Примечание: Товары из вашего заказа не доступны в этом сервисе.</i>",
                        self.body_style
                    ))

                # Разделитель между корзинами - НОВЫЙ ЛИСТ
                if idx < len(data):
                    story.append(PageBreak())  # Каждая монокорзина на новом листе
            
        except Exception as e:
            logger.error(f"❌ Error creating section 2: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _create_delivery_conditions_table(self, lsds: List[Dict]) -> Table:
        """
        Создание горизонтальной таблицы с условиями доставки
        
        Args:
            lsds: Список словарей с lsd_name и delivery_cost_model
        
        Returns:
            Table объект reportlab
        """
        try:
            if not lsds:
                return None
            
            # Готовим данные для таблицы
            table_data = []
            
            # Строка 1: Названия сервисов
            header_row = [Paragraph(lsd.get('lsd_name', 'Неизвестно'), self.table_header_style) for lsd in lsds]
            table_data.append(header_row)
            
            # Строка 2: Минимальная сумма заказа
            min_sum_row = []
            for lsd in lsds:
                delivery_model = lsd.get('delivery_cost_model')
                min_sum = self._extract_min_order(delivery_model)
                min_sum_row.append(Paragraph(f"Минимальная сумма заказа: {min_sum:.2f} руб", self.body_style))
            table_data.append(min_sum_row)
            
            # Строка 3: Диапазоны доставки
            ranges_row = []
            for lsd in lsds:
                delivery_model = lsd.get('delivery_cost_model')
                ranges_text = self._extract_delivery_ranges(delivery_model)
                ranges_row.append(Paragraph(ranges_text, self.body_style))
            table_data.append(ranges_row)
            
            # Создаем таблицу
            page_width = landscape(A4)[0] - 3*cm
            col_width = page_width / len(lsds)
            
            table = Table(table_data, colWidths=[col_width] * len(lsds))
            
            # Стиль таблицы
            table.setStyle(TableStyle([
                # Заголовки (серый фон)
                ('BACKGROUND', (0, 0), (-1, 0), GREY_BG),
                ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), self.font_name_bold),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                
                # Данные
                ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 1), (-1, -1), self.font_name),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [LIGHT_GREY, WHITE]),
                
                # Границы
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8)
            ]))
            
            return table
            
        except Exception as e:
            logger.error(f"❌ Error creating delivery conditions table: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _extract_min_order(self, delivery_cost_model: Any) -> float:
        """
        Извлечение минимальной суммы заказа из delivery_cost_model

        Логика:
        1. Ищем первый "блокирующий" диапазон (где fee >= max, т.е. заказ невозможен)
        2. Минимальная сумма заказа = max этого блокирующего диапазона (или min следующего диапазона)
        3. Если блокирующих диапазонов нет, возвращаем первый min

        Пример (Пятёрочка):
        [
          {"min": 0, "max": 500, "fee": 500},   // Блокирующий (fee >= max)
          {"min": 500, "max": 1200, "fee": 99}, // Первый валидный
          {"min": 1200, "max": null, "fee": 0}  // Бесплатная доставка
        ]
        Минимальная сумма = 500 (max блокирующего диапазона = min первого валидного)
        """
        try:
            if isinstance(delivery_cost_model, str):
                model = json.loads(delivery_cost_model)
            else:
                model = delivery_cost_model

            if not model or not isinstance(model, dict):
                return 0.0

            delivery_cost = model.get('delivery_cost', [])
            if not delivery_cost or not isinstance(delivery_cost, list):
                return 0.0

            # Ищем блокирующий диапазон (где fee >= max или очень высокая стоимость)
            for i, range_item in enumerate(delivery_cost):
                min_val = range_item.get('min', 0)
                max_val = range_item.get('max')
                fee = range_item.get('fee', 0)

                # Проверяем, является ли этот диапазон блокирующим
                if max_val is not None and fee is not None:
                    # Если fee >= max, это блокирующий диапазон
                    # Минимальная сумма заказа = max этого диапазона
                    if fee >= max_val:
                        return float(max_val)

            # Если блокирующих диапазонов нет, ищем первый диапазон с fee > 0
            for range_item in delivery_cost:
                min_val = range_item.get('min', 0)
                fee = range_item.get('fee')
                if fee is not None and fee > 0:
                    return float(min_val)

            # Если все диапазоны с fee = 0 (бесплатная доставка), возвращаем первый min
            first_range = delivery_cost[0] if delivery_cost else None
            if first_range:
                return float(first_range.get('min', 0))

            return 0.0

        except Exception as e:
            logger.error(f"❌ Error extracting min_order: {e}")
            return 0.0
    
    def _extract_delivery_ranges(self, delivery_cost_model: Any) -> str:
        """
        Извлечение диапазонов доставки для таблицы
        """
        try:
            if isinstance(delivery_cost_model, str):
                model = json.loads(delivery_cost_model)
            else:
                model = delivery_cost_model
            
            if not model or not isinstance(model, dict):
                return "Данные отсутствуют"
            
            delivery_cost = model.get('delivery_cost', [])
            if not delivery_cost or not isinstance(delivery_cost, list):
                return "Данные отсутствуют"
            
            ranges = []
            for range_item in delivery_cost:
                min_val = range_item.get('min', 0)
                max_val = range_item.get('max')
                fee = range_item.get('fee')
                
                if fee is None:
                    continue
                
                # Формируем строку диапазона
                if max_val is None:
                    if fee == 0:
                        ranges.append(f"От {min_val:.2f} руб: бесплатно")
                    else:
                        ranges.append(f"От {min_val:.2f} руб: {fee:.2f} руб")
                else:
                    if fee == 0:
                        ranges.append(f"От {min_val:.2f} до {max_val:.2f} руб: бесплатно")
                    else:
                        ranges.append(f"От {min_val:.2f} до {max_val:.2f} руб: {fee:.2f} руб")
            
            if not ranges:
                return "Данные отсутствуют"
            
            return "<br/>".join(ranges)
            
        except Exception as e:
            logger.error(f"❌ Error extracting delivery ranges: {e}")
            return "Ошибка при чтении"
    
    def _parse_delivery_model(self, delivery_cost_model: Any, compact: bool = False) -> str:
        """
        Парсинг JSON delivery_cost_model в читаемый формат
        Формат модели:
        {
          "delivery_cost": [
            {"min": 0, "max": 1000, "fee": 149, "label": "Def1"},
            {"min": 1000, "max": 2000, "fee": 99, "label": "Def2"},
            {"min": 2000, "max": null, "fee": 0, "label": "Def3"}
          ]
        }
        
        Args:
            delivery_cost_model: JSON с моделью стоимости доставки
            compact: если True, возвращает компактную однострочную версию
        """
        try:
            # Логируем входные данные
            logger.debug(f"🔍 [Parse Delivery] Input type: {type(delivery_cost_model).__name__}")
            if delivery_cost_model:
                logger.debug(f"🔍 [Parse Delivery] Input data: {str(delivery_cost_model)[:200]}...")
            
            if isinstance(delivery_cost_model, str):
                model = json.loads(delivery_cost_model)
            else:
                model = delivery_cost_model
            
            # Проверяем наличие данных
            if not model or not isinstance(model, dict):
                logger.warning("⚠️ delivery_cost_model is empty or not a dict")
                return "Данные отсутствуют" if compact else "• Данные о доставке отсутствуют"
            
            # Получаем массив delivery_cost
            delivery_cost = model.get('delivery_cost', [])
            
            if not delivery_cost or not isinstance(delivery_cost, list):
                logger.warning("⚠️ delivery_cost is empty or not a list")
                return "Данные отсутствуют" if compact else "• Данные о доставке отсутствуют"
            
            lines = []

            # Используем ту же логику, что и в _extract_min_order()
            min_order = self._extract_min_order(delivery_cost_model)
            
            # Компактный формат (для монокорзин)
            if compact:
                ranges = []
                for range_item in delivery_cost:
                    min_val = range_item.get('min', 0)
                    max_val = range_item.get('max')
                    fee = range_item.get('fee')
                    
                    if fee is None:
                        continue
                    
                    # Формируем компактную строку диапазона
                    if max_val is None:
                        if fee == 0:
                            ranges.append(f">{min_val:.0f}: бесплатно")
                        else:
                            ranges.append(f">{min_val:.0f}: {fee:.0f} руб")
                    else:
                        if fee == 0:
                            ranges.append(f"{min_val:.0f}-{max_val:.0f}: бесплатно")
                        else:
                            ranges.append(f"{min_val:.0f}-{max_val:.0f}: {fee:.0f} руб")
                
                min_order_str = f"{min_order:.2f}" if min_order is not None else "0.00"
                return f"Мин. сумма: {min_order_str} руб | Доставка: {', '.join(ranges)}"
            
            # Полный формат (для вертикального списка)
            lines = []
            
            if min_order is not None:
                lines.append(f"• Минимальная сумма заказа: {min_order:.2f} руб")
            
            lines.append("• Диапазоны доставки:")
            
            # Формируем диапазоны
            for range_item in delivery_cost:
                min_val = range_item.get('min', 0)
                max_val = range_item.get('max')
                fee = range_item.get('fee')
                
                if fee is None:
                    continue
                
                # Формируем строку диапазона
                if max_val is None:
                    # Без верхней границы
                    if fee == 0:
                        lines.append(f"  - От {min_val:.2f} руб: бесплатно")
                    else:
                        lines.append(f"  - От {min_val:.2f} руб: {fee:.2f} руб")
                else:
                    # С верхней границей
                    if fee == 0:
                        lines.append(f"  - От {min_val:.2f} до {max_val:.2f} руб: бесплатно")
                    else:
                        lines.append(f"  - От {min_val:.2f} до {max_val:.2f} руб: {fee:.2f} руб")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"❌ Error parsing delivery model: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return "Ошибка при чтении" if compact else "• Ошибка при чтении условий доставки"
