"""
ml_stats.py — статистика БД и оценка ML-модели.

Всё через классы, никаких print/logger — данные возвращаются через dict.
"""
import os
from dataclasses import dataclass, field
from typing import Optional

import joblib
import numpy as np
import pandas as pd
import asyncpg
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    r2_score,
)


# ─────────────────────────────────────────────────────────────────────────────
# Датаклассы — структуры ответов
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DBStats:
    """Счётчики по таблицам."""
    unique_items: int
    unique_game_items: int
    unique_skins: int
    unique_weapons: int
    unique_stickers: int
    items_with_stickers: int
    total_listings: int
    active_listings: int
    sold_listings: int
    delisted_listings: int
    price_history_records: int
    unique_traders: int
    inventory_snapshots: int
    total_actions: int
    ml_ready_samples: int


@dataclass
class ReadinessResult:
    """Оценка готовности данных для обучения модели."""
    level: str
    progress_pct: float
    next_target: int
    recommendation: str
    sold_ratio_pct: float
    sold_ok: bool


@dataclass
class ModelMetrics:
    """Метрики обученной модели."""
    mae_usd: float
    mape_pct: float
    r2: float
    samples_evaluated: int
    quality_label: str


@dataclass
class MLStatsResult:
    """Итоговый результат — отдаётся в API."""
    db: DBStats
    readiness: ReadinessResult
    model: Optional[ModelMetrics]  # None если модель ещё не обучена


# ─────────────────────────────────────────────────────────────────────────────
# DBStatsCollector — собирает статистику из БД
# ─────────────────────────────────────────────────────────────────────────────

class DBStatsCollector:
    _SQL = """
    SELECT
        (SELECT COUNT(DISTINCT item_instance_id)
         FROM item_instance)                                             AS unique_items,

        (SELECT COUNT(DISTINCT game_item_id)
         FROM game_item)                                                 AS unique_game_items,

        (SELECT COUNT(DISTINCT market_listing_id)
         FROM market_listing)                                            AS total_listings,

        (SELECT COUNT(DISTINCT market_listing_id)
         FROM market_listing WHERE current_status = 'sold')             AS sold_listings,

        (SELECT COUNT(DISTINCT market_listing_id)
         FROM market_listing WHERE current_status = 'listed')           AS active_listings,

        (SELECT COUNT(DISTINCT market_listing_id)
         FROM market_listing WHERE current_status = 'not_listed')       AS delisted_listings,

        (SELECT COUNT(DISTINCT trader_account_id)
         FROM trader_account)                                            AS unique_traders,

        (SELECT COUNT(DISTINCT trader_inventory_snapshot_id)
         FROM trader_inventory_snapshot)                                 AS inventory_snapshots,

        (SELECT COUNT(DISTINCT trader_item_action_id)
         FROM trader_item_action)                                        AS total_actions,

        (SELECT COUNT(DISTINCT market_listing_price_history_id)
         FROM market_listing_price_history)                             AS price_history_records,

        (SELECT COUNT(DISTINCT skin_id) FROM skin)                      AS unique_skins,
        (SELECT COUNT(DISTINCT weapon_id) FROM weapon)                  AS unique_weapons,
        (SELECT COUNT(DISTINCT sticker_id) FROM sticker)                AS unique_stickers,

        (SELECT COUNT(DISTINCT item_instance_id)
         FROM item_instance_sticker)                                     AS items_with_stickers,

        (SELECT COUNT(DISTINCT ml.market_listing_id)
         FROM market_listing ml
         JOIN item_instance ii ON ii.item_instance_id = ml.item_instance_id
         WHERE ii.float_value IS NOT NULL
           AND ml.listed_price <= 500000
           AND ml.current_status IN ('listed', 'not_listed'))                 AS ml_ready_samples
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def collect(self) -> DBStats:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(self._SQL)
        return DBStats(**{k: (v or 0) for k, v in dict(row).items()})


# ─────────────────────────────────────────────────────────────────────────────
# ReadinessEvaluator — оценивает готовность данных
# ─────────────────────────────────────────────────────────────────────────────

class ReadinessEvaluator:
    _THRESHOLDS = [
        (0,        5_000,   "🔴 Недостаточно",  "Накопи минимум 5 000 образцов. Модель переобучится."),
        (5_000,    15_000,  "🟠 Начальный",     "Пробная модель даст ~30-40% MAPE."),
        (15_000,   50_000,  "🟡 Достаточно",    "Приемлемая точность ~15-25% MAPE."),
        (50_000,   150_000, "🟢 Хорошо",        "Хорошая точность ~8-15% MAPE. Можно в прод."),
        (150_000,  500_000, "🟢 Отлично",       "Высокая точность ~5-10% MAPE. Пробуй per-weapon модели."),
        (500_000,  10**9,   "🏆 Превосходно",   "Стройте ансамбль и временные ряды."),
    ]

    def evaluate(self, ml_ready: int, sold: int) -> ReadinessResult:
        level = ""
        recommendation = ""
        next_target = 5_000

        for lo, hi, lbl, rec in self._THRESHOLDS:
            if lo <= ml_ready < hi:
                level = lbl
                recommendation = rec
                next_target = hi
                break

        progress_pct = min(100.0, round(ml_ready / next_target * 100, 1))
        sold_ratio = round(sold / ml_ready * 100, 1) if ml_ready > 0 else 0.0

        return ReadinessResult(
            level=level,
            progress_pct=progress_pct,
            next_target=next_target,
            recommendation=recommendation,
            sold_ratio_pct=sold_ratio,
            sold_ok=sold >= 1_000,
        )


# ─────────────────────────────────────────────────────────────────────────────
# ModelEvaluator — считает метрики уже обученной модели
# ─────────────────────────────────────────────────────────────────────────────

class ModelEvaluator:
    _FEATURES = [
        "float_value", "float_squared", "paint_seed",
        "is_stattrak", "is_souvenir", "quality_id", "weapon_id", "skin_id",
        "sticker_count", "total_sticker_value", "avg_sticker_wear",
        "seller_trades", "days_on_market",
        "platform_code",
    ]

    _SQL = """
        SELECT
            ii.float_value,
            ii.float_value * ii.float_value         AS float_squared,
            COALESCE(ii.paint_seed, 0)               AS paint_seed,
            gi.is_stattrak::int,
            gi.is_souvenir::int,
            gi.quality_id,
            gi.weapon_id,
            gi.skin_id,
            COALESCE(stk.sticker_count, 0)          AS sticker_count,
            COALESCE(stk.total_sticker_value, 0)    AS total_sticker_value,
            COALESCE(stk.avg_sticker_wear, 1.0)     AS avg_sticker_wear,
            COALESCE(ta.total_trades, 0)             AS seller_trades,
            EXTRACT(EPOCH FROM (
                ml.last_seen_at - ml.first_seen_at
            )) / 86400.0                             AS days_on_market,
            p.code                                   AS platform_code,  -- ← новый
            ml.listed_price / 100.0                  AS target_price_usd
        FROM market_listing ml
        JOIN item_instance ii  ON ii.item_instance_id = ml.item_instance_id
        JOIN game_item gi      ON gi.game_item_id = ii.game_item_id
        JOIN trader_platform_account tpa
            ON tpa.trader_platform_account_id = ml.seller_account_id
        JOIN platform p
            ON p.platform_id = tpa.platform_id
        LEFT JOIN (
            SELECT
                iis.item_instance_id,
                COUNT(*)               AS sticker_count,
                SUM(st.price) / 100.0  AS total_sticker_value,
                AVG(iis.wear_value)    AS avg_sticker_wear
            FROM item_instance_sticker iis
            JOIN sticker st ON st.sticker_id = iis.sticker_id
            GROUP BY iis.item_instance_id
        ) stk ON stk.item_instance_id = ii.item_instance_id
        LEFT JOIN trader_account ta
            ON ta.trader_account_id = tpa.trader_account_id
        WHERE ml.current_status IN ('sold', 'listed')
        AND ii.float_value IS NOT NULL
        AND ml.listed_price > 0
        ORDER BY RANDOM()
        LIMIT 5000
    """

    def __init__(self, pool: asyncpg.Pool, model_path: str = "price_model.pkl"):
        self.pool = pool
        self.model_path = model_path

    def _quality_label(self, mape_pct: float) -> str:
        if mape_pct < 10:
            return "🏆 Отличная точность"
        if mape_pct < 20:
            return "🟢 Хорошая точность"
        if mape_pct < 35:
            return "🟡 Приемлемая точность"
        return "🔴 Нужно больше данных"

    async def evaluate(self) -> Optional[ModelMetrics]:
        if not os.path.exists(self.model_path):
            return None

        model = joblib.load(self.model_path)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(self._SQL)

        if len(rows) < 100:
            return None

        df = pd.DataFrame(rows, columns=rows[0].keys()).fillna(0)

        X = df[self._FEATURES]
        y_true = df["target_price_usd"].values  # ← БАГ ИСПРАВЛЕН: убрали expm1

        y_pred = np.expm1(model.predict(X))     # модель предсказывает log → обратно в $

        mae  = round(float(mean_absolute_error(y_true, y_pred)), 2)
        mape = round(float(mean_absolute_percentage_error(y_true, y_pred)) * 100, 1)
        r2   = round(float(r2_score(y_true, y_pred)), 3)

        return ModelMetrics(
            mae_usd=mae,
            mape_pct=mape,
            r2=r2,
            samples_evaluated=len(df),
            quality_label=self._quality_label(mape),
        )

# ─────────────────────────────────────────────────────────────────────────────
# MLStats — фасад, единая точка входа
# ─────────────────────────────────────────────────────────────────────────────

class MLStats:
    def __init__(self, pool: asyncpg.Pool, model_path: str = "price_model.pkl"):
        self._db_collector   = DBStatsCollector(pool)
        self._readiness_eval = ReadinessEvaluator()
        self._model_eval     = ModelEvaluator(pool, model_path)

    async def get(self) -> MLStatsResult:
        db_stats     = await self._db_collector.collect()
        readiness    = self._readiness_eval.evaluate(
            ml_ready=db_stats.ml_ready_samples,
            sold=db_stats.sold_listings,
        )
        model_metrics = await self._model_eval.evaluate()

        return MLStatsResult(
            db=db_stats,
            readiness=readiness,
            model=model_metrics,
        )