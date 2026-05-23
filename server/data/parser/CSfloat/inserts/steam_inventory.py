from datetime import datetime, timezone
from typing import List
from ...Steam.type import SteamSelects, SteamTraders


async def upsert_steam_trader(pool, owner_steamid: str) -> None:
    """Добавляем трейдера если нет (аналог upsert_trader_from_listing)."""
    async with pool.acquire() as conn:
        platform_id = await conn.fetchval(
            "SELECT platform_id FROM platform WHERE code=$1", "steam"
        )
        existing = await conn.fetchval("""
            SELECT trader_platform_account_id FROM trader_platform_account
            WHERE platform_id=$1 AND platform_user_id=$2
        """, platform_id, owner_steamid)

        if existing:
            return

        trader_account_id = await conn.fetchval("""
            INSERT INTO trader_account (nickname, is_monitored)
            VALUES ($1, TRUE)
            RETURNING trader_account_id
        """, owner_steamid)

        await conn.execute("""
            INSERT INTO trader_platform_account
                (trader_account_id, platform_id, platform_user_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (platform_id, platform_user_id) DO NOTHING
        """, trader_account_id, platform_id, owner_steamid)


async def insert_steam_inventory_snapshot(
    pool,
    owner_steamid: str,
    item_instances: List[SteamSelects],
    prev_instance_ids: set,
    now: datetime
) -> None:
    """
    Аналог insert_stall_data:
    - снапшот инвентаря
    - item_instance для каждого предмета
    - trader_item_action для появившихся (listed) и пропавших (not_listed)
    """
    async with pool.acquire() as conn:
        platform_id = await conn.fetchval(
            "SELECT platform_id FROM platform WHERE code=$1", "steam"
        )
        trader_id = await conn.fetchval("""
            SELECT trader_platform_account_id FROM trader_platform_account
            WHERE platform_id=$1 AND platform_user_id=$2
        """, platform_id, owner_steamid)

        if not trader_id:
            return

        # Собираем item_instance_id для всех текущих предметов
        current_iids = []
        current_asset_ids = set()

        for sel in item_instances:
            iid = await sel.get_item_instance_id(conn)
            if iid:
                current_iids.append(iid)
                current_asset_ids.add(sel.asset_id)

        # Снапшот
        snapshot_id = await conn.fetchval("""
            INSERT INTO trader_inventory_snapshot
                (trader_platform_account_id, observed_at, total_items_count)
            VALUES ($1, $2, $3)
            ON CONFLICT (trader_platform_account_id, observed_at)
            DO UPDATE SET total_items_count = EXCLUDED.total_items_count
            RETURNING trader_inventory_snapshot_id
        """, trader_id, now, len(current_iids))

        for iid in current_iids:
            await conn.execute("""
                INSERT INTO trader_inventory_item_snapshot
                    (trader_inventory_snapshot_id, item_instance_id)
                VALUES ($1, $2)
                ON CONFLICT (trader_inventory_snapshot_id, item_instance_id) DO NOTHING
            """, snapshot_id, iid)

        # Появившиеся и пропавшие → trader_item_action
        appeared_iids = [
            iid for sel, iid in zip(item_instances, current_iids)
            if sel.asset_id not in prev_instance_ids
        ]
        disappeared_asset_ids = prev_instance_ids - current_asset_ids
        disappeared_iids = []
        if disappeared_asset_ids:
            rows = await conn.fetch("""
                SELECT item_instance_id FROM item_instance
                WHERE origin_platform_id=$1 AND origin_asset_id=ANY($2::text[])
            """, platform_id, list(disappeared_asset_ids))
            disappeared_iids = [r["item_instance_id"] for r in rows]

        for event_code, iids in [("listed", appeared_iids), ("not_listed", disappeared_iids)]:
            if not iids:
                continue
            event_type_id = await conn.fetchval(
                "SELECT event_type_id FROM event_type WHERE code=$1", event_code
            )
            if not event_type_id:
                continue
            for iid in iids:
                await conn.execute("""
                    INSERT INTO trader_item_action
                        (trader_platform_account_id, item_instance_id,
                         event_type_id, action_time, confidence_score)
                    VALUES ($1, $2, $3, $4, $5)
                """, trader_id, iid, event_type_id, now, 0.80)