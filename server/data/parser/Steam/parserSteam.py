"""
parserSteam.py — обновление цен Steam по pricehistory + снапшоты инвентарей.
Трейдеры берутся из уже существующих CSFloat аккаунтов (те же люди).
"""
import asyncio
import os
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

import aiohttp
import asyncpg
from dotenv import load_dotenv

from ....core.logger import get_logger
from ..CSfloat.inserts.steam_market import fetch_and_store_price_history

load_dotenv()
logger = get_logger("parserSteam")


def _get_cookies() -> dict:
    return {
        "steamLoginSecure": os.getenv("STEAM_LOGIN_SECURE", ""),
        "sessionid":        os.getenv("STEAM_SESSION_ID", ""),
        "steamCountry":     os.getenv("STEAM_COUNTRY", ""),
        "Steam_Language":   "english",
        "steamCurrencyId":  "1",
        "timezoneOffset":   "10800,0",
    }

_STEAM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":           "application/json, text/javascript, */*; q=0.01",
    "Accept-Language":  "en-US,en;q=0.9",
    "Referer":          "https://steamcommunity.com/market/",
    "X-Requested-With": "XMLHttpRequest",
}

# ─── Получение данных из БД ───────────────────────────────────────────────────


async def _get_game_items(pool: asyncpg.Pool) -> list:
    """Уникальные game_item из CSFloat листингов для запроса цен."""
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT DISTINCT
                gi.game_item_id,
                gi.is_stattrak,
                gi.is_souvenir,
                w.name  AS weapon_name,
                s.name  AS skin_name,
                iq.name AS quality_name
            FROM market_listing ml
            JOIN item_instance ii  ON ii.item_instance_id = ml.item_instance_id
            JOIN game_item gi      ON gi.game_item_id = ii.game_item_id
            JOIN weapon w          USING (weapon_id)
            JOIN skin s            USING (skin_id)
            JOIN item_quality iq   USING (quality_id)
            WHERE ml.current_status IN ('sold', 'listed')
              AND ii.float_value IS NOT NULL
        """)


async def _get_existing_traders(pool: asyncpg.Pool) -> list:
    """
    Берём steamid из уже существующих CSFloat аккаунтов.
    У трейдера в trader_platform_account есть platform_user_id — это steamid.
    Берём все аккаунты у которых is_monitored = TRUE.
    """
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT
                tpa.trader_platform_account_id,
                tpa.platform_user_id    AS steamid,
                tpa.trader_account_id
            FROM trader_platform_account tpa
            JOIN trader_account ta USING (trader_account_id)
            WHERE ta.is_monitored = TRUE
        """)


async def _get_steam_platform_id(pool: asyncpg.Pool) -> Optional[int]:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT platform_id FROM platform WHERE code = $1", "steam"
        )


async def _get_prev_asset_ids(
    pool: asyncpg.Pool,
    trader_platform_account_id: int,
    steam_platform_id: int,
) -> set:
    """Возвращает asset_id из последнего снапшота трейдера — чтобы найти новые предметы."""
    async with pool.acquire() as conn:
        prev_snapshot_id = await conn.fetchval("""
            SELECT trader_inventory_snapshot_id
            FROM trader_inventory_snapshot
            WHERE trader_platform_account_id = $1
            ORDER BY observed_at DESC
            LIMIT 1
        """, trader_platform_account_id)

        if not prev_snapshot_id:
            return set()

        rows = await conn.fetch("""
            SELECT ii.origin_asset_id
            FROM trader_inventory_item_snapshot tis
            JOIN item_instance ii USING (item_instance_id)
            WHERE tis.trader_inventory_snapshot_id = $1
              AND ii.origin_platform_id = $2
        """, prev_snapshot_id, steam_platform_id)

        return {r["origin_asset_id"] for r in rows}


# ─── Парсинг инвентаря ────────────────────────────────────────────────────────


async def _fetch_inventory(
    session: aiohttp.ClientSession,
    steamid: str,
    cookies: dict,
) -> dict:
    url = (
        f"https://steamcommunity.com/inventory/{steamid}/730/2"
        f"?l=english&count=75"
    )
    for attempt in range(3):
        try:
            async with session.get(
                url,
                headers=_STEAM_HEADERS,
                cookies=cookies,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 429:
                    logger.warning(f"Rate limit inventory steamid={steamid}, ждём 60 сек")
                    await asyncio.sleep(60)
                    continue
                if resp.status == 403:
                    logger.warning(f"Инвентарь закрыт steamid={steamid}")
                    return {}
                if resp.status != 200:
                    logger.error(f"HTTP {resp.status} inventory steamid={steamid}")
                    return {}
                return await resp.json(content_type=None)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout inventory steamid={steamid} attempt={attempt + 1}")
        except Exception as e:
            logger.error(f"Ошибка inventory steamid={steamid}: {e}")
            return {}
    return {}


def _parse_inventory_items(data: dict) -> list[dict]:
    """
    Парсим ответ Steam инвентаря.
    Возвращаем список словарей с нужными полями.
    Пропускаем предметы без скина (граффити, музыка, наклейки и т.д.)
    """
    SKIP_TYPES = {
        "CSGO_Type_Spray", "CSGO_Type_Collectible",
        "CSGO_Type_MusicKit", "CSGO_Type_Charm",
        "Type_Customization_Sticker",
    }

    desc_index = {
        (d["classid"], d["instanceid"]): d
        for d in data.get("descriptions", [])
    }

    result = []
    for asset in data.get("assets", []):
        desc = desc_index.get((asset["classid"], asset["instanceid"]))
        if not desc:
            continue

        tags = {t["category"]: t for t in desc.get("tags", [])}
        item_type = tags.get("Type", {}).get("internal_name", "")
        if item_type in SKIP_TYPES:
            continue

        market_hash_name = desc.get("market_hash_name", "")
        if "|" not in market_hash_name:
            continue   # пропускаем предметы без скина

        result.append({
            "asset_id":         asset["assetid"],
            "classid":          asset["classid"],
            "instanceid":       asset["instanceid"],
            "market_hash_name": market_hash_name,
            "marketable":       bool(desc.get("marketable", 0)),
            "tags":             tags,
        })

    return result


# ─── Сохранение снапшота инвентаря ───────────────────────────────────────────


async def _save_inventory_snapshot(
    pool: asyncpg.Pool,
    trader_platform_account_id: int,
    steam_platform_id: int,
    items: list[dict],
    observed_at: datetime,
) -> None:
    """
    Сохраняет снапшот инвентаря трейдера.
    Предметы помечаются платформой steam.
    """
    async with pool.acquire() as conn:
        # Создаём снапшот
        snapshot_id = await conn.fetchval("""
            INSERT INTO trader_inventory_snapshot
                (trader_platform_account_id, observed_at, total_items_count)
            VALUES ($1, $2, $3)
            ON CONFLICT (trader_platform_account_id, observed_at)
            DO UPDATE SET total_items_count = EXCLUDED.total_items_count
            RETURNING trader_inventory_snapshot_id
        """, trader_platform_account_id, observed_at, len(items))

        if not snapshot_id:
            return

        for item in items:
            mhn = item["market_hash_name"]

            # Убираем префикс и качество из названия
            import re
            clean = mhn
            for prefix in ("StatTrak™ ", "Souvenir ", "★ "):
                clean = clean.replace(prefix, "")
            clean = re.sub(r'\s*\([^)]+\)$', '', clean)

            if "|" not in clean:
                continue

            weapon_raw, skin_raw = clean.split("|", 1)
            weapon_name = weapon_raw.strip()
            skin_name   = skin_raw.strip()

            # Качество из тегов
            WEAR_MAP = {
                "WearCategory0": "Factory New",
                "WearCategory1": "Minimal Wear",
                "WearCategory2": "Field-Tested",
                "WearCategory3": "Well-Worn",
                "WearCategory4": "Battle-Scarred",
            }
            exterior = item["tags"].get("Exterior", {}).get("internal_name", "")
            quality_name = WEAR_MAP.get(exterior)
            if not quality_name:
                continue

            is_stattrak = "StatTrak™" in mhn
            is_souvenir = "Souvenir" in mhn

            # Ищем game_item_id
            game_item_id = await conn.fetchval("""
                SELECT gi.game_item_id
                FROM game_item gi
                JOIN weapon w       USING (weapon_id)
                JOIN skin s         USING (skin_id)
                JOIN item_quality iq USING (quality_id)
                WHERE w.name  = $1
                  AND s.name  = $2
                  AND iq.name = $3
                  AND gi.is_stattrak = $4
                  AND gi.is_souvenir = $5
            """, weapon_name, skin_name, quality_name, is_stattrak, is_souvenir)

            if not game_item_id:
                continue  # предмет не знаком системе — пропускаем

            # Upsert item_instance с платформой steam
            item_instance_id = await conn.fetchval("""
                INSERT INTO item_instance
                    (game_item_id, origin_platform_id, origin_asset_id, first_seen_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (origin_platform_id, origin_asset_id)
                DO UPDATE SET game_item_id = EXCLUDED.game_item_id
                RETURNING item_instance_id
            """, game_item_id, steam_platform_id, item["asset_id"], observed_at)

            if not item_instance_id:
                continue

            # Привязываем предмет к снапшоту
            await conn.execute("""
                INSERT INTO trader_inventory_item_snapshot
                    (trader_inventory_snapshot_id, item_instance_id)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
            """, snapshot_id, item_instance_id)


# ─── Публичные функции ────────────────────────────────────────────────────────


async def check_steam_inventories(pool: asyncpg.Pool) -> None:
    """
    Обходит инвентари всех трейдеров из существующих аккаунтов.
    steamid берётся из trader_platform_account.platform_user_id.
    """
    traders = await _get_existing_traders(pool)
    if not traders:
        logger.info("Нет трейдеров для мониторинга.")
        return

    steam_platform_id = await _get_steam_platform_id(pool)
    if not steam_platform_id:
        logger.error("Платформа steam не найдена в БД — запусти bootstrap")
        return

    cookies = _get_cookies()

    logger.info(f"Проверяем инвентари {len(traders)} трейдеров...")

    async with aiohttp.ClientSession() as session:
        for trader in traders:
            steamid = trader["steamid"]
            tpa_id  = trader["trader_platform_account_id"]

            data = await _fetch_inventory(session, steamid, cookies)
            if not data:
                continue

            items = _parse_inventory_items(data)
            if not items:
                logger.info(f"steamid={steamid}: пустой инвентарь")
                continue

            now = datetime.now(timezone.utc)

            await _save_inventory_snapshot(
                pool                      = pool,
                trader_platform_account_id= tpa_id,
                steam_platform_id         = steam_platform_id,
                items                     = items,
                observed_at               = now,
            )

            # logger.info(f"steamid={steamid}: снапшот сохранён ({len(items)} предметов)")
            await asyncio.sleep(1)   # пауза между трейдерами


async def update_steam_prices(pool: asyncpg.Pool) -> None:
    """Обновляет историю цен Steam для всех game_item из CSFloat листингов."""
    game_items = await _get_game_items(pool)

    if not game_items:
        logger.info("Нет game_item для обновления цен.")
        return

    cookies = _get_cookies()
    if not cookies["steamLoginSecure"]:
        logger.error("STEAM_LOGIN_SECURE не задан в .env")
        return

    logger.info(f"Обновляем цены для {len(game_items)} предметов...")

    async with aiohttp.ClientSession() as session:
        for row in game_items:
            saved = await fetch_and_store_price_history(
                pool         = pool,
                session      = session,
                game_item_id = row["game_item_id"],
                weapon_name  = row["weapon_name"],
                skin_name    = row["skin_name"],
                quality_name = row["quality_name"],
                is_stattrak  = row["is_stattrak"],
                is_souvenir  = row["is_souvenir"],
                cookies      = cookies,
            )
            logger.info(f"  {row['weapon_name']} | {row['skin_name']}: {saved} записей")
            await asyncio.sleep(1.5)

    logger.info("Цены обновлены.")