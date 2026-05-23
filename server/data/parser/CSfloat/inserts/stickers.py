async def insert_attributes_from_response(pool, response):
    async with pool.acquire() as conn:
        instance_id = await conn.fetchval("""
            SELECT item_instance_id FROM item_instance
            WHERE origin_asset_id=$1
        """, response["item"]["asset_id"])

        attrs = {
            "rarity": str(response["item"]["rarity"]),
            "rarity_name": response["item"]["rarity_name"],
            "type": response["item"]["type"],
        }

        for k, v in attrs.items():
            await conn.execute("""
                INSERT INTO item_instance_attribute (item_instance_id, attr_name, attr_value)
                VALUES ($1,$2,$3)
                ON CONFLICT (item_instance_id, attr_name)
                DO NOTHING
            """, instance_id, k, v)


async def insert_stickers_from_response(pool, response):
    async with pool.acquire() as conn:
        instance_id = await conn.fetchval("""
            SELECT item_instance_id FROM item_instance
            WHERE origin_asset_id=$1
        """, response["item"]["asset_id"])

        for sticker in response["item"]["stickers"]:
            sticker_id = await conn.fetchval("""
                SELECT sticker_id FROM sticker
                WHERE name=$1
            """, sticker["name"])

            if not sticker_id:
                continue

            await conn.execute("""
                INSERT INTO item_instance_sticker (item_instance_id, sticker_id)
                VALUES ($1,$2)
                ON CONFLICT (item_instance_id, sticker_id)
                DO NOTHING
            """, instance_id, sticker_id)