#!/usr/bin/env python3
"""
Скрипт для перевода названий продуктов USDA на русский язык.
Использует OpenAI API для пакетного перевода.
"""
import asyncio
import json
import os
import sys
from typing import List, Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from openai import AsyncOpenAI
from config.settings import settings

INPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'products_usda.json')
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'products_usda_ru.json')
CACHE_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'translations_cache.json')

BATCH_SIZE = 50  # Количество названий в одном запросе


async def translate_batch(client: AsyncOpenAI, names: List[str]) -> List[str]:
    """Перевод пакета названий продуктов"""
    names_text = "\n".join([f"{i+1}. {name}" for i, name in enumerate(names)])

    prompt = f"""Переведи названия продуктов питания с английского на русский язык.
Сохраняй формат нумерации. Переводи кратко и естественно для русского языка.
Убирай лишние детали типа "raw", "cooked" - оставляй только если важно.
Примеры:
- "Milk, whole, 3.25% milkfat" -> "Молоко цельное 3.25%"
- "Chicken, broilers or fryers, breast, meat only, raw" -> "Куриная грудка"
- "Beef, ground, 80% lean meat / 20% fat, raw" -> "Говяжий фарш 80/20"

Названия для перевода:
{names_text}

Ответь ТОЛЬКО переводами в том же формате (номер. перевод), без пояснений."""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4000
        )

        result_text = response.choices[0].message.content.strip()

        # Парсим ответ
        translations = []
        for line in result_text.split('\n'):
            line = line.strip()
            if line and '.' in line:
                # Извлекаем текст после номера
                parts = line.split('.', 1)
                if len(parts) == 2:
                    translations.append(parts[1].strip())

        # Если не все переведены, дополняем оригиналами
        while len(translations) < len(names):
            translations.append(names[len(translations)])

        return translations[:len(names)]

    except Exception as e:
        print(f"Ошибка перевода: {e}")
        return names  # Возвращаем оригиналы при ошибке


async def translate_all_products():
    """Перевод всех продуктов"""
    print("=" * 60)
    print("Перевод названий продуктов USDA на русский")
    print("=" * 60)

    # Загружаем продукты
    print("\n1. Загрузка продуктов...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    products = data['products']
    print(f"   Загружено {len(products)} продуктов")

    # Загружаем кэш переводов
    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        print(f"   Загружен кэш: {len(cache)} переводов")

    # Собираем названия для перевода
    to_translate = []
    for p in products:
        name_en = p['name_en']
        if name_en not in cache:
            to_translate.append(name_en)

    print(f"\n2. Нужно перевести: {len(to_translate)} названий")

    if to_translate:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        # Разбиваем на батчи
        batches = [to_translate[i:i+BATCH_SIZE] for i in range(0, len(to_translate), BATCH_SIZE)]
        print(f"   Батчей: {len(batches)}")

        translated_count = 0
        for i, batch in enumerate(batches):
            print(f"\n   Батч {i+1}/{len(batches)} ({len(batch)} названий)...", end=" ", flush=True)

            translations = await translate_batch(client, batch)

            for name_en, name_ru in zip(batch, translations):
                cache[name_en] = name_ru
                translated_count += 1

            print(f"✓")

            # Сохраняем кэш каждые 10 батчей
            if (i + 1) % 10 == 0:
                with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2)
                print(f"   [Кэш сохранён: {len(cache)} переводов]")

            # Небольшая задержка между запросами
            await asyncio.sleep(0.5)

        # Финальное сохранение кэша
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Переведено: {translated_count} названий")

    # Применяем переводы к продуктам
    print("\n3. Применение переводов...")
    for p in products:
        name_en = p['name_en']
        p['name'] = cache.get(name_en, name_en)

    # Переводим категории
    for cat in data['categories']:
        # Категории уже переведены в convert_usda_to_json.py
        pass

    # Сохраняем результат
    print(f"\n4. Сохранение в {OUTPUT_FILE}...")
    data['source'] = 'USDA FoodData Central SR Legacy 2018-04 (перевод на русский)'
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Готово!")
    print(f"   Файл: {OUTPUT_FILE}")
    print(f"   Размер: {os.path.getsize(OUTPUT_FILE) / 1024 / 1024:.1f} MB")

    # Показываем примеры
    print("\nПримеры переводов:")
    for p in products[:10]:
        print(f"  {p['name_en'][:50]:50s} -> {p['name']}")


if __name__ == "__main__":
    asyncio.run(translate_all_products())
