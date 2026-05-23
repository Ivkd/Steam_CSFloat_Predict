import asyncpg
import os
from dotenv import load_dotenv
from ..core.logger import get_logger

from ..servises.ml_stats import MLStats
from ..servises.ml_train import MLTrainer

logger = get_logger("services")

dotenv_path = os.path.join(os.path.dirname(__file__), '../../.env')
load_dotenv(dotenv_path)


class CSFloatBD:
    def __init__(self):
        self.pool = None

    async def __aenter__(self):
        try:
            logger.info("Создание пула базы данных...")
            self.pool = await asyncpg.create_pool(
                database=os.getenv("POSTGRES_DB"),
                host=os.getenv("POSTGRES_HOST"),
                port=os.getenv("POSTGRES_PORT"),
                password=os.getenv("POSTGRES_PASSWORD"),
                user=os.getenv("POSTGRES_USER"),
                min_size=5,
                max_size=30,
            )
            return self
        except Exception as e:
            logger.error(f"Сбой при создании пула базы данных: {e}")
            raise e

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.pool:
            await self.pool.close()


# ─── Справочники ──────────────────────────────────────────────────────────────

async def get_references_count(pool) -> dict:
    async with pool.acquire() as c:
        return {
            "weapons":      await c.fetchval("SELECT COUNT(*) FROM weapon"),
            "skins":        await c.fetchval("SELECT COUNT(*) FROM skin"),
            "stickers":     await c.fetchval("SELECT COUNT(*) FROM sticker"),
            "qualities":    await c.fetchval("SELECT COUNT(*) FROM item_quality"),
            "event_types":  await c.fetchval("SELECT COUNT(*) FROM event_type"),
            "platforms":    await c.fetchval("SELECT COUNT(*) FROM platform"),
            "currencies":   await c.fetchval("SELECT COUNT(*) FROM currency"),
            "containers":   await c.fetchval("SELECT COUNT(*) FROM container"),
        }


# ─── Каталог ──────────────────────────────────────────────────────────────────

async def get_catalog_count(pool) -> dict:
    async with pool.acquire() as c:
        return {
            "game_items":           await c.fetchval("SELECT COUNT(DISTINCT game_item_id) FROM game_item"),
            "item_instances":       await c.fetchval("SELECT COUNT(DISTINCT item_instance_id) FROM item_instance"),
            "items_with_float":     await c.fetchval("SELECT COUNT(*) FROM item_instance WHERE float_value IS NOT NULL"),
            "items_with_stickers":  await c.fetchval("SELECT COUNT(DISTINCT item_instance_id) FROM item_instance_sticker"),
            "stattrak_items":       await c.fetchval("SELECT COUNT(*) FROM game_item WHERE is_stattrak = TRUE"),
            "souvenir_items":       await c.fetchval("SELECT COUNT(*) FROM game_item WHERE is_souvenir = TRUE"),
        }


# ─── Рынок ────────────────────────────────────────────────────────────────────

async def get_market_count(pool) -> dict:
    async with pool.acquire() as c:
        return {
            "listings": {
                "total":       await c.fetchval("SELECT COUNT(*) FROM market_listing"),
                "active":      await c.fetchval("SELECT COUNT(*) FROM market_listing WHERE current_status = 'listed'"),
                "sold":        await c.fetchval("SELECT COUNT(*) FROM market_listing WHERE current_status = 'sold'"),
                "not_listed":  await c.fetchval("SELECT COUNT(*) FROM market_listing WHERE current_status = 'not_listed'"),
            },
            "price_history_records": await c.fetchval("SELECT COUNT(*) FROM market_listing_price_history"),
            "market_snapshots":      await c.fetchval("SELECT COUNT(*) FROM item_market_snapshot"),
            "avg_price_usd":         await c.fetchval(
                "SELECT ROUND(AVG(listed_price) / 100.0, 2) FROM market_listing WHERE listed_price > 0"
            ),
            "max_price_usd":         await c.fetchval(
                "SELECT ROUND(MAX(listed_price) / 100.0, 2) FROM market_listing WHERE listed_price > 0"
            ),
        }


# ─── Трейдеры ─────────────────────────────────────────────────────────────────

async def get_traders_count(pool) -> dict:
    async with pool.acquire() as c:
        return {
            "unique_traders":           await c.fetchval("SELECT COUNT(DISTINCT trader_account_id) FROM trader_account"),
            "platform_accounts":        await c.fetchval("SELECT COUNT(*) FROM trader_platform_account"),
            "inventory_snapshots":      await c.fetchval("SELECT COUNT(*) FROM trader_inventory_snapshot"),
            "inventory_item_snapshots": await c.fetchval("SELECT COUNT(*) FROM trader_inventory_item_snapshot"),
            "actions": {
                "total":       await c.fetchval("SELECT COUNT(*) FROM trader_item_action"),
                "listed":      await c.fetchval(
                    "SELECT COUNT(*) FROM trader_item_action ta "
                    "JOIN event_type et ON et.event_type_id = ta.event_type_id "
                    "WHERE et.code = 'listed'"
                ),
                "sold":        await c.fetchval(
                    "SELECT COUNT(*) FROM trader_item_action ta "
                    "JOIN event_type et ON et.event_type_id = ta.event_type_id "
                    "WHERE et.code = 'sold'"
                ),
                "not_listed":  await c.fetchval(
                    "SELECT COUNT(*) FROM trader_item_action ta "
                    "JOIN event_type et ON et.event_type_id = ta.event_type_id "
                    "WHERE et.code = 'not_listed'"
                ),
            },
        }


# ─── Полная сводка + ML-готовность ───────────────────────────────────────────

_ML_THRESHOLDS = [
    (0,       5_000,   "🔴 Недостаточно",  "Жди минимум 5 000 образцов"),
    (5_000,   15_000,  "🟠 Начальный",     "Можно попробовать, точность ~30-40% MAPE"),
    (15_000,  50_000,  "🟡 Достаточно",    "Приемлемо (~15-25% MAPE), можно запускать"),
    (50_000,  150_000, "🟢 Хорошо",        "Хорошая точность (~8-15% MAPE)"),
    (150_000, 500_000, "🟢 Отлично",       "Высокая точность (~5-10% MAPE)"),
    (500_000, 10**9,   "🏆 Превосходно",   "Строй ансамбль и per-weapon модели"),
]


async def get_full_stats_data(pool) -> dict:
    async with pool.acquire() as c:
        ml_ready = await c.fetchval(
            """
            SELECT COUNT(DISTINCT ml.market_listing_id)
            FROM market_listing ml
            JOIN item_instance ii ON ii.item_instance_id = ml.item_instance_id
            WHERE ii.float_value IS NOT NULL
              AND ml.listed_price > 0
              AND ml.current_status IN ('sold', 'listed')
            """
        ) or 0

        sold = await c.fetchval(
            "SELECT COUNT(*) FROM market_listing WHERE current_status = 'sold'"
        ) or 0

        total_listings = await c.fetchval("SELECT COUNT(*) FROM market_listing") or 0
        unique_traders = await c.fetchval("SELECT COUNT(*) FROM trader_platform_account") or 0,
        unique_items   = await c.fetchval("SELECT COUNT(DISTINCT item_instance_id) FROM item_instance") or 0
        total_actions  = await c.fetchval("SELECT COUNT(*) FROM trader_item_action") or 0

    # ML-готовность
    level, recommendation, next_target = "🔴 Недостаточно", "Жди минимум 5 000 образцов", 5_000
    for lo, hi, lbl, rec in _ML_THRESHOLDS:
        if lo <= ml_ready < hi:
            level, recommendation, next_target = lbl, rec, hi
            break

    progress_pct  = round(min(100.0, ml_ready / next_target * 100), 1)
    sold_ratio    = round(sold / ml_ready * 100, 1) if ml_ready > 0 else 0.0
    can_start_ml  = ml_ready >= 15_000

    return {
        "summary": {
            "unique_items":    unique_items,
            "total_listings":  total_listings,
            "sold_listings":   sold,
            "unique_traders":  unique_traders,
            "total_actions":   total_actions,
        },
        "ml_readiness": {
            "ml_ready_samples":     ml_ready,
            "can_start_ml":         can_start_ml,         # True/False — можно ли уже запускать
            "level":                level,
            "progress_to_next_pct": progress_pct,
            "next_target":          next_target,
            "sold_ratio_pct":       sold_ratio,
            "recommendation":       recommendation,
        },
    }

async def get_ml_stats_data(pool) -> dict:
    stats = MLStats(pool)
    result = await stats.get()

    return {
        "db": {
            "unique_items":          result.db.unique_items,
            "unique_game_items":     result.db.unique_game_items,
            "unique_skins":          result.db.unique_skins,
            "unique_weapons":        result.db.unique_weapons,
            "unique_stickers":       result.db.unique_stickers,
            "items_with_stickers":   result.db.items_with_stickers,
            "total_listings":        result.db.total_listings,
            "active_listings":       result.db.active_listings,
            "sold_listings":         result.db.sold_listings,
            "delisted_listings":     result.db.delisted_listings,
            "price_history_records": result.db.price_history_records,
            "unique_traders":        result.db.unique_traders,
            "inventory_snapshots":   result.db.inventory_snapshots,
            "total_actions":         result.db.total_actions,
            "ml_ready_samples":      result.db.ml_ready_samples,
        },
        "ml_readiness": {
            "level":                result.readiness.level,
            "progress_pct":         result.readiness.progress_pct,
            "next_target":          result.readiness.next_target,
            "recommendation":       result.readiness.recommendation,
            "sold_ratio_pct":       result.readiness.sold_ratio_pct,
            "sold_ok":              result.readiness.sold_ok,
            "can_start_ml":         result.db.ml_ready_samples >= 15_000,
        },
        "model": {
            "trained":         result.model is not None,
            "mae_usd":         result.model.mae_usd         if result.model else None,
            "mape_pct":        result.model.mape_pct        if result.model else None,
            "r2":              result.model.r2              if result.model else None,
            "samples_eval":    result.model.samples_evaluated if result.model else None,
            "quality_label":   result.model.quality_label   if result.model else None,
        },
    }


async def run_ml_training(pool) -> dict:
    trainer = MLTrainer(pool)
    result = await trainer.run()

    if not result.success:
        return {
            "success": False,
            "error": result.error,
        }

    return {
        "success":         result.success,
        "error":           result.error,
        "weapons_trained": result.weapons_trained,
        "weapons_skipped": result.weapons_skipped,
        "results": [
            {
                "weapon_id":     r.weapon_id,
                "mae_usd":       r.mae_usd,
                "mape_pct":      r.mape_pct,
                "train_samples": r.train_samples,
                "test_samples":  r.test_samples,
                "model_path":    r.model_path,
                "success":       r.success,
                "error":         r.error,
            }
            for r in result.results
        ],
    }

# ─── Старые функции (оставлены для совместимости) ─────────────────────────────

async def count_weapons_in_db(pool):
    async with pool.acquire() as c:
        return await c.fetchval("SELECT COUNT(*) FROM weapon")

async def count_stickers_in_db(pool):
    async with pool.acquire() as c:
        return await c.fetchval("SELECT COUNT(*) FROM sticker")

async def count_skin_in_db(pool):
    async with pool.acquire() as c:
        return await c.fetchval("SELECT COUNT(*) FROM skin")
    

async def get_price_coverage(pool) -> dict:
    async with pool.acquire() as c:

        # ID платформы csfloat
        csfloat_platform_id = await c.fetchval(
            "SELECT platform_id FROM platform WHERE code = 'csfloat'"
        )

        both_platforms = await c.fetchval("""
            SELECT COUNT(DISTINCT gi.game_item_id)
            FROM game_item gi
            JOIN item_instance ii   ON ii.game_item_id   = gi.game_item_id
            JOIN market_listing ml  ON ml.item_instance_id = ii.item_instance_id
            WHERE ml.platform_id  = $1
            AND ml.listed_price > 0
            AND EXISTS (
                SELECT 1 FROM steam_price_history sph
                WHERE sph.game_item_id = gi.game_item_id
            )
        """, 
        csfloat_platform_id, 
        timeout=15  # максимум 15 секунд
        ) or 0
        # CSFloat — всего уникальных предметов на платформе
        csfloat_total = await c.fetchval("""
            SELECT COUNT(DISTINCT item_instance_id)
            FROM market_listing
            WHERE platform_id = $1
        """, csfloat_platform_id) or 0

        # CSFloat — предметов у которых есть цена
        csfloat_with_price = await c.fetchval("""
            SELECT COUNT(DISTINCT item_instance_id)
            FROM market_listing
            WHERE platform_id = $1
              AND listed_price > 0
        """, csfloat_platform_id) or 0

        # Steam — сколько уникальных game_item в системе
        total_game_items = await c.fetchval(
            "SELECT COUNT(DISTINCT game_item_id) FROM game_item"
        ) or 0

        # Steam — сколько game_item покрыто историей цен
        steam_with_price = await c.fetchval("""
            SELECT COUNT(DISTINCT game_item_id)
            FROM steam_price_history
        """) or 0

        # Steam — предметов в инвентарях трейдеров (через platform_id на item_instance)
        steam_platform_id = await c.fetchval(
            "SELECT platform_id FROM platform WHERE code = 'steam'"
        )

        steam_total = await c.fetchval("""
            SELECT COUNT(DISTINCT item_instance_id)
            FROM item_instance
            WHERE origin_platform_id = $1
        """, steam_platform_id) or 0

        last_steam_update = await c.fetchval(
            "SELECT MAX(recorded_at) FROM steam_price_history"
        )

        last_csfloat_update = await c.fetchval("""
            SELECT MAX(last_seen_at)
            FROM market_listing
            WHERE platform_id = $1
        """, csfloat_platform_id)

    return {
        "csfloat": {
            "items_with_price": int(csfloat_with_price),
            "total_items":      int(csfloat_total),
            "coverage_pct":     round(csfloat_with_price / csfloat_total * 100, 1) if csfloat_total > 0 else 0.0,
         "last_updated":      last_csfloat_update.isoformat() if last_csfloat_update else None,  # ← добавили
        },
        "steam": {
            "game_items_with_history":   int(steam_with_price),
            "total_game_items":          int(total_game_items),
            "count_item_have_steam_price": int(steam_with_price),
            "steam_total":               int(steam_total),
            "coverage_pct":              round(steam_with_price / total_game_items * 100, 1) if total_game_items > 0 else 0.0,
            "last_updated":              last_steam_update.isoformat() if last_steam_update else None,
        },
        "cross_platform": {
            "game_items_on_both":  int(both_platforms),
            "total_game_items":    int(total_game_items),
            "coverage_pct":        round(both_platforms / total_game_items * 100, 1) if total_game_items > 0 else 0.0,
        },
    }