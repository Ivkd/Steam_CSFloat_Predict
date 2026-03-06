from pathlib import Path

from APIs.help_func.trade_shop_cls import SteamAsync, PgAsync
from APIs.help_func.log import Helpfull
LOGS_ = Helpfull()

!!!!!!!!! ПЕРЕКИНУТЬ ЭТО ВСЕ В КЛАСС И СДЕЛАТЬ НОРМЛЬНЫЙ КЛАСС ПО SOLID ТАК ЖЕ ДОБАВИТЬ К НЕМУ НОРМАЛЬНЫЙ SAVE_CHACHE БУДЕТ ПРОЩЕ !!!!!!!!!!

URL_ = "https://steamcommunity.com/market/search/render/"
SQL_ = Path(__file__).resolve().parent / "steam_db.sql"

sort_dir = ["desc"]

@LOGS_.log_
# @LOGS_.count_calls
async def get_item_bd_steam(qwery: str, *args):
    async with PgAsync(sql_path=SQL_, dbname="Steam_items") as pg:
        return await pg.fetch_all(qwery, *args)
    
@LOGS_.log_
# @LOGS_.count_calls
async def  get_all_items_steam(
    sort_column_: str = "popular",
    sort_dir_: str = "desc",
    start_:int = 0,
    category:str = None,
    ):
    
    steam = SteamAsync(url=URL_)

    cases, cod = await steam.get_data(
        start=start_,
        sort_column = sort_column_,
        sort_dir=sort_dir_,
        max_pages=250, 
        category=category
    )

    query = """
        INSERT INTO all_items_steam (
            hash_name,
            name,
            sell_price,
            sell_listings,
            icon_url,
            updated_at
        )
        VALUES ($1, $2, $3, $4, $5, NOW())
        ON CONFLICT (hash_name) DO UPDATE SET
            name = EXCLUDED.name,
            sell_price = EXCLUDED.sell_price,
            sell_listings = EXCLUDED.sell_listings,
            icon_url = EXCLUDED.icon_url,
            updated_at = NOW();
        """

    params_list = [
        (
            case.get("market_hash_name"),
            case.get("item_name"),
            case.get("sell_price"),
            case.get("sell_listings"),
            case.get("icon_url"),
        )
        for case in cases
    ]
    
    async with PgAsync(sql_path=SQL_, dbname="Steam_items") as db:
        await db.save_many(query, params_list)

