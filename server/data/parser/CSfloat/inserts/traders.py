from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from .....core.logger import get_logger
from server.data.parser.CSfloat.inserts.utilits.types import CSFloatItem, CSSelects, CSTraders

logger = get_logger("parserFloatTrader")

PLATFORM_CODE = "csfloat"


async def upsert_trader_from_listing(pool, cs_item: CSFloatItem) -> None:
    """
    Создаёт или обновляет trader_account и trader_platform_account.
    Используем ON CONFLICT чтобы не дублировать продавца при повторных парсингах.
    """
    async with pool.acquire() as conn:
        csselect = CSSelects(cs_item.listing)
        platform_id = await csselect.platform_id(conn, PLATFORM_CODE)

        nickname = cs_item.seller_name.strip() if cs_item.seller_name else None
        nickname = nickname or None

        # Upsert trader_account по nickname
        trader_account_id = await conn.fetchval(
            """
            INSERT INTO trader_account (nickname, total_trades, is_monitored)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
            RETURNING trader_account_id
            """,
            nickname,
            cs_item.total_trades,
            True,
        )

        # Если ON CONFLICT DO NOTHING сработал — запись уже существует, получаем id
        if trader_account_id is None:
            if nickname:
                trader_account_id = await conn.fetchval(
                    "SELECT trader_account_id FROM trader_account WHERE nickname = $1",
                    nickname
                )
            # Если nickname NULL — ищем по platform_user_id через platform_account
            if trader_account_id is None:
                trader_account_id = await conn.fetchval(
                    """
                    SELECT trader_account_id 
                    FROM trader_platform_account
                    WHERE platform_id = $1 AND platform_user_id = $2
                    """,
                    platform_id,
                    str(cs_item.seller_id)
                )

        # Upsert trader_platform_account по (platform_id, platform_user_id)
        await conn.execute(
            """
            INSERT INTO trader_platform_account (
                trader_account_id,
                platform_id,
                platform_user_id,
                profile_url
            )
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (platform_id, platform_user_id) DO UPDATE
            SET profile_url = EXCLUDED.profile_url
            """,
            trader_account_id,
            platform_id,
            str(cs_item.seller_id),
            f"https://csfloat.com/stall/{cs_item.seller_id}"
        )


async def create_trader_inventory_snapshot(pool, cs_item: CSFloatItem) -> Optional[int]:
    """
    Создаёт снимок инвентаря трейдера для текущего момента парсинга.
    Возвращает trader_inventory_snapshot_id.
    """
    cstraders = CSTraders(cs_item.listing)
    observed_at = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        trader_platform_account_id = await cstraders.trader_platform_account_id(conn)
        if trader_platform_account_id is None:
            logger.warning(f"trader_platform_account не найден для seller_id={cs_item.seller_id}")
            return None

        snapshot_id = await conn.fetchval(
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
            0  # TODO: заменить на реальное количество предметов из stall-страницы
        )
        return snapshot_id


async def insert_trader_inventory_item_snapshot(pool, cs_item: CSFloatItem) -> None:
    """
    Сохраняет конкретный предмет в снимке инвентаря трейдера.
    Записывает цену листинга и признак is_listed_for_sale=True.
    """
    async with pool.acquire() as conn:
        csselect = CSSelects(cs_item.listing)
        cstraders = CSTraders(cs_item.listing)

        observed_at = datetime.now(timezone.utc)
        trader_inventory_snapshot_id = await cstraders.trader_inventory_snapshot_id(conn, observed_at)
        item_instance_id = await csselect.get_item_instance_id(conn)
        currency_id = await csselect.currency_id(conn)

        if trader_inventory_snapshot_id is None or item_instance_id is None:
            logger.warning(
                f"Пропуск trader_inventory_item_snapshot: snapshot_id={trader_inventory_snapshot_id}, "
                f"item_instance_id={item_instance_id}, asset_id={cs_item.asset_id}"
            )
            return

        await conn.execute(
            """
            INSERT INTO trader_inventory_item_snapshot (
                trader_inventory_snapshot_id,
                item_instance_id,
                estimated_acquired_at,
                estimated_unlock_at,
                observed_list_price,
                currency_id,
                is_listed_for_sale
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (trader_inventory_snapshot_id, item_instance_id)
            DO UPDATE
            SET observed_list_price = EXCLUDED.observed_list_price,
                currency_id         = EXCLUDED.currency_id,
                is_listed_for_sale  = EXCLUDED.is_listed_for_sale
            """,
            trader_inventory_snapshot_id,
            item_instance_id,
            None,  # estimated_acquired_at — неизвестно из API
            None,  # estimated_unlock_at — неизвестно из API
            cs_item.item_price,
            currency_id,
            True   # предмет активно выставлен
        )


async def insert_trader_item_action(pool, cs_item: CSFloatItem) -> Optional[int]:
    """
    Записывает событие 'listed' для предмета трейдера.
    При каждом парсинге stall-страницы — это событие 'listed' (предмет виден в продаже).
    """
    async with pool.acquire() as conn:
        csselect = CSSelects(cs_item.listing)
        cstraders = CSTraders(cs_item.listing)

        trader_platform_account_id = await cstraders.trader_platform_account_id(conn)
        item_instance_id = await csselect.get_item_instance_id(conn)
        currency_id = await csselect.currency_id(conn)

        # Для stall-парсинга всегда фиксируем событие 'listed'
        event_type_id = await conn.fetchval(
            "SELECT event_type_id FROM event_type WHERE code = $1",
            "listed"
        )
        action_time = datetime.now(timezone.utc)
        observed_at = action_time
        source_snapshot_id = await cstraders.trader_inventory_snapshot_id(conn, observed_at)

        if trader_platform_account_id is None or item_instance_id is None or event_type_id is None:
            logger.warning(
                f"Пропуск trader_item_action: trader_id={trader_platform_account_id}, "
                f"item_instance_id={item_instance_id}, event_type_id={event_type_id}"
            )
            return None

        trader_item_action_id = await conn.fetchval(
            """
            INSERT INTO trader_item_action (
                trader_platform_account_id,
                item_instance_id,
                event_type_id,
                action_time,
                price_amount,
                currency_id,
                confidence_score,
                source_snapshot_id
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING trader_item_action_id
            """,
            trader_platform_account_id,
            item_instance_id,
            event_type_id,
            action_time,
            cs_item.item_price,
            currency_id,
            1.0,  # confidence=1.0: мы точно видим его в stall
            source_snapshot_id
        )
        return trader_item_action_id


async def mark_missing_items_as_not_listed(pool, actual_asset_ids, cs_item: CSFloatItem) -> int:
    """
    После получения актуального stall продавца помечает предметы, которые исчезли из листинга,
    как not_listed и фиксирует событие.

    :param pool: asyncpg pool
    :param seller_id: steam_id продавца (str)
    :param actual_asset_ids: список asset_id предметов, которые сейчас видны в stall
    :return: количество помеченных предметов
    """
    try:
        cstraders = CSTraders(cs_item.listing)
        observed_at = datetime.now(timezone.utc)
        changed = 0


        async with pool.acquire() as conn:
            trader_platform_account_id = await cstraders.trader_platform_account_id(conn)
            event_type_id = await conn.fetchval(
                    "SELECT event_type_id FROM event_type WHERE code=$1",
                    "not_listed"
                )

            missing_rows = await conn.fetch(
                """
                SELECT
                    ii.item_instance_id,
                    ii.origin_asset_id,
                    ml.listed_price,
                    ml.currency_id
                FROM market_listing ml
                JOIN item_instance ii ON ii.item_instance_id = ml.item_instance_id
                WHERE ml.seller_account_id = $1
                AND ml.current_status = 'listed'
                AND ii.origin_asset_id IS NOT NULL
                """,
                trader_platform_account_id
            )
            for i, row in enumerate(missing_rows):
                try:
                    if str(row["origin_asset_id"]) in actual_asset_ids:
                        continue

                    await conn.execute(
                        """
                        UPDATE market_listing
                        SET current_status = 'not_listed',
                            last_seen_at   = $2
                        WHERE seller_account_id = $1
                          AND item_instance_id  = $3
                          AND current_status    = 'listed'
                        """,
                        trader_platform_account_id,
                        observed_at,
                        row["item_instance_id"],
                    )

                    await conn.execute(
                        """
                        INSERT INTO trader_item_action (
                            trader_platform_account_id,
                            item_instance_id,
                            event_type_id,
                            action_time,
                            price_amount,
                            currency_id,
                            confidence_score,
                            source_snapshot_id
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, NULL)
                        """,
                        trader_platform_account_id,
                        row["item_instance_id"],
                        event_type_id,
                        observed_at,
                        row["listed_price"],
                        row["currency_id"],
                        0.75,
                    )
                    changed += 1

                except Exception:
                    logger.exception(
                        "Ошибка на row[%s]: item_instance_id=%s origin_asset_id=%s",
                        i,
                        row.get("item_instance_id"),
                        row.get("origin_asset_id"),
                    )
                    raise

            return changed
    except Exception as e:
        logger.exception("Ошибка в mark_missing_items_as_not_listed: %s", e)
        raise
