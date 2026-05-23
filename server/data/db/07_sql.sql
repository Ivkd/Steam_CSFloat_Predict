-- =========================================================
-- 8. Индексы
-- PostgreSQL не создает индексы на FK автоматически,
-- а для JOIN/DELETE/UPDATE они очень важны.
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_game_item_weapon_id
    ON game_item (weapon_id);

CREATE INDEX IF NOT EXISTS idx_game_item_skin_id
    ON game_item (skin_id);

CREATE INDEX IF NOT EXISTS idx_game_item_quality_id
    ON game_item (quality_id);

CREATE INDEX IF NOT EXISTS idx_item_instance_game_item_id
    ON item_instance (game_item_id);

CREATE INDEX IF NOT EXISTS idx_item_instance_origin_platform_id
    ON item_instance (origin_platform_id);

CREATE INDEX IF NOT EXISTS idx_trader_platform_account_trader_account_id
    ON trader_platform_account (trader_account_id);

CREATE INDEX IF NOT EXISTS idx_trader_platform_account_platform_id
    ON trader_platform_account (platform_id);

CREATE INDEX IF NOT EXISTS idx_market_listing_platform_id
    ON market_listing (platform_id);

CREATE INDEX IF NOT EXISTS idx_market_listing_item_instance_id
    ON market_listing (item_instance_id);

CREATE INDEX IF NOT EXISTS idx_market_listing_seller_account_id
    ON market_listing (seller_account_id);

CREATE INDEX IF NOT EXISTS idx_market_listing_currency_id
    ON market_listing (currency_id);

CREATE INDEX IF NOT EXISTS idx_market_listing_price_history_market_listing_id
    ON market_listing_price_history (market_listing_id);

CREATE INDEX IF NOT EXISTS idx_market_listing_price_history_currency_id
    ON market_listing_price_history (currency_id);

CREATE INDEX IF NOT EXISTS idx_market_listing_status_history_market_listing_id
    ON market_listing_status_history (market_listing_id);

CREATE INDEX IF NOT EXISTS idx_market_listing_status_history_event_type_id
    ON market_listing_status_history (event_type_id);

CREATE INDEX IF NOT EXISTS idx_market_observation_snapshot_market_listing_id
    ON market_observation_snapshot (market_listing_id);

CREATE INDEX IF NOT EXISTS idx_trader_inventory_snapshot_trader_platform_account_id
    ON trader_inventory_snapshot (trader_platform_account_id);

CREATE INDEX IF NOT EXISTS idx_trader_inventory_item_snapshot_inventory_snapshot_id
    ON trader_inventory_item_snapshot (trader_inventory_snapshot_id);

CREATE INDEX IF NOT EXISTS idx_trader_inventory_item_snapshot_item_instance_id
    ON trader_inventory_item_snapshot (item_instance_id);

CREATE INDEX IF NOT EXISTS idx_trader_inventory_item_snapshot_currency_id
    ON trader_inventory_item_snapshot (currency_id);

CREATE INDEX IF NOT EXISTS idx_trader_item_action_trader_platform_account_id
    ON trader_item_action (trader_platform_account_id);

CREATE INDEX IF NOT EXISTS idx_trader_item_action_item_instance_id
    ON trader_item_action (item_instance_id);

CREATE INDEX IF NOT EXISTS idx_trader_item_action_event_type_id
    ON trader_item_action (event_type_id);

CREATE INDEX IF NOT EXISTS idx_trader_item_action_source_snapshot_id
    ON trader_item_action (source_snapshot_id);

CREATE INDEX IF NOT EXISTS idx_item_market_snapshot_platform_id
    ON item_market_snapshot (platform_id);

CREATE INDEX IF NOT EXISTS idx_item_market_snapshot_game_item_id
    ON item_market_snapshot (game_item_id);


