import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod


class SteamItem:
    WEAR_MAP = {
        "WearCategory0": "Factory New",
        "WearCategory1": "Minimal Wear",
        "WearCategory2": "Field-Tested",
        "WearCategory3": "Well-Worn",
        "WearCategory4": "Battle-Scarred",
    }
    SKIP_TYPES = {
        "CSGO_Type_Spray", "CSGO_Type_Collectible",
        "CSGO_Type_MusicKit", "CSGO_Type_Charm",
    }

    def __init__(self, asset: Dict, description: Dict):
        self.asset_id: str = asset["assetid"]
        self.classid: str = asset["classid"]
        self.instanceid: str = asset["instanceid"]

        self.market_hash_name: str = description.get("market_hash_name", "")
        self.item_full_name: str = description.get("name", "")
        self.marketable: bool = bool(description.get("marketable", 0))

        tags = {t["category"]: t for t in description.get("tags", [])}
        self.item_type: str = tags.get("Type", {}).get("internal_name", "")
        self.weapon_name: Optional[str] = tags.get("Weapon", {}).get("localized_tag_name")
        exterior_internal = tags.get("Exterior", {}).get("internal_name", "")
        self.quality: Optional[str] = self.WEAR_MAP.get(exterior_internal)

        self.is_stattrak: bool = "StatTrak™" in self.item_full_name
        self.is_souvenir: bool = "Souvenir" in self.item_full_name

        # Парсим weapon | skin из market_hash_name
        clean = self.market_hash_name
        for prefix in ("StatTrak™ ", "Souvenir ", "★ "):
            clean = clean.replace(prefix, "")
        clean = re.sub(r'\s*\([^)]+\)$', '', clean)

        if "|" in clean:
            parts = clean.split("|", 1)
            self.item_name: str = parts[0].strip()
            self.skin_name: Optional[str] = parts[1].strip()
        else:
            self.item_name = clean.strip()
            self.skin_name = None

        self.first_seen_at = datetime.now(timezone.utc)

    @property
    def should_skip(self) -> bool:
        return self.skin_name is None or self.item_type in self.SKIP_TYPES


def build_steam_items(response: Dict) -> List[SteamItem]:
    desc_index = {
        (d["classid"], d["instanceid"]): d
        for d in response.get("descriptions", [])
    }
    return [
        SteamItem(asset, desc)
        for asset in response.get("assets", [])
        if (desc := desc_index.get((asset["classid"], asset["instanceid"]))) is not None
    ]


# ─── Репозитории (аналог CSSelectRepository) ─────────────────────────────────

class SteamSelectRepository(ABC):
    @abstractmethod
    async def weapon_id(self, conn) -> Optional[int]: ...
    @abstractmethod
    async def skin_id(self, conn) -> Optional[int]: ...
    @abstractmethod
    async def quality_id(self, conn) -> Optional[int]: ...
    @abstractmethod
    async def platform_id(self, conn) -> Optional[int]: ...
    @abstractmethod
    async def get_game_item_id(self, conn) -> Optional[int]: ...
    @abstractmethod
    async def get_item_instance_id(self, conn) -> Optional[int]: ...


class SteamTraderRepository(ABC):
    @abstractmethod
    async def trader_platform_account_id(self, conn) -> Optional[int]: ...


class SteamGetRepository(ABC):
    @abstractmethod
    async def get_trader_ids(self) -> list: ...
    @abstractmethod
    async def get_game_items_for_price(self) -> list: ...


# ─── SteamSelects (аналог CSSelects) ─────────────────────────────────────────

class SteamSelects(SteamSelectRepository, SteamItem):
    def __init__(self, asset: Dict, description: Dict):
        SteamItem.__init__(self, asset, description)
        self._weapon_id: Optional[int] = None
        self._skin_id: Optional[int] = None
        self._quality_id: Optional[int] = None
        self._platform_id: Optional[int] = None
        self._game_item_id: Optional[int] = None
        self.item_instance_id: Optional[int] = None

    async def weapon_id(self, conn) -> Optional[int]:
        if self._weapon_id is None:
            self._weapon_id = await conn.fetchval(
                "SELECT weapon_id FROM weapon WHERE name=$1", self.item_name
            )
        return self._weapon_id

    async def skin_id(self, conn) -> Optional[int]:
        if self._skin_id is None:
            self._skin_id = await conn.fetchval(
                "SELECT skin_id FROM skin WHERE name=$1", self.skin_name
            )
        return self._skin_id

    async def quality_id(self, conn) -> Optional[int]:
        if self._quality_id is None:
            self._quality_id = await conn.fetchval(
                "SELECT quality_id FROM item_quality WHERE name=$1", self.quality
            )
        return self._quality_id

    async def platform_id(self, conn) -> Optional[int]:
        if self._platform_id is None:
            self._platform_id = await conn.fetchval(
                "SELECT platform_id FROM platform WHERE code=$1", "steam"
            )
        return self._platform_id

    async def get_game_item_id(self, conn) -> Optional[int]:
        if self._game_item_id is None:
            w_id = await self.weapon_id(conn)
            s_id = await self.skin_id(conn)
            q_id = await self.quality_id(conn)
            if not all([w_id, s_id, q_id]):
                return None
            self._game_item_id = await conn.fetchval("""
                SELECT game_item_id FROM game_item
                WHERE weapon_id=$1 AND skin_id=$2 AND quality_id=$3
                  AND is_stattrak=$4 AND is_souvenir=$5
            """, w_id, s_id, q_id, self.is_stattrak, self.is_souvenir)
        return self._game_item_id

    async def get_item_instance_id(self, conn) -> Optional[int]:
        if self.item_instance_id is None:
            game_item_id = await self.get_game_item_id(conn)
            platform_id = await self.platform_id(conn)
            if not all([game_item_id, platform_id]):
                return None
            self.item_instance_id = await conn.fetchval("""
                INSERT INTO item_instance
                    (game_item_id, origin_platform_id, origin_asset_id, first_seen_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (origin_platform_id, origin_asset_id)
                DO UPDATE SET game_item_id = EXCLUDED.game_item_id
                RETURNING item_instance_id
            """, game_item_id, platform_id, self.asset_id, self.first_seen_at.isoformat())
        return self.item_instance_id


# ─── SteamTraders (аналог CSTraders) ─────────────────────────────────────────

class SteamTraders(SteamTraderRepository, SteamSelects):
    def __init__(self, asset: Dict, description: Dict, owner_steamid: str):
        SteamSelects.__init__(self, asset, description)
        self.owner_steamid = owner_steamid
        self._trader_id: Optional[int] = None
        self._snapshot_id: Optional[int] = None

    async def trader_platform_account_id(self, conn) -> Optional[int]:
        if self._trader_id is None:
            platform_id = await self.platform_id(conn)
            self._trader_id = await conn.fetchval("""
                SELECT trader_platform_account_id
                FROM trader_platform_account
                WHERE platform_id=$1 AND platform_user_id=$2
            """, platform_id, self.owner_steamid)
        return self._trader_id

    async def inventory_snapshot_id(self, conn, observed_at: datetime, total: int) -> Optional[int]:
        if self._snapshot_id is None:
            trader_id = await self.trader_platform_account_id(conn)
            if not trader_id:
                return None
            self._snapshot_id = await conn.fetchval("""
                INSERT INTO trader_inventory_snapshot
                    (trader_platform_account_id, observed_at, total_items_count)
                VALUES ($1, $2, $3)
                ON CONFLICT (trader_platform_account_id, observed_at)
                DO UPDATE SET total_items_count = EXCLUDED.total_items_count
                RETURNING trader_inventory_snapshot_id
            """, trader_id, observed_at, total)
        return self._snapshot_id


# ─── SteamGet (аналог CSFloatGet) ────────────────────────────────────────────

class SteamGet(SteamGetRepository):
    def __init__(self, pool):
        self.pool = pool
        self._trader_ids = None
        self._game_items = None

    async def get_trader_ids(self) -> list:
        async with self.pool.acquire() as conn:
            if self._trader_ids is None:
                platform_id = await conn.fetchval(
                    "SELECT platform_id FROM platform WHERE code=$1", "steam"
                )
                self._trader_ids = await conn.fetch("""
                    SELECT tpa.trader_platform_account_id, tpa.platform_user_id
                    FROM trader_platform_account tpa
                    JOIN trader_account ta USING (trader_account_id)
                    WHERE ta.is_monitored=TRUE
                """)
        return self._trader_ids

    async def get_game_items_for_price(self) -> list:
        """Уникальные game_item из steam инвентарей для запроса цен."""
        async with self.pool.acquire() as conn:
            if self._game_items is None:
                platform_id = await conn.fetchval(
                    "SELECT platform_id FROM platform WHERE code=$1", "steam"
                )
                self._game_items = await conn.fetch("""
                    SELECT DISTINCT
                        gi.game_item_id,
                        gi.is_stattrak,
                        gi.is_souvenir,
                        w.name  AS weapon_name,
                        s.name  AS skin_name,
                        iq.name AS quality_name
                    FROM item_instance ii
                    JOIN game_item gi    USING (game_item_id)
                    JOIN weapon w        USING (weapon_id)
                    JOIN skin s          USING (skin_id)
                    JOIN item_quality iq USING (quality_id)
                    WHERE ii.origin_platform_id = $1
                """, platform_id)
        return self._game_items