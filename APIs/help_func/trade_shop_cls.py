import os
from typing import Any, List, Dict, Sequence, Optional
from dotenv import load_dotenv
from APIs.help_func.log import Helpfull
from functools import wraps

from pathlib import Path
import asyncio
import aiohttp
import asyncpg
import redis.asyncio
import json

from APIs.help_func.log import Helpfull
LOGS_ = Helpfull()
red = redis.asyncio.Redis(host="localhost", port=6379)
load_dotenv("C:/Users/user/Desktop/My_poject/X/.env")
INIT_LOCK = asyncio.Lock()
CACHE_TIME = 600

# изменить
class Cache:
    def __init__(self, prefix: str, ttl: int = CACHE_TIME):
        self.prefix = prefix
        self.ttl = ttl

    async def get_from_redis(self, key_:str ) -> list:
        raw = await red.get(key_)
        return json.loads(raw) if raw else None


    def deco(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            safe_args = args[1:] 
            key = f"{self.prefix}:{json.dumps([safe_args, kwargs], default=str)}"

            cached = await self.get_from_redis(key)
            if cached is not None:
                return cached, 200

            result, status_cod = await func(*args, **kwargs)
            await red.setex(key, self.ttl, json.dumps(result))

            return result, status_cod 
        return wrapper


class PgAsync:
    def __init__(
        self, 
        sql_path: Path, 
        dbname: str, 
        min_size: int = 1, 
        max_size: int = 5
        ):

        self.sql_path = sql_path
        self.dbname = dbname
        self.min_size = min_size
        self.max_size = max_size
        self.pool: asyncpg.Pool | None = None

    async def __aenter__(self) -> "PgAsync":
        self.pool = await asyncpg.create_pool(
            host=os.getenv("HOST"),
            port=int(os.getenv("PORT", "5432")),
            user=os.getenv("USER"),
            password=os.getenv("PASSWORD"),
            database=self.dbname,
            min_size=self.min_size,
            max_size=self.max_size,
        )

        sql = self.sql_path.read_text(encoding="utf-8")
        async with self.pool.acquire() as conn:
            async with INIT_LOCK:
                await conn.execute(sql)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        if self.pool:
            await self.pool.close()
            self.pool = None
        return False

    async def save_many(
        self, 
        query: str,     
        rows: Sequence[tuple] 
        ) -> None:
        if not rows:
            return
        async with self.pool.acquire() as conn:
            await conn.executemany(query, rows)

    @LOGS_.log_
    # @LOGS_.count_calls
    async def fetch_all(
        self, 
        query: str, 
        *args:Any
        ) -> list[asyncpg.Record]:
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

class CSFloatAsync:
    def __init__(self, url:str):
        self._url= url
        self._cursor:str | None = None

    @LOGS_.log_
    @LOGS_.count_calls
    @LOGS_.sey_time
    @Cache(prefix="csf_items").deco
    async def get_data_skins( 
        self,
        min_price: int = 0,
        max_price: int | None = None,
        sort_by: str | None = None,
        category: int | None = None,
        def_index: int | None = None,
        limit: int = 40,
        sleep: float = 0.7,
        timeout: float = 20.0,
        **extra_params: Any,
    ):
        items: List[Dict[str, Any]] = []
        headers = {"Authorization": os.getenv("API_KEY", "")}
        page = 0
        client_timeout = aiohttp.ClientTimeout(total=timeout)
        params: Dict[str, Any] = {
            "limit": limit,
            "category": category,
            "min_price": min_price,
            "max_price": max_price,
            "sort_by": sort_by,
            "def_index": def_index,
            **extra_params
        }

        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            while True:
                async with session.get(self._url, params=params, headers=headers) as resp:
                    if resp.status != 200:
                        err_status_cod(resp.status, "csf_items")
                        return items, resp.status
                    payload = await resp.json()

                self._cursor = payload.get("cursor")
                params["cursor"] = self._cursor

                for listing in payload.get("data", []):
                    item = listing.get("item", {})
                    items.append(
                        {
                            "id":                   listing.get("id"),
                            "type":                 listing.get("type"),
                            "price":                listing.get("price"),
                            "float_value":          item.get("float_value"),
                            "icon_url":             item.get("icon_url"),
                            "market_hash_name":     item.get("market_hash_name"),
                            "item_name":            item.get("item_name"),
                            "wear_name":            item.get("wear_name"),
                            "paint_index":          item.get("paint_index"),
                        }
                    )

                if page % 10 == 0:
                    LOGS_.log.info(f"csf, {page}")

                page += 1
                if not self._cursor:
                    return items, 200

                await asyncio.sleep(sleep)
    
    @LOGS_.log_
    @LOGS_.count_calls
    @LOGS_.sey_time
    @Cache(prefix="csf_case").deco
    async def get_data_containers(
        self,
        timeout: float = 20.0,
        ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        headers = {"Authorization": os.getenv("API_KEY", "")}

        client_timeout = aiohttp.ClientTimeout(total=timeout)

        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.get(self._url, headers=headers) as resp:
                if resp.status != 200:
                    err_status_cod(resp.status, "csf_case")
                    return items, resp.status
                
                payload = await resp.json()
                data_ = payload.get("data")

                for listing in data_[0].get("items"):
                    items.append(
                        {
                            "market_hash_name": listing.get("market_hash_name"),
                            "price": listing.get("price"),
                        }
                    )

                return items, 200
    
    @LOGS_.count_calls
    async def get_similar_items(self):
        items: List[Dict[str, Any]] = []
        async with aiohttp.ClientSession()as sesi:
            async with sesi.get(self._url) as resp:
                if resp.status != 200:
                    err_status_cod(resp.status, "csf_similar")
                    return items, resp.status

                data = await resp.json()

                if not data:
                    err_not_mash_page(1, "csf_sim")
                    return items, 200

                for item in data:
                    i = item.get("item")
                    items.append(
                        {   
                            "id": item.get("id"),
                            "market_hash_name": i.get("market_hash_name"),
                            "price": item.get("price"),
                            "type": item.get("type")
                        }
                    )
                return items, 200


    @LOGS_.count_calls
    # @Cache(prefix=("csf_hist")).deco # ошибка 
    async def get_from_history(self):
        items: List[Dict[str, Any]] = []
        async with aiohttp.ClientSession() as sesion:
            async with sesion.get(self._url) as resp:
                if resp.status != 200:
                    err_status_cod(resp.status, "csf_history")
                    return items, resp.status

                data = await resp.json()
                
                if not data:
                    err_not_mash_page(1, "csf_hist")
                    return items, 200

                for item in data:
                    i = item.get("item")
                    items.append(
                        {
                            "market_hash_name": i.get("market_hash_name"),
                            "price": item.get("price"),
                            # добавить еще полей 
                        }
                    )
                return items, 200


class SteamAsync:
    def __init__(self, url: str):
        self._url = url

    @LOGS_.log_
    @LOGS_.count_calls
    @LOGS_.sey_time
    # @Cache(prefix=("steam")).deco # ошибка 
    async def get_data(
        self,
        query: str = "",
        start: int = 0,
        sort_column: str | None = None,
        sort_dir: str | None = None,
        norender: int = 1,
        sleep: float = 0.5,
        max_pages: int | None = None,
        timeout: float = 20.0,
        category:str = "",
        **extra_params: Any,
    ):
        
        items: List[Dict[str, Any]] = []
        cur_start = start
        client_timeout = aiohttp.ClientTimeout(total=timeout)


        total_count = None

        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            for _ in range(max_pages):
                params = {
                    "query": query,
                    "start": cur_start,
                    "appid": 730,
                    "sort_column": sort_column,
                    "sort_dir": sort_dir,
                    "category_730_Weapon[]": category,
                    "norender": norender,
                    **extra_params,
                }

                headers = {
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json,text/javascript,*/*;q=0.1",
                    "Referer": "https://steamcommunity.com/market/",
                    "Cookie": os.getenv("COOKIS")
                }
                async with session.get(self._url,params=params, headers=headers, timeout=20) as resp:
                    if resp.status != 200:
                        err_status_cod(resp.status, "steam") # интересная задумка можно сделать для всех 
                        return items, resp.status
                    
                    payload = await resp.json()
                    total_count = payload.get("total_count")
                    results = payload.get("results")
                    
                    if total_count == 0:
                        LOGS_.log.info(f"steam, {cur_start}, count: {total_count}, result: {results[:300]}")
                        continue
                    
                    if cur_start >= total_count:
                        return items, 200

                    for it in results:
                        ad = it.get("asset_description") or {}
                        items.append(
                            {
                                "item_name": it.get("name"),
                                "market_hash_name": it.get("hash_name"),
                                "sell_listings": it.get("sell_listings"),
                                "sell_price": it.get("sell_price"),
                                "icon_url": ad.get("icon_url"),
                            }
                        )



                    if cur_start % 50 == 0:
                        LOGS_.log.info(f"steam work {cur_start}, remained: {total_count}")
                    cur_start += 10
                    await asyncio.sleep(sleep)
        return items, 200
    
@LOGS_.func_say
def err_status_cod(cod, where = None):
    return cod, where

@LOGS_.func_say
def err_not_mash_page(total_count, where = None):
    return total_count, where