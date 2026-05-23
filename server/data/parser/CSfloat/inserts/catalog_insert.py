from .....core.logger import get_logger
from server.data.parser.CSfloat.inserts.utilits.types import CSFloatItem, CSSelects

logger = get_logger("parserFloat")

PLATFORM_CODE = "csfloat"


async def insert_game_item_from_response(pool, cs_item: CSFloatItem) -> int | None:
    try:
        async with pool.acquire() as conn:
            csselects = CSSelects(cs_item.listing)
            w_id = await csselects.weapon_id(conn)
            s_id = await csselects.skin_id(conn)
            q_id = await csselects.quality_id(conn)

            if w_id is None or s_id is None or q_id is None:
                logger.warning(
                    "Пропуск: не найден weapon_id(%s) skin_id(%s) quality_id(%s) для %s",
                    w_id, s_id, q_id, cs_item.item_name
                )
                return None

            game_item_id = await conn.fetchval("""
                INSERT INTO game_item (weapon_id, skin_id, quality_id, is_stattrak, is_souvenir)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (weapon_id, skin_id, quality_id, is_stattrak, is_souvenir)
                DO UPDATE SET weapon_id = EXCLUDED.weapon_id
                RETURNING game_item_id
            """, w_id, s_id, q_id, csselects.is_stattrak, csselects.is_souvenir)

            return game_item_id

    except Exception as e:
        logger.exception("Ошибка при вставке game_item: %s", e)
        raise


async def insert_item_instance_from_response(pool, cs_item: CSFloatItem) -> None:
    try:
        async with pool.acquire() as conn:
            csselects = CSSelects(cs_item.listing)
            game_item_id = await csselects.get_game_item_id(conn)
            # ИСПРАВЛЕНО: "csfoat" -> "csfloat"
            platform_id = await csselects.platform_id(conn, PLATFORM_CODE)

            await conn.execute("""
                INSERT INTO item_instance (
                    game_item_id, 
                    origin_platform_id,
                    origin_asset_id,
                    float_value,
                    paint_seed,
                    inspect_link,
                    first_seen_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (origin_platform_id, origin_asset_id)
                DO NOTHING
            """,
            game_item_id,
            platform_id,
            cs_item.asset_id,
            cs_item.float_value,
            cs_item.paint_seed,
            cs_item.inspect_link,
            cs_item.created_at
            )
    except Exception as e:
        logger.error(f"Ошибка при вставке item_instance: {e}")


async def insert_container_item(pool, cs_item: CSFloatItem) -> None:
    try:
        async with pool.acquire() as conn:
            csselects = CSSelects(cs_item.listing)
            container_id = await csselects.container_id(conn)
            if container_id is None:
                return

            await conn.execute("""
                INSERT INTO container_item (container_id, item_id, is_active)
                VALUES ($1, $2, $3)
                ON CONFLICT (container_id, item_id, is_active)
                DO NOTHING
            """,
            int(container_id),
            int(cs_item.id),
            True
            )
    except Exception as e:
        logger.error(f"Ошибка при вставке container_item: {e}")
