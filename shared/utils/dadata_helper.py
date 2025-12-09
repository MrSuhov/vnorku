"""
DaData API Helper для подсказок адресов
"""
import httpx
import logging
from typing import List, Dict, Optional
from config.settings import settings

logger = logging.getLogger(__name__)


class DaDataHelper:
    """Помощник для работы с DaData API"""

    API_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"

    # Типы улиц для удаления из адреса (в порядке убывания длины для корректной замены)
    STREET_TYPES = [
        "проспект",
        "бульвар",
        "площадь",
        "переулок",
        "шоссе",
        "тупик",
        "набережная",
        "аллея",
        "микрорайон",
        "просп",
        "пр-кт",
        "пр-т",
        "ул",
        "б-р",
        "пл",
        "пер",
        "ш",
        "туп",
        "наб",
        "мкр",
        "д",
        "к",
        "стр",
        "влд",
    ]

    @classmethod
    def _normalize_street_name(cls, street_with_type: str, street_name: str) -> str:
        """
        Нормализует название улицы, убирая тип (пр-кт, ул., просп и т.д.)

        Args:
            street_with_type: Название с типом, например "Нахимовский пр-кт"
            street_name: Чистое название улицы, например "Нахимовский"

        Returns:
            Нормализованное название без типа
        """
        # Если есть чистое название без типа - используем его
        if street_name:
            return street_name

        # Иначе пытаемся убрать тип из street_with_type
        result = street_with_type.strip()

        # Убираем все типы улиц (регистронезависимо)
        for street_type in cls.STREET_TYPES:
            # Убираем с конца строки
            if result.lower().endswith(f" {street_type}"):
                result = result[:-(len(street_type) + 1)].strip()
                break
            # Убираем с начала строки
            if result.lower().startswith(f"{street_type} "):
                result = result[len(street_type) + 1:].strip()
                break

        return result

    @classmethod
    async def get_address_suggestions(cls, query: str, count: int = 5) -> List[Dict]:
        """
        Получить подсказки адресов от DaData

        Args:
            query: Текст запроса (адрес с квартирой)
            count: Количество подсказок (по умолчанию 5)

        Returns:
            Список словарей с данными адресов:
            [
                {
                    "value": "117335, Москва, Нахимовский просп, д 63 к 1, кв 29",
                    "unrestricted_value": "117335, г Москва, Нахимовский пр-кт, д 63 к 1, кв 29",
                    "address": "117335, Москва, Нахимовский просп, д 63 к 1",
                    "apartment": "29",
                    "postal_code": "117335",
                    "region": "Москва",
                    "city": "Москва",
                    "street": "Нахимовский просп",
                    "house": "63",
                    "block": "1",
                    "flat": "29",
                    "geo_lat": "55.123456",
                    "geo_lon": "37.654321"
                },
                ...
            ]
        """
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Token {settings.dadata_api_key}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "query": query,
                    "count": count
                }

                logger.info(f"🔍 DaData request: query='{query}', count={count}")

                response = await client.post(
                    cls.API_URL,
                    json=payload,
                    headers=headers,
                    timeout=10.0
                )

                if response.status_code != 200:
                    logger.error(f"❌ DaData API error: {response.status_code} {response.text}")
                    return []

                data = response.json()
                suggestions = data.get("suggestions", [])

                logger.info(f"✅ DaData returned {len(suggestions)} suggestions")

                # Парсим результаты
                result = []
                for suggestion in suggestions:
                    value = suggestion.get("value", "")
                    unrestricted_value = suggestion.get("unrestricted_value", "")
                    data_obj = suggestion.get("data", {})

                    # Извлекаем компоненты адреса
                    postal_code = data_obj.get("postal_code", "")
                    region = data_obj.get("region_with_type", "")
                    city = data_obj.get("city", "") or data_obj.get("settlement", "")
                    street_with_type = data_obj.get("street_with_type", "")
                    street_name = data_obj.get("street", "")  # Название улицы БЕЗ типа
                    house = data_obj.get("house", "")
                    block = data_obj.get("block", "")
                    flat = data_obj.get("flat", "")

                    # Координаты
                    geo_lat = data_obj.get("geo_lat", "")
                    geo_lon = data_obj.get("geo_lon", "")

                    # Нормализуем название улицы (убираем типы: пр-кт, ул., просп и т.д.)
                    street_normalized = cls._normalize_street_name(street_with_type, street_name)

                    # Формируем адрес без квартиры (с индексом) в компактном формате
                    address_parts = []
                    if postal_code:
                        address_parts.append(postal_code)
                    if city:
                        address_parts.append(city)
                    if street_normalized:
                        address_parts.append(street_normalized)
                    if house:
                        # Компактный формат: "63к1" вместо "д 63 к 1"
                        if "-" in house and not block:
                            # Дом с корпусом через дефис: "63-1" -> "63к1"
                            house_parts = house.split("-")
                            house_str = f"{house_parts[0]}к{house_parts[1]}"
                        else:
                            house_str = house
                            if block:
                                house_str += f"к{block}"
                        address_parts.append(house_str)

                    address_without_flat = ", ".join(address_parts)

                    result.append({
                        "value": value,  # Полный адрес с квартирой (оригинальный от DaData)
                        "unrestricted_value": unrestricted_value,
                        "address": address_without_flat,  # Нормализованный адрес без квартиры
                        "apartment": flat,  # Номер квартиры
                        "postal_code": postal_code,
                        "region": region,
                        "city": city,
                        "street": street_normalized,  # Нормализованное название улицы БЕЗ типа
                        "house": house,
                        "block": block,
                        "flat": flat,
                        "geo_lat": geo_lat,
                        "geo_lon": geo_lon
                    })

                return result

        except httpx.TimeoutException:
            logger.error("❌ DaData API timeout")
            return []
        except Exception as e:
            logger.error(f"❌ DaData API error: {e}")
            return []

    @classmethod
    def format_suggestion_for_button(cls, suggestion: Dict) -> str:
        """
        Форматировать подсказку для отображения в inline кнопке

        Args:
            suggestion: Словарь с данными адреса

        Returns:
            Строка для отображения в кнопке (макс 64 символа)
        """
        value = suggestion.get("value", "")

        # Telegram inline button text ограничен 64 символами
        if len(value) > 60:
            # Пробуем сократить: оставляем город, улицу, дом, квартиру
            city = suggestion.get("city", "")
            street = suggestion.get("street", "")
            house = suggestion.get("house", "")
            block = suggestion.get("block", "")
            flat = suggestion.get("flat", "")

            short_parts = []
            if city:
                short_parts.append(city)
            if street:
                short_parts.append(street)
            if house:
                house_str = f"д{house}"
                if block:
                    house_str += f"к{block}"
                short_parts.append(house_str)
            if flat:
                short_parts.append(f"кв{flat}")

            value = ", ".join(short_parts)

            # Если всё ещё длинно - обрезаем
            if len(value) > 60:
                value = value[:57] + "..."

        return value
