from typing import Optional, List, Dict, Any 
from datetime import datetime
from dataclasses import dataclass  
from abc import ABC, abstractmethod


class CSFloatItem:
    def __init__(self, listing: Dict[str, Any]):
        self.listing = listing
        self.id = listing.get("id")
        self.item_data = listing.get("item", {})
        self.item_price = self.listing.get("price")
        created_at_str = self.listing.get("created_at")
        if created_at_str:
            normalized = created_at_str.replace("Z", "+00:00")
            self.created_at = datetime.fromisoformat(normalized)
        self.state = self.listing.get("state")
        self.seller = self.listing.get("seller", {})

        self.seller_id = self.seller.get("steam_id") 
        self.seller_name = self.seller.get("username")
        stats = self.seller.get("statistics") or {}
        self.total_trades = stats.get("total_trades")

        self.item_type = self.item_data.get("type", {})
        self.item_full_name = self.item_data.get("item_name")
        self.is_stattrak = self.item_data.get("is_stattrak") or False
        self.is_souvenir = self.item_data.get("is_souvenir") or False
        self.quality = self.item_data.get("wear_name")
        self.asset_id = self.item_data.get("asset_id")
        self.float_value = self.item_data.get("float_value")
        self.paint_seed = self.item_data.get("paint_seed")
        self.inspect_link = self.item_data.get("serialized_inspect")
        self.stickers = self.item_data.get("stickers", [])
        self.def_index = self.item_data.get("def_index")

        if self.item_full_name and "|" in self.item_full_name:
            self.skin_name = self.item_full_name.split("|")[-1].strip()
            self.item_name = self.item_full_name.split("|")[0].strip().strip("★").strip()
        else:
            self.skin_name = None
            self.item_name = self.item_full_name


class CSSelectRepository(ABC):
    @abstractmethod
    async def weapon_id(self, conn) -> "CSSelects": ...
    @abstractmethod
    async def skin_id(self, conn) -> "CSSelects": ...
    @abstractmethod
    async def quality_id(self, conn) -> "CSSelects": ...
    @abstractmethod
    async def platform_id(self, conn, platform_data) -> "CSSelects": ...
    @abstractmethod
    async def get_game_item_id(self, conn) -> "CSSelects": ...
    @abstractmethod
    async def currency_id(self, conn) -> "CSSelects": ...
    @abstractmethod
    async def market_listing_id(self, conn, platform_data) -> "CSSelects": ...
    @abstractmethod
    async def get_item_instance_id(self, conn) -> Optional[int]: ...


class CSTraderRepository(ABC):
    @abstractmethod
    async def trader_platform_account_id(self, conn) -> "CSTraders": ...


class CSFloatGetRepository(ABC):
    @abstractmethod
    async def get_items(self) -> list: ...
    @abstractmethod
    async def get_skins(self) -> list: ...
    @abstractmethod
    async def get_seller_ids(self) -> list: ...


class CSSelects(CSSelectRepository, CSFloatItem):
    def __init__(self, listing: Dict[str, Any]):
        CSFloatItem.__init__(self, listing)
        self._weapon_id: int = None
        self._skin_id: int = None
        self._quality_id: int = None
        self._game_item_id: int = None
        self._platform_id: int = None
        self._currency_id: int = None
        self._event_type_id: int = None
        self._market_listing_id: int = None
        self._container_id: int = None
        self.item_instance_id: int = None

    async def weapon_id(self, conn) -> "CSSelects":
        if self._weapon_id is None:
            self._weapon_id = await conn.fetchval(
                "SELECT weapon_id FROM weapon WHERE name=$1",
                self.item_name
            )
        return self._weapon_id 

    async def skin_id(self, conn) -> "CSSelects":
        if self._skin_id is None:
            self._skin_id = await conn.fetchval(
                "SELECT skin_id FROM skin WHERE name=$1",
                self.skin_name
            )
        return self._skin_id

    async def quality_id(self, conn) -> "CSSelects":
        if self._quality_id is None:
            self._quality_id = await conn.fetchval(
                "SELECT quality_id FROM item_quality WHERE name=$1",
                self.quality
            )
        return self._quality_id

    async def platform_id(self, conn, platform_data: str):
        if self._platform_id is None:
            self._platform_id = await conn.fetchval(
                "SELECT platform_id FROM platform WHERE code=$1",
                platform_data
            )
        return self._platform_id 

    async def currency_id(self, conn):
        if self._currency_id is None:
            self._currency_id = await conn.fetchval(
                "SELECT currency_id FROM currency WHERE code=$1",
                "USD"
            )
        return self._currency_id

    async def event_type_id(self, conn):
        if self._event_type_id is None:
            self._event_type_id = await conn.fetchval(
                "SELECT event_type_id FROM event_type WHERE code=$1",
                self.state
            )
        return self._event_type_id

    async def container_id(self, conn):
        if self._container_id is None:
            self._container_id = await conn.fetchval(
                "SELECT container_id FROM container WHERE def_index=$1",
                self.def_index
            )
        return self._container_id

    async def get_game_item_id(self, conn) -> "CSSelects":
        if self._game_item_id is None:
            w_id = await self.weapon_id(conn)
            s_id = await self.skin_id(conn)
            q_id = await self.quality_id(conn)
            # ИСПРАВЛЕНО: запятые заменены на AND в WHERE
            self._game_item_id = await conn.fetchval("""
                SELECT game_item_id FROM game_item
                WHERE weapon_id=$1 AND skin_id=$2 AND quality_id=$3
                AND is_stattrak=$4 AND is_souvenir=$5
            """,
            w_id, s_id, q_id,
            self.is_stattrak,
            self.is_souvenir
            )
        return self._game_item_id

    async def market_listing_id(self, conn, platform_data: str):
        if self._market_listing_id is None:    
            p_id = await self.platform_id(conn, platform_data)
            # ИСПРАВЛЕНО: запятая заменена на AND
            self._market_listing_id = await conn.fetchval("""
                SELECT market_listing_id FROM market_listing
                WHERE platform_id=$1 AND external_listing_id=$2
            """,
            p_id, self.id
            )
        return self._market_listing_id

    async def get_item_instance_id(self, conn) -> Optional[int]:
        g_i_id = await self.get_game_item_id(conn)
        # ИСПРАВЛЕНО: "csfoat" -> "csfloat"
        p_id = await self.platform_id(conn, "csfloat")

        # ИСПРАВЛЕНО: проверка self.item_instance_id вместо self._market_listing_id
        if self.item_instance_id is None:
            self.item_instance_id = await conn.fetchval("""
                SELECT item_instance_id FROM item_instance
                WHERE game_item_id=$1 AND origin_platform_id=$2 AND origin_asset_id=$3
            """,
            g_i_id,
            p_id,
            self.asset_id
            )
        return self.item_instance_id


class CSTraders(CSTraderRepository, CSSelects):
    def __init__(self, listing: Dict[str, Any]):
        CSSelects.__init__(self, listing)
        self._trader_id: int = None
        self._trader_inventory_snapshot_id: int = None

    async def trader_platform_account_id(self, conn) -> "CSTraders":
        p_id = await self.platform_id(conn, "csfloat")
        if self._trader_id is None:
            self._trader_id = await conn.fetchval(
                """
                SELECT trader_platform_account_id
                FROM trader_platform_account
                WHERE platform_id = $1 AND platform_user_id = $2
                """,
                p_id,
                str(self.seller_id)
            )
        return self._trader_id

    async def trader_inventory_snapshot_id(self, conn, observed_at) -> int:
        trader_platform_account_id = await self.trader_platform_account_id(conn)
        if self._trader_inventory_snapshot_id is None:
            self._trader_inventory_snapshot_id = await conn.fetchval(
                """
                INSERT INTO trader_inventory_snapshot (
                    trader_platform_account_id,
                    observed_at,
                    total_items_count
                )
                VALUES ($1, $2, $3)
                ON CONFLICT (trader_platform_account_id, observed_at) DO UPDATE
                SET total_items_count = EXCLUDED.total_items_count
                RETURNING trader_inventory_snapshot_id
                """,
                trader_platform_account_id,
                observed_at,
                0
            )
        return self._trader_inventory_snapshot_id


class CSFloatGet(CSFloatGetRepository):
    def __init__(self, pool):
        self.pool = pool
        self.data = None
        self.skins = None
        self.seller_ids = None

    async def get_items(self) -> list:
        async with self.pool.acquire() as conn:
            if self.data is None:
                self.data = await conn.fetch("SELECT external_listing_id FROM market_listing")
        return self.data

    async def get_skins(self) -> list:
        async with self.pool.acquire() as conn:
            if self.skins is None:
                self.skins = await conn.fetch("SELECT name FROM skin")
        return self.skins

    async def get_seller_ids(self) -> list:
        async with self.pool.acquire() as conn:
            if self.seller_ids is None:
                self.seller_ids = await conn.fetch(
                    "SELECT platform_user_id FROM trader_platform_account WHERE platform_id = 2"
                )
        return self.seller_ids


class CursorState:
    def __init__(self):
        self.cursor: str | None = None

    def get(self) -> str | None:
        return self.cursor

    def set(self, value: str | None) -> None:
        self.cursor = value

    def clear(self) -> None:
        self.cursor = None

