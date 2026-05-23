"""
ml_train.py — обучение моделей цены по оружиям.

Для каждого weapon_id + is_stattrak обучается отдельная LightGBM-модель.
Модели сохраняются в папку models/ как weapon_{id}_st{0|1}.pkl
"""
import os
from dataclasses import dataclass, field
from typing import Optional

import asyncpg
import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.compose import ColumnTransformer
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder


# ─────────────────────────────────────────────────────────────────────────────
# Константы групп оружий
# ─────────────────────────────────────────────────────────────────────────────

_KNIFE_IDS = {500,503,505,506,507,508,509,512,514,515,516,517,518,519,520,521,522,523,525,526}
_GLOVE_IDS = {4725,5027,5030,5031,5032,5033,5034,5035}

def get_weapon_group(weapon_id: int) -> str:
    if weapon_id in _KNIFE_IDS:
        return "Knife"
    if weapon_id in _GLOVE_IDS:
        return "Glove"
    return "Weapon"


# ─────────────────────────────────────────────────────────────────────────────
# Датаклассы
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WeaponTrainResult:
    weapon_id: int
    is_stattrak: int
    weapon_group: str
    mae_usd: float
    mape_pct: float
    train_samples: int
    test_samples: int
    model_path: str
    success: bool
    error: Optional[str] = None


@dataclass
class TrainResult:
    weapons_trained: int
    weapons_skipped: int
    results: list[WeaponTrainResult] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# DataLoader
# ─────────────────────────────────────────────────────────────────────────────

class DataLoader:
    _SQL = """
        SELECT
            ii.float_value::float,
            (ii.float_value * ii.float_value)::float    AS float_squared,
            COALESCE(ii.paint_seed, 0)                  AS paint_seed,
            gi.is_stattrak::int,
            gi.is_souvenir::int,
            gi.quality_id,
            gi.weapon_id,
            gi.skin_id,
            COALESCE(stk.sticker_count, 0)              AS sticker_count,
            COALESCE(stk.total_sticker_value, 0)::float AS total_sticker_value,
            COALESCE(stk.avg_sticker_wear, 1.0)::float  AS avg_sticker_wear,
            COALESCE(ta.total_trades, 0)                AS seller_trades,
            EXTRACT(EPOCH FROM (
                ml.last_seen_at - ml.first_seen_at
            ))::float / 86400.0                         AS days_on_market,
            p.code                                      AS platform_code,
            (ml.listed_price / 100.0)::float            AS target_price_usd
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
        WHERE ml.current_status IN ('listed', 'not_listed')
          AND ii.float_value IS NOT NULL
          AND ml.listed_price BETWEEN 100 AND 500000
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def load(self) -> pd.DataFrame:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(self._SQL)
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=rows[0].keys())
        df["weapon_group"] = df["weapon_id"].apply(get_weapon_group)
        return df


# ─────────────────────────────────────────────────────────────────────────────
# ModelTrainer
# ─────────────────────────────────────────────────────────────────────────────

class ModelTrainer:
    _NUM_FEATURES = [
        "float_value", "float_squared", "paint_seed",
        "is_souvenir",
        "sticker_count", "log_stickers", "avg_sticker_wear",
        "seller_trades", "days_on_market",
    ]
    _CAT_FEATURES = ["quality_id", "skin_id", "platform_code", "weapon_group"]

    # Минимум строк по группе
    _MIN_SAMPLES = {"Knife": 200, "Glove": 150, "Weapon": 300}

    def _build_pipeline(self) -> Pipeline:
        preprocessor = ColumnTransformer([
            ("cat", OrdinalEncoder(
                handle_unknown="use_encoded_value",
                unknown_value=-1
            ), self._CAT_FEATURES),
        ], remainder="passthrough")

        return Pipeline([
            ("prep", preprocessor),
            ("lgbm", LGBMRegressor(
                n_estimators=1000,
                learning_rate=0.05,
                max_depth=8,
                num_leaves=63,
                min_child_samples=20,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=0.1,
                reg_lambda=0.1,
                random_state=42,
                n_jobs=-1,
                verbose=-1,
            )),
        ])

    def train(self, df: pd.DataFrame, model_path: str) -> WeaponTrainResult:
        weapon_id   = int(df["weapon_id"].iloc[0])
        is_stattrak = int(df["is_stattrak"].iloc[0])
        weapon_group = df["weapon_group"].iloc[0]
        min_samples  = self._MIN_SAMPLES.get(weapon_group, 300)

        if len(df) < min_samples:
            return WeaponTrainResult(
                weapon_id=weapon_id, is_stattrak=is_stattrak,
                weapon_group=weapon_group,
                mae_usd=0, mape_pct=0,
                train_samples=0, test_samples=0,
                model_path=model_path, success=False,
                error=f"Мало данных: {len(df)} < {min_samples}"
            )

        df = df.copy()
        df["avg_sticker_wear"] = df["avg_sticker_wear"].fillna(1.0)
        df = df.fillna(0)

        # Фильтры цен
        df = df[df["target_price_usd"] >= 1.0]
        q99 = df["target_price_usd"].quantile(0.99)
        df = df[df["target_price_usd"] <= q99]
        df["days_on_market"] = df["days_on_market"].clip(lower=0)

        if len(df) < min_samples:
            return WeaponTrainResult(
                weapon_id=weapon_id, is_stattrak=is_stattrak,
                weapon_group=weapon_group,
                mae_usd=0, mape_pct=0,
                train_samples=0, test_samples=0,
                model_path=model_path, success=False,
                error=f"Мало данных после фильтрации: {len(df)}"
            )

        df["log_stickers"] = np.log1p(df["total_sticker_value"].astype(float))
        df["log_price"]    = np.log1p(df["target_price_usd"].astype(float))

        X = df[self._NUM_FEATURES + self._CAT_FEATURES]
        y = df["log_price"]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        model = self._build_pipeline()
        model.fit(X_train, y_train)

        y_pred = np.expm1(model.predict(X_test))
        y_true = np.expm1(y_test.values)

        # MAPE считаем только на ценах >= $1
        mask = y_true >= 1.0
        mae  = round(float(mean_absolute_error(y_true[mask], y_pred[mask])), 2)
        mape = round(float(mean_absolute_percentage_error(y_true[mask], y_pred[mask])) * 100, 1)

        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(model, model_path)

        return WeaponTrainResult(
            weapon_id=weapon_id, is_stattrak=is_stattrak,
            weapon_group=weapon_group,
            mae_usd=mae, mape_pct=mape,
            train_samples=len(X_train), test_samples=len(X_test),
            model_path=model_path, success=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# MLTrainer — фасад
# ─────────────────────────────────────────────────────────────────────────────

class MLTrainer:
    def __init__(self, pool: asyncpg.Pool, models_dir: str = "/server/models"):
        self._loader     = DataLoader(pool)
        self._trainer    = ModelTrainer()
        self._models_dir = models_dir

    def model_path(self, weapon_id: int, is_stattrak: int) -> str:
        return os.path.join(self._models_dir, f"weapon_{weapon_id}_st{is_stattrak}.pkl")

    async def run(self) -> TrainResult:
        df = await self._loader.load()

        if df.empty:
            return TrainResult(weapons_trained=0, weapons_skipped=0,
                               success=False, error="Нет данных в БД")

        trained, skipped = 0, 0
        results = []

        for (weapon_id, is_stattrak), group_df in df.groupby(["weapon_id", "is_stattrak"]):
            path = self.model_path(int(weapon_id), int(is_stattrak))
            result = self._trainer.train(group_df, path)
            results.append(result)
            if result.success:
                trained += 1
            else:
                skipped += 1

        return TrainResult(weapons_trained=trained, weapons_skipped=skipped, results=results)   