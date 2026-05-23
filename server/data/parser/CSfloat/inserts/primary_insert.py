
from fastapi import logger
from .....core.logger import *

# Функция без response, так как данные о платформах статичны и не зависят от ответа API
async def insert_platform(pool, platform_data):
    for id in platform_data:
        code = platform_data[id]["code"]
        name = platform_data[id]["name"]    
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO platform (code, name)
                VALUES ($1, $2)
                ON CONFLICT (code) DO NOTHING
            """, code, name)

async def insert_currency(pool, currency_data):
    for id in currency_data:
        code = currency_data[id]["code"]
        name = currency_data[id]["name"]
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO currency (code, name)
                VALUES ($1, $2)
                ON CONFLICT (code) DO NOTHING
            """, code, name)

async def insert_quality(pool, item_quality_data):
    for id in item_quality_data:

        code = item_quality_data[id]["code"]
        name = item_quality_data[id]["name"] 
        min_float = item_quality_data[id]["min_float"]
        max_float = item_quality_data[id]["max_float"]

        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO item_quality (code, name, min_float, max_float)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (code) DO NOTHING
            """, code, name, min_float, max_float)

async def insert_weapon(pool, weapon_data):
    for id in weapon_data:
        weapon_id = id
        weapon_name = weapon_data[id]["name"]
        weapon_group = weapon_data[id]["weapon_group"]
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO weapon (weapon_id, name, weapon_group)
                VALUES ($1, $2, $3)
                ON CONFLICT (weapon_id) DO NOTHING
            """, weapon_id, weapon_name, weapon_group)


# Далее функции для вставки данных, зависящих от ответа API
async def insert_sticker(pool, name: str, price: int):
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO sticker (name, price)
                VALUES ($1, $2)
                ON CONFLICT (name) DO NOTHING
            """, name, price)

async def insert_skin_from_response(pool, skin_name: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO skin (name)
            VALUES ($1)
            ON CONFLICT (name) DO NOTHING
        """, skin_name)

async def insert_event_type(pool, event_type_data):
    for id in event_type_data:
        code = event_type_data[id]["code"]
        name = event_type_data[id]["name"]
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO event_type (code, name)
                VALUES ($1, $2)
                ON CONFLICT (code) DO NOTHING
            """, code, name)
        
async def insert_containers(pool, container_data):
    for id in container_data:
        name = container_data[id]["name"]
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO container (def_index, name)
                VALUES ($1, $2)
            """, id, name)