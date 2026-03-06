from APIs.steam.pars_steam import (
    get_item_bd_steam,
    get_all_items_steam,
) 
from APIs.csflaot.pars_csfloat import (
    get_item_bd_csfloat,
    get_items_csfloat,
    get_case_csfloat,
    get_avg_price_from_history,
    get_history,
    get_similar,
    get_avg_price_similar_items,
)


from datetime import datetime
import asyncio
import numpy
import pydentic
import pandas
from typing import Any
from decimal import Decimal
from APIs.help_func.log import Helpfull
import aiofiles

LOGS_ = Helpfull()
STEAM_PERCENT = Decimal("0.87")

COUNT_ITEMS_TO_PRINT = 30
MAX_PRICE = 15 * 100
MIN_PRICE = 10 * 100

# код работает 
#
# придумать как обернуть хождение на сайт в sql и cache, чтоб при хронении в cache не идти в bd
# именно при хождении на сайт а не просто выборку из sql
#
# Начать логировать больше функций и убрать не нужные декораторы логов у функций
#


def create_url_steam_item(name_item:str):
    name_item = name_item.replace(" ","%20")
    return f"https://steamcommunity.com/market/listings/730/{name_item}"

def create_url_csf_item(item_id):
    return f"https://csfloat.com/item/{item_id}"

@LOGS_.log_
@LOGS_.sey_time
async def get_containers_from_bd(): 

    cases:list[dict] = []
    count = 1
    
    qwery_select = """SELECT * FROM containers"""
    qwery = """SELECT * FROM all_items_steam WHERE hash_name ILIKE '%Case%';"""

    data_csfloat = await get_item_bd_csfloat(qwery_select)
    data_steam = await get_item_bd_steam(qwery)
    
    steam_by_name = {row["hash_name"]: row for row in data_steam}

    for item_c in data_csfloat:

        name = item_c.get("market_hash_name")
        item_s = steam_by_name.get(name)
        if not item_s:
            continue
        
        price_c:int = item_c.get("price") 
        price_s:int = item_s.get("sell_price")
        icon = item_s.get("icon_url")

        procent = round((price_c / price_s) * 100)
        cases.append(    
            {   
                "id": count,
                "name": name,
                "price_csf": price_c,
                "price_steam": price_s,
                "icon": icon,
                "procent": procent,
            }
        )
        
        count += 1
    return cases

# добавить логику выбора(кейсы и скины и ...)
@LOGS_.sey_time
async def count_true_price(buget, item: dict):
    buget = Decimal(buget)         
    end_price = Decimal("0")        

    price_c = Decimal(item["price_csf"])
    price_s = Decimal(item["price_steam"])

    count = buget // price_c   
    sell_p = Decimal(count) * price_s      
    end_price += sell_p * STEAM_PERCENT     

    return round(end_price - buget), round(end_price)

@LOGS_.count_calls
async def get_sim_hist(data):
    # временно 
    name_list = []
    print(data)
    for d in data:
        name = d.get("name")
        item_id = d.get("item_id")
        if name not in name_list:
            await get_similar(item_id)
            name_list.append(name)
    
    avg_items = {}
    avg_sim_items = await get_avg_price_similar_items()

    for sim_item in avg_sim_items:
        avg_items[sim_item.get("market_hash_name")] = sim_item.get("avg_price")
    return avg_items

@LOGS_.log_
@LOGS_.count_calls
async def get_items_from_bd(ustr:str):
    items:list[dict] = []
    count = 1

    qwery_c = f"""SELECT * FROM skins_items WHERE market_hash_name ILIKE $1;"""
    qwery_s = f"""SELECT * FROM all_items_steam WHERE hash_name ILIKE $1;"""

    data_steam = await get_item_bd_steam(qwery_s, f'%{ustr}%')
    data_csfloat = await get_item_bd_csfloat(qwery_c, f'%{ustr}%')

    print(data_csfloat)
    print("")
    print("")
    print(data_steam)

    steam_by_name = {row["hash_name"]: row for row in data_steam}
    for csf_data in data_csfloat:
        name = csf_data.get("market_hash_name")

        steam_data = steam_by_name.get(name)
        if not steam_data:
            print(f"not {name} in steam")
            continue
        
        price_csf:int = csf_data.get("price") 
        float_value = csf_data.get("float_value")
        paint_index = csf_data.get("paint_index")
        item_id = csf_data.get("item_id")
        item_type = csf_data.get("type")
        price_steam:int = steam_data.get("sell_price")
        icon = steam_data.get("icon_url")

        steam_url = create_url_steam_item(name)
        csf_url = create_url_csf_item(item_id)

        procent = round((price_csf / price_steam) * 100)
        items.append(    
            {   
                "id": count,
                "item_id": item_id,
                "name": name,
                "price_csf": price_csf,
                "price_steam": price_steam,
                "icon": icon,
                "procent": procent,
                "float_value_csf": float_value,
                "paint_index": paint_index,
                "steam_url": steam_url,
                "csf_url": csf_url,
                "item_type": item_type
            }
        )    

        count += 1

    return items

@LOGS_.log_  
@LOGS_.sey_time
async def menu():
    text = f"""
        0. case
        2.1. Desert Eagle ✅
        2.2. Dual Berettas
        2.3. Five-SeveN
        2.4. Glock-18 ✅
        2.7. AK-47 ✅
        2.8. AUG
        2.9. AWP ✅
        2.10. FAMAS
        2.11. G3SG1
        2.13. Galil AR ✅
        2.14. M249
        2.16. M4A4 ✅
        2.17. MAC-10
        2.19. P90 ✅
        2.23. MP5-SD
        2.24. UMP-45
        2.25. XM1014
        2.26. PP-Bizon
        2.27. MAG-7
        2.28. Negev
        2.29. Sawed-Off
        2.30. Tec-9
        2.31. Zeus x27
        2.32. P2000
        2.33. MP7
        2.34. MP9
        2.35. Nova
        2.36. P250 ✅
        2.38. SCAR-20
        2.39. SG 553
        2.40. SSG 08
        2.60. M4A1-S ✅
        2.61. USP-S ✅
        2.63. CZ75-Auto ✅
        2.64. R8 Revolver
    """

    f_id_dict = {
    1: ["Deagle", "deagle"],
    2: ["Dual Berettas", "Dual Berettas"],
    3: ["Five-SeveN", "Five-SeveN"],
    4: ["Glock-18", "glock"],
    7: ["AK-47", "AK-47"],
    8: ["AUG", "AUG"],
    9: ["AWP", "AWP"],
    10: ["FAMAS", "FAMAS"],
    11: ["G3SG1", "G3SG1"],
    13: ["Galil AR", "galilar"],
    14: ["M249", "M249"],
    16: ["M4A4", "m4a1"],
    17: ["MAC-10", "MAC-10"],
    19: ["P90", "p90"],
    23: ["MP5-SD", "MP5-SD"],
    24: ["UMP-45", "UMP-45"],
    25: ["XM1014", "XM1014"],
    26: ["PP-Bizon", "PP-Bizon"],
    27: ["MAG-7", "MAG-7"],
    28: ["Negev", "Negev"],
    29: ["Sawed-Off", "Sawed-Off"],
    30: ["Tec-9", "Tec-9"],
    31: ["Zeus x27", "Zeus x27"],
    32: ["P2000", "hkp2000"],
    33: ["MP7", "MP7"],
    34: ["MP9", "MP9"],
    35: ["Nova", "Nova"],
    36: ["P250", "P250"],
    38: ["SCAR-20", "SCAR-20"],
    39: ["SG 553", "SG 553"],
    40: ["SSG 08", "SSG 08"],
    60: ["M4A1-S", "m4a1_silencer"],
    61: ["USP-S", "usp_silencer"],
    63: ["CZ75-Auto", "cz75a"],
    64: ["R8 Revolver", ""],
    }

    buget = int(input("input youre buget... \n"))
   
    choice = int(input(f"input youre choose... \n {text}"))
    if choice == 0:
        await get_case_csfloat()
        items = await get_containers_from_bd()
    else:
        val = f_id_dict.get(choice)
        for_csf = choice
        for_steam = f'tag_weapon_{val[1].lower().replace(" ","").replace("-","")}'
        for_bd = val[0]

        t1 = asyncio.create_task(get_items_csfloat(def_index_=for_csf, min_price_=MIN_PRICE, max_price_=MAX_PRICE))
        t2 = asyncio.create_task(get_all_items_steam(category=for_steam))
        await asyncio.gather(t1, t2)

        items = await get_items_from_bd(for_bd)
        avg_items = await get_sim_hist(items)
        sorted_items = sorted(items, key=lambda x: x.get("procent"), )  # [web:132]

        count = 0
        seen_name_print = set()

        for item in sorted_items:

            p = item.get("procent")
            name = item.get("name")
            pr = item.get("price_steam")

            avg_price_sim = avg_items.get(name)

            pr_avg_sim  = round(avg_price_sim  / pr * 100) if pr and avg_price_sim else 0

            if not (MIN_PRICE <= pr <= MAX_PRICE):
                continue

            # if not (70 <= p <= 100):
            #     continue

            # if p is None or name is None:
            #     continue
            
            if name in seen_name_print:
                continue
            seen_name_print.add(name)

            if count == COUNT_ITEMS_TO_PRINT:
                break
            try:
                async with aiofiles.open(f"Предложения по {val[0]}.txt", mode="a", encoding="utf-8") as f:
                    text = f"""
    №{item.get("id")},
    {name}: %{p}.
    price is {item.get("price_csf")}, {pr}
    avg similar price csf {avg_price_sim} %{pr_avg_sim}
    steam: {item.get("steam_url")}
    csf: {item.get("csf_url")}
    type: {item.get("item_type")}
        """     
                    await f.write(text)
                    count += 1
            except Exception as e:
                print(e)

        now = datetime.now()
        async with aiofiles.open(f"Предложения по {val[0]}.txt", mode="a", encoding="utf-8") as f:
            await f.write(f"{now:%d.%m.%Y %H:%M}\n")
        
        print(f"Seve complite to {val[0]}")

        choose = int(input("input youre choose... \n"))

        result = await count_true_price(buget*100, items[choose-1])
        print(f"u get: ", result)

@LOGS_.log_
@LOGS_.sey_time
async def start():
    await menu() 
asyncio.run(start())
