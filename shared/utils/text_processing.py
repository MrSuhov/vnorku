"""
Модуль для работы с текстом: синонимы, лемматизация, нормализация
"""

import re
from typing import List, Set


def get_word_synonyms(word: str) -> Set[str]:
    """Получение синонимов и вариантов написания для слова"""
    synonyms_dict = {
        # Яйца
        'яйцо': {'яйца', 'яиц', 'яйцам', 'яйцами'},
        'яйца': {'яйцо', 'яиц', 'яйцам', 'яйцами'},
        'яиц': {'яйцо', 'яйца', 'яйцам', 'яйцами'},

        # зефирчики
        'зефир': {'зефирчики'},

        # Яблоки
        'яблоко': {'яблоки', 'яблок', 'яблочко', 'яблочки'},
        'яблоки': {'яблоко', 'яблок', 'яблочко', 'яблочки'},
        'яблок': {'яблоко', 'яблоки', 'яблочко', 'яблочки'},
        
        # Гольден/Голден
        'гольден': {'голден', 'golden', 'гольдэн'},
        'голден': {'гольден', 'golden', 'гольдэн'},
        'golden': {'гольден', 'голден', 'гольдэн'},
        
        # Другие фрукты
        'банан': {'бананы', 'банана'},
        'бананы': {'банан', 'банана'},
        'апельсин': {'апельсины', 'апельсина'},
        'апельсины': {'апельсин', 'апельсина'},
        
        # Овощи
        'помидор': {'помидоры', 'помидора', 'томат', 'томаты'},
        'помидоры': {'помидор', 'помидора', 'томат', 'томаты'},
        'томат': {'томаты', 'помидор', 'помидоры'},
        'томаты': {'томат', 'помидор', 'помидоры'},
        'огурец': {'огурцы', 'огурца'},
        'огурцы': {'огурец', 'огурца'},
        'морковь': {'морковка', 'морковки'},
        'морковка': {'морковь', 'морковки'},
        
        # Молочные продукты
        'молоко': {'молока'},
        'сыр': {'сыры', 'сыра'},
        'сыры': {'сыр', 'сыра'},
        'йогурт': {'йогурты', 'йогурта'},
        'йогурты': {'йогурт', 'йогурта'},
        
        # Мясные продукты
        'сосиска': {'сосиски', 'сосисок'},
        'сосиски': {'сосиска', 'сосисок'},
        'колбаса': {'колбасы', 'колбасок'},
        'колбасы': {'колбаса', 'колбасок'},
        
        # Хлебобулочные
        'хлеб': {'хлеба', 'хлебушек'},
        'батон': {'батоны', 'батона'},
        'батоны': {'батон', 'батона'},
        'булка': {'булки', 'булочка', 'булочки'},
        'булки': {'булка', 'булочка', 'булочки'},
        
        # Напитки
        'сок': {'соки', 'сока'},
        'соки': {'сок', 'сока'},
        'вода': {'воды', 'водичка'},
        'воды': {'вода', 'водичка'},
    }
    
    return synonyms_dict.get(word.lower(), set())


def enhanced_lemmatize(word: str) -> str:
    """Улучшенная лемматизация с большим словарём"""
    word = word.lower()
    
    # Расширенный словарь лемматизации
    lemma_dict = {
        # Фрукты
        'яблоки': 'яблоко', 'яблок': 'яблоко', 'яблочко': 'яблоко', 'яблочки': 'яблоко',
        'бананы': 'банан', 'банана': 'банан', 'бананов': 'банан',
        'апельсины': 'апельсин', 'апельсина': 'апельсин', 'апельсинов': 'апельсин',
        'груши': 'груша', 'груш': 'груша', 'грушей': 'груша',
        
        # Сорта
        'гольден': 'гольден', 'голден': 'гольден', 'golden': 'гольден',
        'семеренко': 'семеренко', 'симиренко': 'семеренко',
        'антоновка': 'антоновка', 'антоновки': 'антоновка',
        
        # Овощи
        'помидоры': 'помидор', 'помидора': 'помидор', 'помидоров': 'помидор',
        'томаты': 'помидор', 'томат': 'помидор', 'томатов': 'помидор',
        'огурцы': 'огурец', 'огурца': 'огурец', 'огурцов': 'огурец',
        'морковка': 'морковь', 'морковки': 'морковь', 'морковок': 'морковь',
        'картошка': 'картофель', 'картофель': 'картофель', 'картошки': 'картофель',
        'лук': 'лук', 'лука': 'лук', 'луковица': 'лук',
        
        # Яйца
        'яйца': 'яйцо', 'яиц': 'яйцо', 'яйцам': 'яйцо', 'яйцами': 'яйцо',
        
        # Молочные продукты
        'молока': 'молоко', 'молочко': 'молоко',
        'сыры': 'сыр', 'сыра': 'сыр', 'сырок': 'сыр', 'сырочек': 'сыр',
        'йогурты': 'йогурт', 'йогурта': 'йогурт',
        'кефир': 'кефир', 'кефира': 'кефир', 'кефирчик': 'кефир',
        'сметана': 'сметана', 'сметаны': 'сметана', 'сметанка': 'сметана',
        
        # Мясные продукты
        'сосиски': 'сосиска', 'сосисок': 'сосиска', 'сосисочка': 'сосиска',
        'колбасы': 'колбаса', 'колбасок': 'колбаса', 'колбаска': 'колбаса',
        'ветчина': 'ветчина', 'ветчины': 'ветчина',
        
        # Хлебобулочные
        'хлебы': 'хлеб', 'хлеба': 'хлеб', 'хлебушек': 'хлеб',
        'батоны': 'батон', 'батона': 'батон',
        'булки': 'булка', 'булочка': 'булка', 'булочки': 'булка',
        'хлебцы': 'хлебец', 'хлебца': 'хлебец',
        
        # Напитки
        'соки': 'сок', 'сока': 'сок', 'сочок': 'сок',
        'воды': 'вода', 'водичка': 'вода', 'водочка': 'вода',
        'чай': 'чай', 'чая': 'чай', 'чаёк': 'чай',
        'кофе': 'кофе', 'кофей': 'кофе', 'кофеёк': 'кофе',
        
        # Крупы и макароны
        'рис': 'рис', 'риса': 'рис', 'рисик': 'рис',
        'гречка': 'гречка', 'гречки': 'гречка', 'гречневая': 'гречка',
        'макароны': 'макароны', 'макарон': 'макароны', 'макаронины': 'макароны',
        'спагетти': 'спагетти', 'спагеттини': 'спагетти'
    }
    
    return lemma_dict.get(word, word)


def get_processing_modifiers() -> Set[str]:
    """Список модификаторов обработки продуктов для штрафа в скоринге"""
    return {
        # Маринованные/соленые
        'маринованный', 'маринованная', 'маринованные', 'маринованных',
        'соленый', 'соленая', 'соленые', 'соленых',
        'слабосоленый', 'слабосоленая', 'слабосоленые',
        'малосольный', 'малосольная', 'малосольные',
        
        # Копченые
        'копченый', 'копченая', 'копченые', 'копченых', 'копчения',
        
        # Жареные
        'жареный', 'жаренный', 'жареная', 'жаренная', 'жареные', 'жаренные',
        'обжаренный', 'обжаренная', 'обжаренные',
        
        # Замороженные
        'замороженный', 'замороженная', 'замороженные', 'замороженных',
        'мороженый', 'мороженая', 'мороженые',
        
        # Сушеные/вяленые
        'сушеный', 'сушеная', 'сушеные', 'сушеных',
        'вяленый', 'вяленая', 'вяленые', 'вяленых',
        'сухой', 'сухая', 'сухие',
        
        # Консервированные
        'консервированный', 'консервированная', 'консервированные',
        'консервный', 'консервная', 'консервные',

        # Обработка
        'паста',
        
        # Другие виды обработки
        'тушеный', 'тушеная', 'тушеные',
        'вареный', 'вареная', 'вареные', 'вареных',
        'запеченный', 'запеченная', 'запеченные',
        'печеный', 'печеная', 'печеные',
        
        # Непищевые аксессуары к продуктам
        'термопленка', 'термоплёнка', 'термопленки', 'термоплёнки',
        'пленка', 'плёнка', 'пленки', 'плёнки',
        'наклейка', 'наклейки',
        'стикер', 'стикеры',
        'декор', 'декоративный', 'декоративная', 'декоративные',
        'украшение', 'украшения',
    }


def detect_processing_modifiers(text: str) -> Set[str]:
    """Определяет наличие модификаторов обработки в тексте
    
    Args:
        text: Нормализованный текст товара
        
    Returns:
        Множество найденных модификаторов обработки
    """
    if not text:
        return set()
    
    text_lower = text.lower()
    modifiers = get_processing_modifiers()
    found_modifiers = set()
    
    # Извлекаем слова из текста
    words = re.findall(r'\b[а-яёa-z]+\b', text_lower)
    
    for word in words:
        if word in modifiers:
            found_modifiers.add(word)
    
    return found_modifiers


def normalize_and_extract_keywords(text: str) -> List[str]:
    """Улучшенная нормализация текста и извлечение ключевых слов"""
    if not text:
        return []
    
    stop_words = {
        'шт', 'кг', 'г', 'гр', 'грамм', 'л', 'мл', 'мг', 'штук', 'штука', 'литр', 'литра', 'литров',
        'в', 'на', 'с', 'и', 'или', 'для', 'от', 'до', 'по', 'за', 'без', 'из', 'к', 'о', 
        '1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
        'упак','уп', 'упаковка', 'пакет', 'бутылка', 'банка', 'коробка', 'пачка', 'коробок'
    }
    
    text = text.lower().strip()
    # Убираем числа с единицами измерения
    text = re.sub(r'\d+\s*(г|гр|грамм|кг|мл|л|мг|шт)\b', '', text)
    text = re.sub(r'\b\d+\s*шт\b', '', text)
    text = re.sub(r'\b\d+[.,]\d+\b', '', text)  # Убираем дробные числа
    
    # Извлекаем слова (включая английские для golden)
    words = re.findall(r'\b[а-яёa-z]+\b', text)
    
    keywords = []
    for word in words:
        if len(word) >= 2 and word not in stop_words:
            normalized_word = enhanced_lemmatize(word)
            if normalized_word:  # Добавляем только если нормализация успешна
                keywords.append(normalized_word)
    
    return keywords


def extract_numeric_parameters(text: str) -> dict:
    """Извлекает числовые параметры из текста товара
    
    Args:
        text: Текст названия товара
        
    Returns:
        Словарь с извлеченными числовыми параметрами:
        {
            'percentages': [20.0],  # Список всех процентов
            'weights': [300],       # Вес в граммах (нормализованный)
            'volumes': [1000],      # Объем в мл (нормализованный)
            'pieces': [10]          # Количество штук
        }
    """
    if not text:
        return {'percentages': [], 'weights': [], 'volumes': [], 'pieces': []}
    
    text_lower = text.lower()
    result = {
        'percentages': [],
        'weights': [],
        'volumes': [],
        'pieces': []
    }
    
    # 1. Извлечение процентов жирности/содержания
    # Паттерн: 20%, 15%, 3.2%, 2,5%
    percentage_pattern = r'(\d+[.,]?\d*)\s*%'
    for match in re.finditer(percentage_pattern, text_lower):
        pct_str = match.group(1).replace(',', '.')  # Нормализуем запятую в точку
        try:
            pct_value = float(pct_str)
            result['percentages'].append(pct_value)
        except ValueError:
            continue
    
    # 2. Извлечение веса (граммы и килограммы)
    # Паттерн: 300г, 1кг, 500 г, 1.5 кг
    weight_pattern = r'(\d+[.,]?\d*)\s*(г|гр|грамм|кг)\b'
    for match in re.finditer(weight_pattern, text_lower):
        value_str = match.group(1).replace(',', '.')
        unit = match.group(2)
        try:
            value = float(value_str)
            # Нормализуем в граммы
            if unit == 'кг':
                value = value * 1000
            result['weights'].append(int(value))
        except ValueError:
            continue
    
    # 3. Извлечение объема (миллилитры и литры)
    # Паттерн: 1л, 500мл, 1.5 л
    volume_pattern = r'(\d+[.,]?\d*)\s*(мл|л|литр|литра|литров)\b'
    for match in re.finditer(volume_pattern, text_lower):
        value_str = match.group(1).replace(',', '.')
        unit = match.group(2)
        try:
            value = float(value_str)
            # Нормализуем в миллилитры
            if unit in ['л', 'литр', 'литра', 'литров']:
                value = value * 1000
            result['volumes'].append(int(value))
        except ValueError:
            continue
    
    # 4. Извлечение количества штук
    # Паттерн: 10 шт, 6 яиц, 12 штук
    pieces_pattern = r'(\d+)\s*(шт|штук|штука|яиц|яйц|яйца)\b'
    for match in re.finditer(pieces_pattern, text_lower):
        try:
            pieces = int(match.group(1))
            result['pieces'].append(pieces)
        except ValueError:
            continue
    
    return result


# ============ СЛОВАРИ ПРОДУКТОВЫХ КАТЕГОРИЙ (v5.6) ============

PRODUCT_CATEGORIES = {
    'овощи': {
        'огурец', 'помидор', 'томат', 'перец', 'баклажан', 'кабачок',
        'картофель', 'картошка', 'морковь', 'морковка', 'свекла', 'капуста', 
        'лук', 'чеснок', 'редис', 'редька', 'репа', 'тыква', 'патиссон', 
        'цуккини', 'черри'  # черри как подвид томатов
    },
    
    'фрукты': {
        'яблоко', 'груша', 'банан', 'апельсин', 'мандарин', 'лимон',
        'грейпфрут', 'киви', 'ананас', 'манго', 'персик', 'абрикос',
        'слива', 'виноград', 'арбуз', 'дыня', 'нектарин', 'гранат'
    },
    
    'ягоды': {
        'клубника', 'земляника', 'малина', 'черника', 'голубика',
        'ежевика', 'смородина', 'крыжовник', 'вишня', 'черешня'
    },
    
    'молочные': {
        'молоко', 'сметана', 'творог', 'кефир', 'йогурт', 'ряженка',
        'сливки', 'масло', 'сыр', 'простокваша', 'варенец', 'айран'
    },
    
    'мясо': {
        'курица', 'говядина', 'свинина', 'индейка', 'утка', 'баранина',
        'кролик', 'фарш', 'котлета', 'колбаса', 'сосиска', 'сардель',
        'ветчина', 'бекон', 'грудка', 'окорочок', 'филе'
    },
    
    'рыба': {
        'лосось', 'семга', 'форель', 'скумбрия', 'сельдь', 'минтай',
        'треска', 'горбуша', 'кета', 'судак', 'окунь', 'щука', 'тунец'
    },
    
    'крупы': {
        'рис', 'гречка', 'овсянка', 'перловка', 'пшено', 'манка',
        'макароны', 'спагетти', 'вермишель'
    },
    
    'зелень': {
        'укроп', 'петрушка', 'кинза', 'базилик', 'салат', 'шпинат',
        'руккола', 'щавель', 'сельдерей'
    }
}


def get_product_category(product_name: str) -> str | None:
    """Определяет категорию продукта по его названию
    
    Args:
        product_name: Нормализованное название продукта
        
    Returns:
        Название категории или None если продукт не найден
    """
    if not product_name:
        return None
    
    # Извлекаем ключевые слова (лемматизированные)
    keywords = normalize_and_extract_keywords(product_name)
    
    # Ищем первое совпадение с любой категорией
    for keyword in keywords:
        for category_name, products in PRODUCT_CATEGORIES.items():
            if keyword in products:
                return category_name
    
    return None


# Словарь частей/подвидов продуктов (не являются дополнительными продуктами)
PRODUCT_PARTS = {
    'курица': {'грудка', 'бедро', 'окорочок', 'крыло', 'филе'},
    'говядина': {'грудка', 'вырезка', 'ребра', 'фарш', 'мясо'},
    'свинина': {'грудка', 'вырезка', 'ребра', 'фарш', 'мясо'},
    'помидор': {'черри'},  # черри - подвид помидоров
    'томат': {'черри'},
}

def detect_extra_products_same_category(search_query: str, found_name: str) -> dict:
    """Детектирует наличие дополнительных продуктов ТОЙ ЖЕ категории
    
    Логика:
    1. Определяем категорию товара из search_query
    2. Ищем в found_name другие продукты из ТОЙ ЖЕ категории
    3. Исключаем продукты, которые есть в search_query
    4. Исключаем части/подвиды основного продукта
    5. Исключаем синонимы
    
    Args:
        search_query: Поисковый запрос (уже нормализованный)
        found_name: Найденное название товара (уже нормализованное)
        
    Returns:
        {
            'has_extra': bool,           # Есть ли дополнительные продукты
            'extra_products': list,      # Список найденных доп. продуктов
            'category': str | None       # Категория товара
        }
    """
    # Извлекаем ключевые слова из обоих названий
    search_keywords = normalize_and_extract_keywords(search_query)
    found_keywords = normalize_and_extract_keywords(found_name)
    
    # Определяем категорию запроса
    category = get_product_category(search_query)
    
    if not category:
        # Продукт не в наших словарях - нет штрафа
        return {
            'has_extra': False,
            'extra_products': [],
            'category': None
        }
    
    # Получаем все продукты этой категории
    category_products = PRODUCT_CATEGORIES[category]
    
    # Ищем продукты из этой категории в found_name
    found_category_products = [kw for kw in found_keywords if kw in category_products]
    
    # Ищем продукты из запроса
    search_category_products = [kw for kw in search_keywords if kw in category_products]
    
    # Находим дополнительные продукты (есть в found, но нет в search)
    extra_products = [p for p in found_category_products if p not in search_category_products]
    
    # ФИЛЬТРАЦИЯ: Убираем части/подвиды основного продукта
    filtered_extra_products = []
    for extra in extra_products:
        is_part_of_main = False
        
        # Проверяем для каждого продукта из search_query
        for search_product in search_category_products:
            # Проверяем синонимы (помидор == томат)
            synonyms = get_word_synonyms(search_product)
            if extra in synonyms or search_product in get_word_synonyms(extra):
                is_part_of_main = True
                break
            
            # Проверяем части/подвиды
            if search_product in PRODUCT_PARTS:
                if extra in PRODUCT_PARTS[search_product]:
                    is_part_of_main = True
                    break
            
            # Обратная проверка (если extra - основной продукт для search_product)
            if extra in PRODUCT_PARTS:
                if search_product in PRODUCT_PARTS[extra]:
                    is_part_of_main = True
                    break
        
        if not is_part_of_main:
            filtered_extra_products.append(extra)
    
    return {
        'has_extra': len(filtered_extra_products) > 0,
        'extra_products': filtered_extra_products,
        'category': category
    }


def calculate_extra_products_penalty(extra_products: list) -> float:
    """Рассчитывает штраф за наличие дополнительных продуктов той же категории
    
    Штрафы:
    - 1 дополнительный продукт: -0.30
    - 2+ дополнительных продукта: -0.45
    
    Args:
        extra_products: Список дополнительных продуктов
        
    Returns:
        Значение штрафа (0.0 - 0.45)
    """
    if not extra_products:
        return 0.0
    
    if len(extra_products) == 1:
        return 0.30
    else:
        return 0.45


# ============ КОНЕЦ v5.6 ============

def calculate_numeric_mismatch_penalty(search_params: dict, found_params: dict) -> tuple[float, str]:
    """Вычисляет штраф за несовпадение числовых параметров
    
    Args:
        search_params: Числовые параметры из поискового запроса
        found_params: Числовые параметры из найденного товара
        
    Returns:
        Кортеж (penalty, reason):
        - penalty: Значение штрафа (0.0 - 0.70)
        - reason: Описание причины штрафа
    """
    total_penalty = 0.0
    reasons = []
    
    # 1. ПРОЦЕНТЫ ЖИРНОСТИ (самый критичный параметр)
    if search_params['percentages'] and found_params['percentages']:
        search_pct = search_params['percentages'][0]  # Берем первый процент
        found_pct = found_params['percentages'][0]
        
        diff = abs(search_pct - found_pct)
        
        if diff == 0:
            # Точное совпадение - нет штрафа
            percentage_penalty = 0.0
        elif diff <= 2:
            # Малое отклонение (18% vs 20%) - легкий штраф
            percentage_penalty = 0.15
            reasons.append(f"percentage diff={diff:.1f}% (minor)")
        elif diff <= 5:
            # Среднее отклонение (15% vs 20%) - КРИТИЧНЫЙ штраф (усилен с 0.35)
            percentage_penalty = 0.50
            reasons.append(f"percentage diff={diff:.1f}% (CRITICAL)")
        else:
            # Большое отклонение (10% vs 20%) - МАКСИМАЛЬНЫЙ штраф (усилен с 0.60)
            percentage_penalty = 0.70
            reasons.append(f"percentage diff={diff:.1f}% (MAXIMUM)")
        
        total_penalty += percentage_penalty
    
    elif search_params['percentages'] and not found_params['percentages']:
        # Процент указан в запросе, но отсутствует в найденном товаре
        # Это может быть вариант без явного указания % (например, базовая версия)
        # Легкий штраф
        total_penalty += 0.10
        reasons.append(f"percentage {search_params['percentages'][0]}% requested but not found")
    
    # 2. ВЕС (менее критичный, но важный)
    if search_params['weights'] and found_params['weights']:
        search_weight = search_params['weights'][0]
        found_weight = found_params['weights'][0]
        
        # Вычисляем соотношение (больший к меньшему)
        ratio = max(search_weight, found_weight) / min(search_weight, found_weight)
        
        if ratio == 1.0:
            weight_penalty = 0.0
        elif ratio <= 1.5:  # 300г vs 400г
            weight_penalty = 0.10
            reasons.append(f"weight ratio={ratio:.2f} (minor)")
        elif ratio <= 2.0:  # 300г vs 600г
            weight_penalty = 0.25
            reasons.append(f"weight ratio={ratio:.2f} (medium)")
        else:  # 300г vs 1000г
            weight_penalty = 0.40
            reasons.append(f"weight ratio={ratio:.2f} (critical)")
        
        total_penalty += weight_penalty
    
    # 3. ОБЪЕМ (аналогично весу)
    if search_params['volumes'] and found_params['volumes']:
        search_volume = search_params['volumes'][0]
        found_volume = found_params['volumes'][0]
        
        ratio = max(search_volume, found_volume) / min(search_volume, found_volume)
        
        if ratio == 1.0:
            volume_penalty = 0.0
        elif ratio <= 1.5:
            volume_penalty = 0.10
            reasons.append(f"volume ratio={ratio:.2f} (minor)")
        elif ratio <= 2.0:
            volume_penalty = 0.25
            reasons.append(f"volume ratio={ratio:.2f} (medium)")
        else:
            volume_penalty = 0.40
            reasons.append(f"volume ratio={ratio:.2f} (critical)")
        
        total_penalty += volume_penalty
    
    # 4. КОЛИЧЕСТВО ШТУК (для яиц, упаковок)
    if search_params['pieces'] and found_params['pieces']:
        search_pieces = search_params['pieces'][0]
        found_pieces = found_params['pieces'][0]
        
        ratio = max(search_pieces, found_pieces) / min(search_pieces, found_pieces)
        
        if ratio == 1.0:
            pieces_penalty = 0.0
        elif ratio <= 1.5:  # 10 vs 12
            pieces_penalty = 0.08
            reasons.append(f"pieces ratio={ratio:.2f} (minor)")
        elif ratio <= 2.0:  # 10 vs 20
            pieces_penalty = 0.20
            reasons.append(f"pieces ratio={ratio:.2f} (medium)")
        else:
            pieces_penalty = 0.35
            reasons.append(f"pieces ratio={ratio:.2f} (critical)")
        
        total_penalty += pieces_penalty
    
    # Ограничиваем максимальный штраф
    total_penalty = min(0.70, total_penalty)
    
    # Формируем итоговое сообщение
    if reasons:
        reason = "; ".join(reasons)
    else:
        reason = "no numeric mismatch"
    
    return total_penalty, reason
