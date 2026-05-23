import asyncio
import asyncpg
import os
from dotenv import load_dotenv
import logging

from server.core.logger import get_logger
from server.data.parser.CSfloat.parserFloat import (
    CSFloatBD,
    activate_primary_insert,
    started,
    check_data_seller,
)
from server.data.parser.CSfloat.checker import run_listing_checker
from server.data.parser.Steam.parserSteam import ( 
    check_steam_inventories,
    update_steam_prices,
)

load_dotenv()
logger = get_logger("main")

logging.basicConfig(level=logging.INFO)
logging.getLogger("selenium").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("selenium.webdriver.remote.remote_connection").setLevel(logging.WARNING)
logging.getLogger("selenium.webdriver.common.service").setLevel(logging.WARNING)
logging.getLogger("selenium.webdriver.common.driver_finder").setLevel(logging.WARNING)


# ─── Интервалы ───────────────────────────────
INTERVAL_MARKET      = 15 * 60   # каждые 15 мин
INTERVAL_SELLERS     = 20 * 60   # каждые 20 мин
INTERVAL_STEAM_INV   = 20 * 60   # каждые 60 мин — инвентари Steam
INTERVAL_CHECKER     = 30 * 60   # каждые 30 мин
INTERVAL_STEAM_PRICE = 30 * 60   # каждые 90 мин — цены Steam (не спамим API)


async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(
        database=os.getenv("POSTGRES_DB"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        password=os.getenv("POSTGRES_PASSWORD"),
        user=os.getenv("POSTGRES_USER"),
        min_size=5,
        max_size=20,
    )


# ─── Task A: общий рынок CSFloat ─────────────

async def task_market(pool: asyncpg.Pool) -> None:
    while True:
        try:
            logger.info("▶ started(): парсинг общего рынка...")
            await started()
        except Exception as e:
            logger.error(f"Task A ошибка: {e}")
        logger.info(f"Task A: следующий запуск через {INTERVAL_MARKET // 60} мин")
        await asyncio.sleep(INTERVAL_MARKET)


# ─── Task B: stall продавцов CSFloat ─────────

async def task_sellers(pool: asyncpg.Pool) -> None:
    await asyncio.sleep(120)
    while True:
        try:
            logger.info("▶ check_data_seller(): обход stall трейдеров...")
            await check_data_seller()
        except Exception as e:
            logger.error(f"Task B ошибка: {e}")
        logger.info(f"Task B: следующий запуск через {INTERVAL_SELLERS // 60} мин")
        await asyncio.sleep(INTERVAL_SELLERS)


# ─── Task C: проверка статуса листингов ──────

async def task_checker(pool: asyncpg.Pool) -> None:
    await asyncio.sleep(240)
    while True:
        try:
            logger.info("▶ run_listing_checker(): проверка статуса листингов...")
            await run_listing_checker(pool)
        except Exception as e:
            logger.error(f"Task C ошибка: {e}")
        logger.info(f"Task C: следующий запуск через {INTERVAL_CHECKER // 60} мин")
        await asyncio.sleep(INTERVAL_CHECKER)


# ─── Task D: снапшоты инвентарей Steam ───────

async def task_steam_inventories(pool: asyncpg.Pool) -> None:
    # Ждём 4.1 мин — пусть сначала CSFloat парсер заполнит трейдеров в БД
    await asyncio.sleep(60)
    while True:
        try:
            logger.info("▶ check_steam_inventories(): снапшоты инвентарей...")
            await check_steam_inventories(pool)
        except Exception as e:
            logger.error(f"Task D ошибка: {e}")
        logger.info(f"Task D: следующий запуск через {INTERVAL_STEAM_INV // 60} мин")
        await asyncio.sleep(INTERVAL_STEAM_INV)


# ─── Task E: цены Steam ───────────────────────

async def task_steam_prices(pool: asyncpg.Pool) -> None:
    # Ждём 5 мин — пусть game_item заполнятся через CSFloat
    await asyncio.sleep(60)
    while True:
        try:
            logger.info("▶ update_steam_prices(): обновление цен Steam...")
            await update_steam_prices(pool)
        except Exception as e:
            logger.error(f"Task E ошибка: {e}")
        logger.info(f"Task E: следующий запуск через {INTERVAL_STEAM_PRICE // 60} мин")
        await asyncio.sleep(INTERVAL_STEAM_PRICE)


# ─── Фаза 1: справочники ─────────────────────

async def bootstrap(pool: asyncpg.Pool) -> None:
    try:
        await activate_primary_insert(pool)
        logger.info("═══ Справочники заполнены ═══")
    except Exception as e:
        logger.error(f"Ошибка при заполнении справочников: {e}")
        raise


# ─── Главный запуск ──────────────────────────

async def main() -> None:
    pool = await create_pool()

    try:
        # await bootstrap(pool)
        logger.info("stop machine")
        # await asyncio.gather(
        #     task_market(pool),              # Task A — рынок CSFloat
        #     task_sellers(pool),             # Task B — продавцы CSFloat
        #     task_checker(pool),             # Task C — статус предметов
        #     task_steam_inventories(pool),   # Task D — инвентари Steam  ← новый
        #     task_steam_prices(pool),        # Task E — цены Steam        ← новый
        # )

    except KeyboardInterrupt:
        logger.info("Остановка по Ctrl+C")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise
    finally:
        await pool.close()
        logger.info("Пул закрыт, выход.")


if __name__ == "__main__":
    asyncio.run(main())