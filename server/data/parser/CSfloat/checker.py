import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

import aiohttp
import asyncpg
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from ....core.logger import get_logger
from .inserts.utilits.types import CSFloatItem
from .parserFloat import insert_data_from_response

logger = get_logger("checker")

dotenv_path = os.path.join(os.path.dirname(__file__), "../../../../.env")
load_dotenv(dotenv_path)

CSFLOAT_API_KEY = os.getenv("API_KEY")
CSFLOAT_SIMILAR_URL = "https://csfloat.com/api/v1/listings"
CSFLOAT_ITEM_URL    = "https://csfloat.com/item"

DELAY_BETWEEN = 0  # секунды между запросами

# ─────────────────────────────────────────────
# Вспомогательные функции для URL
# ─────────────────────────────────────────────

def build_similar_url(cs_item_id: int) -> str:
    return f"{CSFLOAT_SIMILAR_URL}/{cs_item_id}/similar"


def build_item_url(cs_item_id: str) -> str:
    return f"{CSFLOAT_ITEM_URL}/{cs_item_id}"


# ─────────────────────────────────────────────
# aiohttp: получить similar-листинги
# ─────────────────────────────────────────────

async def fetch_similar(session: aiohttp.ClientSession, cs_item_id: asyncpg.Record) -> Optional[dict]:

    id = cs_item_id["external_listing_id"]
    url = build_similar_url(id)

    for attempt in range(3):
        
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 404:
                    logger.warning(f"similar: 404 для url={url}, попытка {attempt + 1}")
                    await asyncio.to_thread(touch_item_with_selenium, cs_item_id)
                    continue
                if resp.status == 429:
                    logger.warning(f"Rate limit на {url} попытка {attempt + 1}")
                    await asyncio.sleep(60)
                    continue
                if resp.status != 200:
                    logger.error(f"HTTP {resp.status} для cs_item_id={cs_item_id}")
                    return None

                data = await resp.json(content_type=None)
                if not data:
                    logger.warning(f"similar: пустой JSON для url={url}")
                    return None
                return data
        except asyncio.TimeoutError:
            logger.warning(f"Timeout для cs_item_id={cs_item_id}, попытка {attempt + 1}")
        except Exception as e:
            logger.error(f"Ошибка aiohttp cs_item_id={cs_item_id}: {e}")
            return None

    return None


# ─────────────────────────────────────────────
# Selenium: симулируем визит пользователя
# ─────────────────────────────────────────────

def touch_item_with_selenium(cs_item_id: str) -> None:
    url = build_item_url(cs_item_id)

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.binary_location = "/usr/bin/chromium"

    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.get(url)
    finally:
        driver.quit()


# ─────────────────────────────────────────────
# Основная логика: aiohttp → fallback Selenium → повтор
# ─────────────────────────────────────────────

async def insert_similar_reregister_listings(conn, pool, session: aiohttp.ClientSession, row: asyncpg.Record):
    data = await fetch_similar(session, row)
    if data is None:
        return

    new_data = {}

    new_data["data"] = [d for d in data]

    await insert_data_from_response(pool, new_data)
    await process_listing(conn, row, new_data)


# ─────────────────────────────────────────────
# Обработка одного листинга
# ─────────────────────────────────────────────

async def process_listing(conn, row: asyncpg.Record, data: dict) -> None:
    listing_id = row["market_listing_id"]
    cs_item_id = row["external_listing_id"]
    old_status = row["current_status"]
    seller_id = row["trader_platform_account_id"]
    item_instance_id = row["item_instance_id"]
    currency_id = row["currency_id"]
    old_price = row["listed_price"]
    now = datetime.now(timezone.utc)

    await asyncio.sleep(DELAY_BETWEEN)

    if data is None:
        logger.info(f"Нет данных даже после Selenium, помечаем not_listed cs_item_id={cs_item_id}")
        await _mark_not_listed(conn, listing_id, seller_id, item_instance_id,
                               old_price, currency_id, old_status, now)
        return

    listings = data.get("data")

    for listing in listings:
        new_state = listing.get("state", "")
        new_price = listing.get("price", old_price)

        if new_state == "listed":
            await conn.execute(
                """
                UPDATE market_listing
                SET last_seen_at = $1,
                    listed_price = $2
                WHERE market_listing_id = $3
                """,
                now, new_price, listing_id
            )
            if new_price != old_price:
                await conn.execute(
                    """
                    INSERT INTO market_listing_price_history
                        (market_listing_id, observed_at, price_amount, currency_id)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (market_listing_id, observed_at) DO NOTHING
                    """,
                    listing_id, now, new_price, currency_id
                )

        # elif new_state == "sold":
        #     sold_at = data.get("sold_at", now.isoformat())
        #     if isinstance(sold_at, str):
        #         try:
        #             sold_at = datetime.fromisoformat(sold_at.replace("Z", "+00:00"))
        #         except Exception:
        #             sold_at = now

        #     await _mark_sold(conn, listing_id, seller_id, item_instance_id,
        #                     new_price, currency_id, old_status, sold_at)
        #     # logger.info(f"[sold] cs_item_id={cs_item_id} sold_at={sold_at}")

        else:
            await _mark_not_listed(conn, listing_id, seller_id, item_instance_id,
                                new_price, currency_id, old_status, now)
            # logger.info(f"[not_listed] cs_item_id={cs_item_id} state={new_state}")


# ─────────────────────────────────────────────
# Пометить как sold
# ─────────────────────────────────────────────

async def _mark_sold(conn, listing_id, seller_id, item_instance_id,
                     price, currency_id, old_status, action_time):
    await conn.execute(
        """
        UPDATE market_listing
        SET current_status = 'sold',
            last_seen_at   = $1
        WHERE market_listing_id = $2
        """,
        action_time, listing_id
    )

    event_type_id = await conn.fetchval(
        "SELECT event_type_id FROM event_type WHERE code = $1", "sold"
    )
    if event_type_id:
        await conn.execute(
            """
            INSERT INTO market_listing_status_history
                (market_listing_id, event_type_id, event_time, old_status, new_status)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (market_listing_id, event_time, event_type_id) DO NOTHING
            """,
            listing_id, event_type_id, action_time, old_status, "sold"
        )

    if seller_id and event_type_id:
        await conn.execute(
            """
            INSERT INTO trader_item_action
                (trader_platform_account_id, item_instance_id, event_type_id,
                 action_time, price_amount, currency_id, confidence_score)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            seller_id, item_instance_id, event_type_id,
            action_time, price, currency_id,
            0.95
        )


# ─────────────────────────────────────────────
# Пометить как not_listed
# ─────────────────────────────────────────────

async def _mark_not_listed(conn, listing_id, seller_id, item_instance_id,
                           price, currency_id, old_status, action_time):
    await conn.execute(
        """
        UPDATE market_listing
        SET current_status = 'not_listed',
            last_seen_at   = $1
        WHERE market_listing_id = $2
        """,
        action_time, listing_id
    )

    event_type_id = await conn.fetchval(
        "SELECT event_type_id FROM event_type WHERE code = $1", "not_listed"
    )
    if event_type_id:
        await conn.execute(
            """
            INSERT INTO market_listing_status_history
                (market_listing_id, event_type_id, event_time, old_status, new_status)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (market_listing_id, event_time, event_type_id) DO NOTHING
            """,
            listing_id, event_type_id, action_time, old_status, "not_listed"
        )

    if seller_id and event_type_id:
        await conn.execute(
            """
            INSERT INTO trader_item_action
                (trader_platform_account_id, item_instance_id, event_type_id,
                 action_time, price_amount, currency_id, confidence_score)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            seller_id, item_instance_id, event_type_id,
            action_time, price, currency_id,
            0.75
        )


# ─────────────────────────────────────────────
# Главная точка входа
# ─────────────────────────────────────────────

async def run_listing_checker(pool) -> None:
    async with pool.acquire() as conn:
         rows = await conn.fetch(
            """
            SELECT
                ml.market_listing_id,
                ml.external_listing_id,
                ml.current_status,
                ml.seller_account_id AS trader_platform_account_id,
                ml.item_instance_id,
                ml.currency_id,
                ml.listed_price
            FROM market_listing ml
            WHERE ml.current_status = 'listed'
            ORDER BY ml.first_seen_at ASC
            """
        )

    if not rows:
        logger.info("Нет активных листингов для проверки.")
        return

    logger.info(f"Проверяем {len(rows)} активных листингов...")

    async with aiohttp.ClientSession() as session:
        async with pool.acquire() as conn:
            for row in rows:
                await insert_similar_reregister_listings(conn, pool, session, row)
            
    logger.info("Проверка листингов завершена.")