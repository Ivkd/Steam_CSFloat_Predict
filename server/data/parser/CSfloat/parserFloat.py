"""
parserFloat.py — основной оркестратор парсинга CSFloat.

Два режима работы:
1. started()             — обходит /api/v1/listings (общий маркет)
2. check_data_seller()   — обходит stall каждого трейдера, фиксирует listed/not_listed
"""
import os
import aiohttp
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from dotenv import load_dotenv
import asyncpg
import asyncio

from ....core.logger import get_logger, trace_execution, count_calls
from .inserts.primary_insert import *
from .inserts.market_insert import *
from .inserts.stickers import *
from .inserts.traders import (
    upsert_trader_from_listing,
    create_trader_inventory_snapshot,
    insert_trader_inventory_item_snapshot,
    insert_trader_item_action,
    mark_missing_items_as_not_listed,
)
from .inserts.catalog_insert import *
from ...cs2data import *
from .inserts.utilits.types import CursorState, CSFloatGet, CSFloatItem

url_newest_price = "https://csfloat.com/api/v1/listings?limit=40&category=1&sort_by=most_recent"
url_lowest_price = "https://csfloat.com/api/v1/listings?limit=40&category=1&sort_by=lowest_price"
url_csfloat = "https://csfloat.com/api/v1/listings"
url_sellerCSfloat = "https://csfloat.com/api/v1/users"

dotenv_path = os.path.join(os.path.dirname(__file__), "../../../../.env")
load_dotenv(dotenv_path)
CSFLOAT_API_KEY = os.getenv("API_KEY")
logger = get_logger("parserFloat")


class CSFloatBD:
    def __init__(self):
        self.pool = None

    async def __aenter__(self):
        self.pool = await asyncpg.create_pool(
            database=os.getenv("POSTGRES_DB"),
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT"),
            password=os.getenv("POSTGRES_PASSWORD"),
            user=os.getenv("POSTGRES_USER"),
            min_size=5,
            max_size=20,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.pool:
            await self.pool.close()


async def _request(session: aiohttp.ClientSession, url: str, headers: dict, params: dict) -> Optional[Dict]:
    try:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 429:
                await asyncio.sleep(15* 60)
                logger.error(f"HTTP {response.status} для {url}")
                return None
            if response.status != 200:
                logger.error(f"HTTP {response.status} для {url}")
                return None

            data = await response.json()
            if data.get("message") == "You need to be logged in to search listings":
                logger.error("Ошибка авторизации CSFloat API")
                return None
            return data
    except Exception as e:
        logger.error(f"Ошибка запроса {url}: {e}")
        return None


@count_calls
async def get_data_csfloat(url: str, cursor_state: CursorState) -> Optional[Dict[str, Any]]:
    params = {}
    if cursor_state.get():
        params["cursor"] = cursor_state.get()
    headers = {"Authorization": CSFLOAT_API_KEY, "Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        data = await _request(session, url, headers, params)
        if data is None:
            return None
        cursor_state.set(data.get("cursor"))
        return data


async def get_data_stall(seller_id: str) -> Optional[Dict[str, Any]]:
    """Получить stall-страницу продавца (без API ключа)."""
    url = f"{url_sellerCSfloat}/{seller_id}/stall?limit=40"
    headers = {"Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        return await _request(session, url, headers, {})


async def activate_primary_insert(pool):
    try:
        await insert_platform(pool, platform_data)
        await insert_currency(pool, currency_data)
        await insert_quality(pool, item_quality_data)
        await insert_weapon(pool, weapon_data)
        await insert_event_type(pool, event_type_data)
        await insert_containers(pool, container_data)
    except Exception as e:
        logger.error(f"Ошибка при первичной вставке справочников: {e}")


async def get_items(response: Dict[str, Any]) -> list:
    listings = response.get("data", [])
    if listings is None:
        return [CSFloatItem(response)]
    return [CSFloatItem(listing) for listing in listings]


async def insert_data_from_response(pool, response: Dict[str, Any]) -> None:
    try:
        items = await get_items(response)
        for cs_item in items:
            cs_item: CSFloatItem
            item_type = cs_item.item_type
            # logger.info(item_type)

            if item_type == "container":
                await insert_container_item(pool, cs_item)
                continue
            if item_type == "sticker":
                await insert_sticker(pool, cs_item.item_name, cs_item.item_price)
                continue
            if item_type == "agent":
                continue
            if item_type =="charm":
                continue

            if cs_item.stickers:
                for sticker in cs_item.stickers:
                    name = sticker.get("name")
                    price = (sticker.get("reference") or {}).get("price")
                    if name and price is not None:
                        await insert_sticker(pool, name, price)

            if cs_item.skin_name is None:
                continue

            await insert_skin_from_response(pool, cs_item.skin_name)
            game_item_id = await insert_game_item_from_response(pool, cs_item)
            if game_item_id is None:
                logger.warning("Пропуск item_instance и listing: нет game_item_id для %s", cs_item.item_name)
                continue

            await insert_item_instance_from_response(pool, cs_item)

            await upsert_trader_from_listing(pool, cs_item)
            await create_trader_inventory_snapshot(pool, cs_item)
            await insert_trader_inventory_item_snapshot(pool, cs_item)
            await insert_trader_item_action(pool, cs_item)

            await market_listing_insert(pool, cs_item)
            await market_listing_price_history_insert(pool, cs_item)
            await market_listing_status_history_insert(pool, cs_item)
            await market_observation_snapshot_insert(pool, cs_item)

    except Exception as e:
        logger.error(f"Ошибка при вставке данных: {e}")
        raise


async def insert_stall_data(pool, seller_id: str, response: Dict[str, Any]) -> None:
    """
    Обработка stall-ответа:
    1. Вставляем все активные предметы как listed
    2. Помечаем пропавшие предметы как not_listed
    """

    await insert_data_from_response(pool, response)

    items = await get_items(response)
    if not items:
        logger.warning("Пустой items для seller_id=%s", seller_id)
        return

    actual_asset_ids = [item.asset_id for item in items if item.asset_id]
    cs_item = items[0]


    marked = await mark_missing_items_as_not_listed(pool, actual_asset_ids, cs_item)
    # if marked:
    #     logger.info(f"Помечено как not_listed: {marked} предмет(ов) для seller_id={seller_id}")


@trace_execution
async def started():
    """Обход общего маркета /api/v1/listings."""
    try:
        floatdb = CSFloatBD()
        cursor = CursorState()
        logger.info(f"Парсер запущен: {datetime.now(timezone.utc).isoformat()}")

        data = await get_data_csfloat(url_newest_price, cursor)

        async with floatdb as db:
            csfloatget = CSFloatGet(db.pool)
            skins = await csfloatget.get_skins()
            if not skins:
                await activate_primary_insert(db.pool)

            while data and cursor.get():
                await insert_data_from_response(db.pool, data)
                data = await get_data_csfloat(url_newest_price, cursor)
                if not cursor.get():
                    logger.info("Курсор пуст, завершение парсинга.")
                    break
                await asyncio.sleep(50)
    except Exception as e:
        logger.error(f"Ошибка в started(): {e}")
        raise


@trace_execution
async def check_data_seller():
    """
    Обход stall всех известных трейдеров:
    - фиксирует listed для активных предметов
    - фиксирует not_listed для пропавших
    """
    try:
        floatdb = CSFloatBD()
        async with floatdb as db:
            csfloatget = CSFloatGet(db.pool)
            seller_ids = await csfloatget.get_seller_ids()

            for row in seller_ids:
                seller_id = row["platform_user_id"]
                response = await get_data_stall(seller_id)
                if response is None:
                    logger.warning(f"Нет ответа для seller_id={seller_id}")
                    continue
                await insert_stall_data(db.pool, seller_id, response)
    except Exception as e:
        logger.error(f"Ошибка в check_data_seller(): {e}")
        raise
