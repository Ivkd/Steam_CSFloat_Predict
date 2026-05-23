from fastapi import FastAPI, Depends
from fastapi.responses import RedirectResponse
from .services import *
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CSFloat Parser API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return RedirectResponse(url="/docs")

@app.get("/weapon")
async def get(pool=Depends(CSFloatBD)):
    async with pool as db:
        return await count_weapons_in_db(db.pool)

# ─── Справочники ──────────────────────────────────────────────────────────────

@app.get("/stats/references", tags=["Справочники"])
async def get_references_stats(pool=Depends(CSFloatBD)):
    """Количество уникальных записей в справочных таблицах"""
    async with pool as db:
        return await get_references_count(db.pool)

# ─── Каталог предметов ────────────────────────────────────────────────────────

@app.get("/stats/catalog", tags=["Каталог"])
async def get_catalog_stats(pool=Depends(CSFloatBD)):
    """Количество уникальных предметов, скинов, типов"""
    async with pool as db:
        return await get_catalog_count(db.pool)

# ─── Рынок ────────────────────────────────────────────────────────────────────

@app.get("/stats/market", tags=["Рынок"])
async def get_market_stats(pool=Depends(CSFloatBD)):
    """Листинги, история цен, снимки рынка"""
    async with pool as db:
        return await get_market_count(db.pool)

# ─── Трейдеры ─────────────────────────────────────────────────────────────────

@app.get("/stats/traders", tags=["Трейдеры"])
async def get_traders_stats(pool=Depends(CSFloatBD)):
    """Трейдеры, снимки инвентарей, события"""
    async with pool as db:
        return await get_traders_count(db.pool)

# ─── Общая сводка + ML-готовность ────────────────────────────────────────────

@app.get("/stats", tags=["Сводка"])
async def get_full_stats(pool=Depends(CSFloatBD)):
    """Полная сводка по всей базе + готовность к запуску ML"""
    async with pool as db:
        return await get_full_stats_data(db.pool)

pp = FastAPI(title="CSFloat Parser API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return RedirectResponse(url="/docs")


@app.get("/weapon")
async def get(pool=Depends(CSFloatBD)):
    async with pool as db:
        return await count_weapons_in_db(db.pool)


# ─── Справочники ──────────────────────────────────────────────────────────────


@app.get("/stats/references", tags=["Справочники"])
async def get_references_stats(pool=Depends(CSFloatBD)):
    """Количество уникальных записей в справочных таблицах"""
    async with pool as db:
        return await get_references_count(db.pool)


# ─── Каталог предметов ────────────────────────────────────────────────────────


@app.get("/stats/catalog", tags=["Каталог"])
async def get_catalog_stats(pool=Depends(CSFloatBD)):
    """Количество уникальных предметов, скинов, типов"""
    async with pool as db:
        return await get_catalog_count(db.pool)


# ─── Рынок ────────────────────────────────────────────────────────────────────


@app.get("/stats/market", tags=["Рынок"])
async def get_market_stats(pool=Depends(CSFloatBD)):
    """Листинги, история цен, снимки рынка"""
    async with pool as db:
        return await get_market_count(db.pool)


# ─── Трейдеры ─────────────────────────────────────────────────────────────────


@app.get("/stats/traders", tags=["Трейдеры"])
async def get_traders_stats(pool=Depends(CSFloatBD)):
    """Трейдеры, снимки инвентарей, события"""
    async with pool as db:
        return await get_traders_count(db.pool)


# ─── Общая сводка + ML-готовность ────────────────────────────────────────────


@app.get("/stats", tags=["Сводка"])
async def get_full_stats(pool=Depends(CSFloatBD)):
    """Полная сводка по всей базе + готовность к запуску ML"""
    async with pool as db:
        return await get_full_stats_data(db.pool)

@app.get("/stats/prices", tags=["Рынок"])
async def get_price_coverage_stats(pool=Depends(CSFloatBD)):
    """Сколько предметов имеют известную цену — по CSFloat и Steam"""
    async with pool as db:
        return await get_price_coverage(db.pool)

# ─── ML ───────────────────────────────────────────────────────────────────────


@app.get("/ml/stats", tags=["ML"])
async def get_ml_stats(pool=Depends(CSFloatBD)):
    """Статистика БД + точность обученной модели"""
    async with pool as db:
        return await get_ml_stats_data(db.pool)


@app.post("/ml/train", tags=["ML"])
async def train_model(pool=Depends(CSFloatBD)):
    """Запустить обучение модели. Возвращает MAE, MAPE и путь к файлу."""
    async with pool as db:
        return await run_ml_training(db.pool)