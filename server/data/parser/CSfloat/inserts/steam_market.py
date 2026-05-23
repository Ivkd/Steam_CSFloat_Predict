"""
steam_market.py — загрузка истории цен с Steam Market.
Использует /market/pricehistory/ — возвращает массив [дата, цена, объём].
Сохраняет в таблицу steam_price_history.
"""
import asyncio
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

import aiohttp
import asyncpg


# ─── Построение market_hash_name ─────────────────────────────────────────────

def build_market_hash_name(
    weapon_name: str,
    skin_name: str,
    quality_name: str,
    is_stattrak: bool,
    is_souvenir: bool,
) -> str:
    """
    Собираем строку для запроса к Steam.
    Пример: "StatTrak™ AK-47 | Redline (Field-Tested)"
    """
    prefix = ""
    if is_souvenir:
        prefix = "Souvenir "
    elif is_stattrak:
        prefix = "StatTrak™ "
    return f"{prefix}{weapon_name} | {skin_name} ({quality_name})"


# ─── Загрузка истории цен ─────────────────────────────────────────────────────

async def fetch_price_history(
    session: aiohttp.ClientSession,
    market_hash_name: str,
    cookies: dict,         # нужны steamLoginSecure + sessionid
) -> Optional[list]:
    """
    Возвращает список записей: [(дата_str, цена_float, объём_int), ...]
    или None если ошибка.
    """
    encoded = urllib.parse.quote(market_hash_name)
    url = f"https://steamcommunity.com/market/pricehistory/?appid=730&market_hash_name={encoded}"

    try:
        async with session.get(
            url,
            cookies=cookies,
            timeout=aiohttp.ClientTimeout(total=20)
        ) as resp:
            if resp.status == 429:
                await asyncio.sleep(60)
                return None
            if resp.status == 401:
                raise RuntimeError("Steam: нет авторизации — проверь cookies")
            if resp.status != 200:
                return None

            data = await resp.json(content_type=None)
            if not data.get("success"):
                return None

            return data.get("prices", [])

    except asyncio.TimeoutError:
        return None
    except Exception:
        return None


# ─── Сохранение в БД ──────────────────────────────────────────────────────────

async def store_price_history(
    pool: asyncpg.Pool,
    game_item_id: int,
    prices: list,
) -> int:
    """
    Сохраняет историю цен в steam_price_history.
    Возвращает количество сохранённых записей.
    Структура prices: [["Feb 21 2014 01: +0", 41.405, "198"], ...]
    """
    if not prices:
        return 0

    records = []
    for entry in prices:
        try:
            date_str = entry[0].split(" 01:")[0].strip()   # "Feb 21 2014"
            price    = float(entry[1])
            volume   = int(entry[2])
            date     = datetime.strptime(date_str, "%b %d %Y").replace(tzinfo=timezone.utc)
            records.append((game_item_id, date, price, volume))
        except (ValueError, IndexError):
            continue

    if not records:
        return 0

    async with pool.acquire() as conn:
        await conn.executemany("""
            INSERT INTO steam_price_history
                (game_item_id, recorded_at, median_price_usd, volume)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (game_item_id, recorded_at) DO UPDATE
                SET median_price_usd = EXCLUDED.median_price_usd,
                    volume           = EXCLUDED.volume
        """, records)

    return len(records)


# ─── Главная функция ──────────────────────────────────────────────────────────

async def fetch_and_store_price_history(
    pool: asyncpg.Pool,
    session: aiohttp.ClientSession,
    game_item_id: int,
    weapon_name: str,
    skin_name: str,
    quality_name: str,
    is_stattrak: bool,
    is_souvenir: bool,
    cookies: dict,
) -> int:
    mhn    = build_market_hash_name(weapon_name, skin_name, quality_name, is_stattrak, is_souvenir)
    prices = await fetch_price_history(session, mhn, cookies)
    if prices is None:
        return 0
    return await store_price_history(pool, game_item_id, prices)