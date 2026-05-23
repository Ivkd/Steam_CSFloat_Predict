from .....core.logger import get_logger
from server.data.parser.CSfloat.inserts.utilits.types import CSFloatItem, CSSelects, CSTraders

logger = get_logger("parserFloat")

PLATFORM_CODE = "csfloat"


async def market_listing_insert(pool, cs_item: CSFloatItem):
    async with pool.acquire() as conn:
        csselect = CSSelects(cs_item.listing)
        cstraders = CSTraders(cs_item.listing)

        # ИСПРАВЛЕНО: "csfoat" -> PLATFORM_CODE
        platform_id = await csselect.platform_id(conn, PLATFORM_CODE)
        currency_id = await csselect.currency_id(conn)
        item_instance_id = await csselect.get_item_instance_id(conn)
        seller_account_id = await cstraders.trader_platform_account_id(conn)

        await conn.execute(
            """
            INSERT INTO market_listing (
                platform_id,
                external_listing_id,
                item_instance_id,
                seller_account_id,
                currency_id,
                listed_price,
                listed_at,
                first_seen_at,
                last_seen_at,
                current_status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $7, $7, $8)
            ON CONFLICT (platform_id, external_listing_id)
            DO UPDATE
            SET
                listed_price   = EXCLUDED.listed_price,
                last_seen_at   = EXCLUDED.last_seen_at,
                current_status = EXCLUDED.current_status
            """,
            platform_id,
            cs_item.id,
            item_instance_id,
            seller_account_id,
            currency_id,
            cs_item.item_price,
            cs_item.created_at,
            cs_item.state,
        )


async def market_listing_price_history_insert(pool, cs_item: CSFloatItem):
    async with pool.acquire() as conn:
        csselect = CSSelects(cs_item.listing)
        currency_id = await csselect.currency_id(conn)
        market_listing_id = await csselect.market_listing_id(conn, PLATFORM_CODE)

        if market_listing_id is None:
            logger.warning(f"market_listing не найден для listing_id={cs_item.id}")
            return

        await conn.execute(
            """
            INSERT INTO market_listing_price_history (
                market_listing_id,
                observed_at,
                price_amount,
                currency_id
            )
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (market_listing_id, observed_at)
            DO NOTHING
            """,
            market_listing_id,
            cs_item.created_at,
            cs_item.item_price,
            currency_id
        )


async def market_listing_status_history_insert(pool, cs_item: CSFloatItem):
    async with pool.acquire() as conn:
        csselect = CSSelects(cs_item.listing)
        market_listing_id = await csselect.market_listing_id(conn, PLATFORM_CODE)
        event_type_id = await csselect.event_type_id(conn)

        if market_listing_id is None:
            return

        await conn.execute(
            """
            INSERT INTO market_listing_status_history (
                market_listing_id,
                event_type_id,
                event_time,
                old_status,
                new_status
            )
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (market_listing_id, event_time, event_type_id)
            DO NOTHING
            """,
            market_listing_id,
            event_type_id,
            cs_item.created_at,
            None,  # TODO: получить предыдущий статус из БД при необходимости
            cs_item.state
        )


async def market_observation_snapshot_insert(pool, cs_item: CSFloatItem):
    async with pool.acquire() as conn:
        csselect = CSSelects(cs_item.listing)
        market_listing_id = await csselect.market_listing_id(conn, PLATFORM_CODE)

        if market_listing_id is None:
            return

        is_visible = cs_item.state == "listed"

        await conn.execute(
            """
            INSERT INTO market_observation_snapshot (
                market_listing_id,
                observed_at,
                position_in_search,
                watchers_count,
                min_offer_price,
                scm_reference_price,
                scm_reference_volume,
                is_visible
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (market_listing_id, observed_at)
            DO UPDATE
            SET
                position_in_search   = EXCLUDED.position_in_search,
                watchers_count       = EXCLUDED.watchers_count,
                min_offer_price      = EXCLUDED.min_offer_price,
                scm_reference_price  = EXCLUDED.scm_reference_price,
                scm_reference_volume = EXCLUDED.scm_reference_volume,
                is_visible           = EXCLUDED.is_visible
            """,
            market_listing_id,
            cs_item.created_at,
            None,  # position_in_search — недоступно из одиночного листинга
            None,  # watchers_count — доступно в /listings/<id>, добавить cs_item.watchers если нужно
            cs_item.item_price,
            None,  # scm_reference_price — TODO
            None,  # scm_reference_volume — TODO
            is_visible
        )
