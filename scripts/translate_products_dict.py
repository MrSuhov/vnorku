#!/usr/bin/env python3
"""
Скрипт для перевода названий продуктов USDA на русский язык.
Использует локальный словарь базовых продуктовых терминов.
Запуск: python scripts/translate_products_dict.py
"""
import json
import os
import re

INPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'products_usda.json')
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'products_usda_ru.json')

# Словарь перевода базовых продуктовых терминов EN -> RU
FOOD_DICTIONARY = {
    # Мясо
    "beef": "говядина",
    "pork": "свинина",
    "lamb": "баранина",
    "veal": "телятина",
    "chicken": "курица",
    "turkey": "индейка",
    "duck": "утка",
    "goose": "гусь",
    "meat": "мясо",
    "steak": "стейк",
    "roast": "жаркое",
    "ground": "фарш",
    "minced": "рубленый",
    "cutlet": "котлета",
    "fillet": "филе",
    "breast": "грудка",
    "thigh": "бедро",
    "leg": "ножка",
    "wing": "крылышко",
    "liver": "печень",
    "kidney": "почка",
    "heart": "сердце",
    "tongue": "язык",
    "bacon": "бекон",
    "ham": "ветчина",
    "sausage": "колбаса",
    "salami": "салями",
    "bologna": "болонья",
    "hot dog": "сосиска",
    "frankfurter": "сосиска",
    "wiener": "сосиска",

    # Рыба и морепродукты
    "fish": "рыба",
    "salmon": "лосось",
    "tuna": "тунец",
    "cod": "треска",
    "trout": "форель",
    "herring": "сельдь",
    "mackerel": "скумбрия",
    "sardine": "сардина",
    "anchovy": "анчоус",
    "carp": "карп",
    "bass": "окунь",
    "perch": "окунь",
    "pike": "щука",
    "catfish": "сом",
    "tilapia": "тилапия",
    "haddock": "пикша",
    "halibut": "палтус",
    "flounder": "камбала",
    "sole": "морской язык",
    "shrimp": "креветка",
    "prawn": "креветка",
    "lobster": "омар",
    "crab": "краб",
    "oyster": "устрица",
    "mussel": "мидия",
    "clam": "моллюск",
    "scallop": "гребешок",
    "squid": "кальмар",
    "octopus": "осьминог",
    "caviar": "икра",
    "seafood": "морепродукты",

    # Молочные продукты
    "milk": "молоко",
    "cream": "сливки",
    "butter": "масло сливочное",
    "cheese": "сыр",
    "cheddar": "чеддер",
    "mozzarella": "моцарелла",
    "parmesan": "пармезан",
    "feta": "фета",
    "brie": "бри",
    "camembert": "камамбер",
    "cottage cheese": "творог",
    "ricotta": "рикотта",
    "yogurt": "йогурт",
    "kefir": "кефир",
    "sour cream": "сметана",
    "whey": "сыворотка",
    "ice cream": "мороженое",

    # Яйца
    "egg": "яйцо",
    "eggs": "яйца",
    "yolk": "желток",
    "white": "белок",
    "omelet": "омлет",
    "omelette": "омлет",

    # Овощи
    "vegetable": "овощ",
    "vegetables": "овощи",
    "potato": "картофель",
    "potatoes": "картофель",
    "tomato": "помидор",
    "tomatoes": "помидоры",
    "cucumber": "огурец",
    "carrot": "морковь",
    "onion": "лук",
    "garlic": "чеснок",
    "pepper": "перец",
    "bell pepper": "болгарский перец",
    "cabbage": "капуста",
    "broccoli": "брокколи",
    "cauliflower": "цветная капуста",
    "spinach": "шпинат",
    "lettuce": "салат",
    "celery": "сельдерей",
    "corn": "кукуруза",
    "peas": "горох",
    "bean": "фасоль",
    "beans": "фасоль",
    "lentil": "чечевица",
    "lentils": "чечевица",
    "chickpea": "нут",
    "chickpeas": "нут",
    "soybean": "соя",
    "eggplant": "баклажан",
    "zucchini": "кабачок",
    "squash": "тыква",
    "pumpkin": "тыква",
    "beet": "свекла",
    "radish": "редис",
    "turnip": "репа",
    "asparagus": "спаржа",
    "artichoke": "артишок",
    "mushroom": "гриб",
    "mushrooms": "грибы",
    "olive": "оливка",
    "olives": "оливки",
    "pickle": "соленье",
    "sauerkraut": "квашеная капуста",

    # Фрукты и ягоды
    "fruit": "фрукт",
    "fruits": "фрукты",
    "apple": "яблоко",
    "pear": "груша",
    "plum": "слива",
    "peach": "персик",
    "apricot": "абрикос",
    "cherry": "вишня",
    "grape": "виноград",
    "grapes": "виноград",
    "banana": "банан",
    "orange": "апельсин",
    "lemon": "лимон",
    "lime": "лайм",
    "grapefruit": "грейпфрут",
    "tangerine": "мандарин",
    "mandarin": "мандарин",
    "pomegranate": "гранат",
    "mango": "манго",
    "papaya": "папайя",
    "pineapple": "ананас",
    "coconut": "кокос",
    "kiwi": "киви",
    "watermelon": "арбуз",
    "melon": "дыня",
    "cantaloupe": "канталупа",
    "berry": "ягода",
    "berries": "ягоды",
    "strawberry": "клубника",
    "raspberry": "малина",
    "blueberry": "черника",
    "blackberry": "ежевика",
    "cranberry": "клюква",
    "currant": "смородина",
    "gooseberry": "крыжовник",
    "fig": "инжир",
    "date": "финик",
    "prune": "чернослив",
    "raisin": "изюм",
    "raisins": "изюм",
    "dried": "сушёный",

    # Орехи и семена
    "nut": "орех",
    "nuts": "орехи",
    "walnut": "грецкий орех",
    "almond": "миндаль",
    "almonds": "миндаль",
    "cashew": "кешью",
    "peanut": "арахис",
    "peanuts": "арахис",
    "hazelnut": "фундук",
    "pistachio": "фисташка",
    "pecan": "пекан",
    "chestnut": "каштан",
    "seed": "семя",
    "seeds": "семена",
    "sunflower": "подсолнечник",
    "sesame": "кунжут",
    "flax": "лён",
    "chia": "чиа",
    "pumpkin seeds": "тыквенные семечки",

    # Зерновые и крупы
    "grain": "зерно",
    "grains": "злаки",
    "wheat": "пшеница",
    "rice": "рис",
    "oat": "овёс",
    "oats": "овёс",
    "oatmeal": "овсянка",
    "barley": "ячмень",
    "rye": "рожь",
    "buckwheat": "гречка",
    "millet": "пшено",
    "quinoa": "киноа",
    "cereal": "хлопья",
    "flour": "мука",
    "bran": "отруби",
    "semolina": "манка",

    # Хлеб и выпечка
    "bread": "хлеб",
    "loaf": "буханка",
    "toast": "тост",
    "roll": "булочка",
    "bun": "булочка",
    "bagel": "бейгл",
    "croissant": "круассан",
    "muffin": "маффин",
    "biscuit": "бисквит",
    "cookie": "печенье",
    "cookies": "печенье",
    "cracker": "крекер",
    "crackers": "крекеры",
    "cake": "торт",
    "pie": "пирог",
    "tart": "тарт",
    "pastry": "выпечка",
    "donut": "пончик",
    "doughnut": "пончик",
    "pancake": "блин",
    "waffle": "вафля",
    "waffles": "вафли",
    "pretzel": "крендель",

    # Макаронные изделия
    "pasta": "паста",
    "noodle": "лапша",
    "noodles": "лапша",
    "spaghetti": "спагетти",
    "macaroni": "макароны",
    "lasagna": "лазанья",
    "ravioli": "равиоли",

    # Сладости
    "sugar": "сахар",
    "honey": "мёд",
    "syrup": "сироп",
    "maple": "кленовый",
    "molasses": "патока",
    "chocolate": "шоколад",
    "candy": "конфета",
    "candies": "конфеты",
    "caramel": "карамель",
    "marshmallow": "зефир",
    "jelly": "желе",
    "jam": "джем",
    "marmalade": "мармелад",
    "pudding": "пудинг",
    "custard": "заварной крем",

    # Напитки
    "water": "вода",
    "juice": "сок",
    "tea": "чай",
    "coffee": "кофе",
    "cocoa": "какао",
    "soda": "газировка",
    "cola": "кола",
    "lemonade": "лимонад",
    "smoothie": "смузи",
    "shake": "коктейль",
    "milkshake": "молочный коктейль",
    "wine": "вино",
    "beer": "пиво",
    "vodka": "водка",
    "whiskey": "виски",
    "brandy": "бренди",
    "rum": "ром",
    "gin": "джин",
    "liqueur": "ликёр",
    "cider": "сидр",

    # Масла и жиры
    "oil": "масло",
    "olive oil": "оливковое масло",
    "vegetable oil": "растительное масло",
    "sunflower oil": "подсолнечное масло",
    "coconut oil": "кокосовое масло",
    "fat": "жир",
    "lard": "сало",
    "margarine": "маргарин",

    # Соусы и приправы
    "sauce": "соус",
    "ketchup": "кетчуп",
    "mayonnaise": "майонез",
    "mustard": "горчица",
    "vinegar": "уксус",
    "salt": "соль",
    "pepper": "перец",
    "spice": "специя",
    "spices": "специи",
    "herb": "трава",
    "herbs": "травы",
    "basil": "базилик",
    "oregano": "орегано",
    "thyme": "тимьян",
    "rosemary": "розмарин",
    "parsley": "петрушка",
    "dill": "укроп",
    "cilantro": "кинза",
    "mint": "мята",
    "cinnamon": "корица",
    "ginger": "имбирь",
    "nutmeg": "мускатный орех",
    "clove": "гвоздика",
    "cumin": "кумин",
    "curry": "карри",
    "paprika": "паприка",
    "chili": "чили",
    "vanilla": "ваниль",
    "bay leaf": "лавровый лист",

    # Способы приготовления
    "raw": "сырой",
    "fresh": "свежий",
    "frozen": "замороженный",
    "canned": "консервированный",
    "cooked": "приготовленный",
    "boiled": "варёный",
    "fried": "жареный",
    "baked": "запечённый",
    "roasted": "жареный",
    "grilled": "гриль",
    "steamed": "на пару",
    "smoked": "копчёный",
    "pickled": "маринованный",
    "salted": "солёный",
    "dried": "сушёный",
    "sliced": "нарезанный",
    "diced": "кубиками",
    "chopped": "рубленый",
    "mashed": "пюре",
    "stuffed": "фаршированный",
    "breaded": "в панировке",
    "marinated": "маринованный",

    # Характеристики
    "whole": "цельный",
    "lean": "постный",
    "fat-free": "обезжиренный",
    "low-fat": "низкожирный",
    "skim": "обезжиренный",
    "reduced": "с пониженным",
    "light": "лёгкий",
    "organic": "органический",
    "natural": "натуральный",
    "enriched": "обогащённый",
    "fortified": "витаминизированный",
    "plain": "простой",
    "flavored": "ароматизированный",
    "sweetened": "подслащённый",
    "unsweetened": "без сахара",
    "with": "с",
    "without": "без",
    "and": "и",

    # Детское питание
    "baby": "детское",
    "infant": "младенческое",
    "toddler": "для малышей",
    "formula": "смесь",
    "puree": "пюре",

    # Прочее
    "soup": "суп",
    "broth": "бульон",
    "stock": "бульон",
    "stew": "рагу",
    "salad": "салат",
    "sandwich": "сэндвич",
    "pizza": "пицца",
    "burger": "бургер",
    "hot dog": "хот-дог",
    "taco": "тако",
    "burrito": "буррито",
    "wrap": "ролл",
    "snack": "закуска",
    "appetizer": "закуска",
    "dessert": "десерт",
    "meal": "блюдо",
    "dish": "блюдо",
    "serving": "порция",
    "portion": "порция",

    # Бренды и типы (оставляем как есть)
    "pillsbury": "Pillsbury",
    "kraft": "Kraft",
    "general mills": "General Mills",
    "nestle": "Nestle",
    "kellogg": "Kellogg's",
}


def translate_name(name_en: str) -> str:
    """Перевод названия продукта используя словарь"""
    # Приводим к нижнему регистру для поиска
    name_lower = name_en.lower()
    result = name_en

    # Сортируем словарь по длине ключа (сначала длинные фразы)
    sorted_dict = sorted(FOOD_DICTIONARY.items(), key=lambda x: len(x[0]), reverse=True)

    for en_term, ru_term in sorted_dict:
        # Ищем термин как отдельное слово
        pattern = r'\b' + re.escape(en_term) + r'\b'
        if re.search(pattern, name_lower, re.IGNORECASE):
            # Заменяем в результате
            result = re.sub(pattern, ru_term, result, flags=re.IGNORECASE)
            name_lower = re.sub(pattern, ru_term, name_lower, flags=re.IGNORECASE)

    return result


def translate_products():
    """Перевод названий продуктов"""
    print("=" * 60)
    print("Перевод названий продуктов USDA на русский")
    print("(через локальный словарь терминов)")
    print("=" * 60)

    # Загружаем данные
    print("\n1. Загрузка продуктов...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    products = data['products']
    print(f"   Загружено {len(products)} продуктов")
    print(f"   Словарь содержит {len(FOOD_DICTIONARY)} терминов")

    # Переводим
    print("\n2. Перевод названий...")
    translated_count = 0
    partially_translated = 0

    for i, product in enumerate(products):
        name_en = product['name_en']
        name_ru = translate_name(name_en)
        product['name'] = name_ru

        # Считаем статистику
        if name_ru != name_en:
            if name_ru.lower() != name_en.lower():  # Реальный перевод
                translated_count += 1
                # Проверяем, остались ли английские слова
                has_english = any(c.isalpha() and ord(c) < 128 for c in name_ru)
                if has_english:
                    partially_translated += 1

        # Прогресс каждые 1000
        if (i + 1) % 1000 == 0:
            print(f"   Обработано: {i + 1}/{len(products)}")

    print(f"\n   Полностью/частично переведено: {translated_count}")
    print(f"   Частично переведённых: {partially_translated}")

    # Сохраняем результат
    print("\n3. Сохранение результата...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    file_size = os.path.getsize(OUTPUT_FILE) / 1024 / 1024
    print(f"   Сохранено в {OUTPUT_FILE}")
    print(f"   Размер файла: {file_size:.1f} MB")

    # Примеры переводов
    print("\n" + "=" * 60)
    print("ПРИМЕРЫ ПЕРЕВОДОВ")
    print("=" * 60)

    # Показать примеры где произошёл перевод
    examples = []
    for p in products:
        if p.get('name') != p.get('name_en'):
            examples.append(p)
        if len(examples) >= 20:
            break

    for p in examples:
        en = p.get('name_en', '')[:40]
        ru = p.get('name', '')[:40]
        print(f"   {en:<42} → {ru}")

    print("\n✅ Перевод завершён!")


if __name__ == "__main__":
    translate_products()
