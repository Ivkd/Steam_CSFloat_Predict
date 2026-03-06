import asyncio
from pathlib import Path
import asyncpg

from APIs.help_func.trade_shop_cls import CSFloatAsync, PgAsync
from APIs.help_func.log import Helpfull

!!!!!!!!! ПЕРЕКИНУТЬ ЭТО ВСЕ В КЛАСС И СДЕЛАТЬ НОРМЛЬНЫЙ КЛАСС ПО SOLID ТАК ЖЕ ДОБАВИТЬ К НЕМУ НОРМАЛЬНЫЙ SAVE_CHACHE БУДЕТ ПРОЩЕ !!!!!!!!!!

URL_ = "https://csfloat.com/api/v1/listings"
URL_CASE_ = "https://csfloat.com/api/v1/schema/browse?type=containers"
SQL_ = Path(__file__).resolve().parent / "csfloat_db.sql"
LOGS_ = Helpfull()

@LOGS_.log_
# @LOGS_.count_calls
async def get_item_bd_csfloat(qwery:str, *args) -> list[asyncpg.Record]:
    async with PgAsync(sql_path=SQL_, dbname="CSfloat_items") as pg:
        return await pg.fetch_all(qwery, *args)

@LOGS_.log_
@LOGS_.sey_time
async def get_case_csfloat():
    csf = CSFloatAsync(url=URL_CASE_)
    cases, cod = await csf.get_data_containers()

    query = f"""
    INSERT INTO containers (
        market_hash_name,
        price,
        updated_at
    )
    VALUES ($1, $2, NOW())
    ON CONFLICT (market_hash_name) DO UPDATE SET
        price = EXCLUDED.price,
        updated_at = NOW()
    """

    params_list = [
        (
            case.get("market_hash_name"),
            case.get("price"),
        )
        for case in cases
    ]
    
    async with PgAsync(sql_path=SQL_, dbname="CSfloat_items") as db:
        await db.save_many(query, params_list)

@LOGS_.log_
@LOGS_.sey_time
async def get_items_csfloat(
    def_index_:int,
    sort_by_:str = "lowest_price", 
    min_price_:int = None,
    max_price_:int = None
    ) -> None:

    csf = CSFloatAsync(url=URL_)

    items_data, status_cod = await csf.get_data_skins(
        min_price=min_price_,
        max_price=max_price_,
        sort_by=sort_by_,
        category=1,
        def_index=def_index_
    )

    query = f"""
    INSERT INTO skins_items (
        item_id,
        type,
        price,
        float_value,
        icon_url,
        market_hash_name,
        item_name,
        wear_name,
        paint_index,
        updated_at
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
    ON CONFLICT (item_id) DO UPDATE SET
        type = EXCLUDED.type,
        price = EXCLUDED.price,
        float_value = EXCLUDED.float_value,
        icon_url = EXCLUDED.icon_url,
        market_hash_name = EXCLUDED.market_hash_name,
        item_name = EXCLUDED.item_name,
        wear_name = EXCLUDED.wear_name,
        paint_index = EXCLUDED.paint_index,
        updated_at = NOW()
    """

    params_list = [
        (
            int(item["id"]),
            item.get("type"),
            item.get("price"),
            item.get("float_value"),
            item.get("icon_url"),
            item.get("market_hash_name"),
            item.get("item_name"),
            item.get("wear_name"),
            item.get("paint_index"),
        )
        for item in items_data
    ]

    async with PgAsync(sql_path=SQL_, dbname="CSfloat_items") as db:
        await db.save_many(query, params_list)
    
    if status_cod == 429:
        LOGS_.log.info(f"I wil sleep 1h -- {status_cod}")
        await asyncio.sleep(600)
        return await get_items_csfloat(        
            min_price=min_price_,
            max_price=max_price_,
            sort_by=sort_by_,
            category=1,
            def_index=def_index_,
        )


@LOGS_.count_calls
async def get_avg_price_similar_items():
    qwery = """
    SELECT * FROM avg_price_similar_items
    """
    async with PgAsync(sql_path=SQL_, dbname="CSfloat_items") as pg:
        return await pg.fetch_all(qwery)

@LOGS_.log_
# @LOGS_.count_calls
async def get_similar(id):
    url = f"https://csfloat.com/api/v1/listings/{id}/similar"
    csf = CSFloatAsync(url=url)

    items, cod = await csf.get_similar_items()
    if cod == 429: # повторение если кинет в бан 429
        await get_similar(id)

    query = """
        INSERT INTO similar_items(
            id,
            market_hash_name,
            price,
            type
        )  
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (id) DO UPDATE SET
            market_hash_name = EXCLUDED.market_hash_name,
            price = EXCLUDED.price,
            type = EXCLUDED.type 
    """ 

    params_list = [
        (   
            int(item["id"]),
            item.get("market_hash_name"),
            item.get("price"),
            item.get("type"),
        )
        for item in items
    ]

    async with PgAsync(sql_path=SQL_, dbname="CSfloat_items") as db: # и это в цикле очень долго работатет
        await db.save_many(query, params_list)


@LOGS_.count_calls
async def get_avg_price_from_history():
    qwery = """
    SELECT * FROM avg_price_by_name
    """
    async with PgAsync(sql_path=SQL_, dbname="CSfloat_items") as pg:
        return await pg.fetch_all(qwery)

# очень долгая функция очень очень очень 
@LOGS_.log_
async def get_history(hash_name:str, paint_idx):
    name_p7c_p20 =hash_name.replace(" ","%20").replace("|","%7C") 
    url = f"https://csfloat.com/api/v1/history/{name_p7c_p20}/sales?paint_index={paint_idx}"
    
    csf = CSFloatAsync(url=url)

    items, cod = await csf.get_from_history() # это в цикле очень долго работатет
    query = """
        INSERT INTO avg_price_where_hashname(
        market_hash_name,
        price
        )  
        VALUES ($1, $2);      
    """

    params_list = [
        (
            item.get("market_hash_name"),
            item.get("price"),
        )
        for item in items
    ]

    async with PgAsync(sql_path=SQL_, dbname="CSfloat_items") as db: # и это в цикле очень долго работатет
        await db.save_many(query, params_list)


async def seve_similar():
    pass

async def save_history():
    pass