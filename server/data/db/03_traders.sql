-- =========================================================
-- 3. Трейдеры
-- =========================================================

CREATE TABLE IF NOT EXISTS trader_account (
    trader_account_id    BIGSERIAL PRIMARY KEY,
    nickname             TEXT,
    total_trades         INTEGER,
    is_monitored         BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_trader_account_nickname_not_blank CHECK (
        nickname IS NULL OR btrim(nickname) <> ''
    )
);

CREATE TABLE IF NOT EXISTS trader_platform_account (
    trader_platform_account_id BIGSERIAL PRIMARY KEY,
    trader_account_id          BIGINT NOT NULL,
    platform_id                BIGINT NOT NULL,
    platform_user_id           TEXT NOT NULL,
    profile_url                TEXT,

    CONSTRAINT fk_trader_platform_account_trader_account
        FOREIGN KEY (trader_account_id)
        REFERENCES trader_account (trader_account_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT fk_trader_platform_account_platform
        FOREIGN KEY (platform_id)
        REFERENCES platform (platform_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT uq_trader_platform_account_platform_user
        UNIQUE (platform_id, platform_user_id),

    CONSTRAINT chk_trader_platform_account_platform_user_not_blank
        CHECK (btrim(platform_user_id) <> '')
);

-- =========================================================
-- 5. Инвентари трейдеров
-- =========================================================

CREATE TABLE IF NOT EXISTS trader_inventory_snapshot (
    trader_inventory_snapshot_id BIGSERIAL PRIMARY KEY,
    trader_platform_account_id   BIGINT NOT NULL,
    observed_at                  TIMESTAMPTZ NOT NULL,
    total_items_count            INTEGER,

    CONSTRAINT fk_trader_inventory_snapshot_trader_platform_account
        FOREIGN KEY (trader_platform_account_id)
        REFERENCES trader_platform_account (trader_platform_account_id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,

    CONSTRAINT uq_trader_inventory_snapshot_account_observed
        UNIQUE (trader_platform_account_id, observed_at),

    CONSTRAINT chk_trader_inventory_snapshot_total_items_nonnegative
        CHECK (total_items_count IS NULL OR total_items_count >= 0)
);

CREATE TABLE IF NOT EXISTS trader_inventory_item_snapshot (
    trader_inventory_item_snapshot_id BIGSERIAL PRIMARY KEY,
    trader_inventory_snapshot_id      BIGINT NOT NULL,
    item_instance_id                  BIGINT NOT NULL,
    estimated_acquired_at             TIMESTAMPTZ,
    estimated_unlock_at               TIMESTAMPTZ,
    observed_list_price               NUMERIC(12,2),
    currency_id                       BIGINT,
    is_listed_for_sale                BOOLEAN,

    CONSTRAINT fk_trader_inventory_item_snapshot_inventory_snapshot
        FOREIGN KEY (trader_inventory_snapshot_id)
        REFERENCES trader_inventory_snapshot (trader_inventory_snapshot_id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,

    CONSTRAINT fk_trader_inventory_item_snapshot_item_instance
        FOREIGN KEY (item_instance_id)
        REFERENCES item_instance (item_instance_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT fk_trader_inventory_item_snapshot_currency
        FOREIGN KEY (currency_id)
        REFERENCES currency (currency_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT uq_trader_inventory_item_snapshot_business
        UNIQUE (trader_inventory_snapshot_id, item_instance_id),

    CONSTRAINT chk_trader_inventory_item_snapshot_price_nonnegative
        CHECK (observed_list_price IS NULL OR observed_list_price >= 0),

    CONSTRAINT chk_trader_inventory_item_snapshot_time_order
        CHECK (
            estimated_acquired_at IS NULL
            OR estimated_unlock_at IS NULL
            OR estimated_acquired_at <= estimated_unlock_at
        )
);

CREATE TABLE IF NOT EXISTS trader_item_action (
    trader_item_action_id       BIGSERIAL PRIMARY KEY,
    trader_platform_account_id  BIGINT NOT NULL,
    item_instance_id            BIGINT NOT NULL,
    event_type_id               BIGINT NOT NULL,
    action_time                 TIMESTAMPTZ NOT NULL,
    price_amount                NUMERIC(12,2),
    currency_id                 BIGINT,
    confidence_score            NUMERIC(5,4),
    source_snapshot_id          BIGINT,

    CONSTRAINT fk_trader_item_action_trader_platform_account
        FOREIGN KEY (trader_platform_account_id)
        REFERENCES trader_platform_account (trader_platform_account_id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,

    CONSTRAINT fk_trader_item_action_item_instance
        FOREIGN KEY (item_instance_id)
        REFERENCES item_instance (item_instance_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT fk_trader_item_action_event_type
        FOREIGN KEY (event_type_id)
        REFERENCES event_type (event_type_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT fk_trader_item_action_currency
        FOREIGN KEY (currency_id)
        REFERENCES currency (currency_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT fk_trader_item_action_source_snapshot
        FOREIGN KEY (source_snapshot_id)
        REFERENCES trader_inventory_snapshot (trader_inventory_snapshot_id)
        ON UPDATE RESTRICT
        ON DELETE SET NULL,

    CONSTRAINT chk_trader_item_action_price_nonnegative
        CHECK (price_amount IS NULL OR price_amount >= 0),

    CONSTRAINT chk_trader_item_action_confidence_range
        CHECK (confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1))
);

CREATE TABLE IF NOT EXISTS item_market_snapshot (
    item_market_snapshot_id BIGSERIAL PRIMARY KEY,
    platform_id             BIGINT NOT NULL,
    game_item_id            BIGINT NOT NULL,
    observed_at             TIMESTAMPTZ NOT NULL,
    listings_count          INTEGER NOT NULL,
    min_price               NUMERIC(12,2),
    median_price            NUMERIC(12,2),
    avg_price               NUMERIC(12,2),
    max_price               NUMERIC(12,2),
    sold_estimate_24h       INTEGER,
    sold_estimate_7d        INTEGER,
    scm_reference_price     NUMERIC(12,2),
    scm_reference_volume    INTEGER,

    CONSTRAINT fk_item_market_snapshot_platform
        FOREIGN KEY (platform_id)
        REFERENCES platform (platform_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT fk_item_market_snapshot_game_item
        FOREIGN KEY (game_item_id)
        REFERENCES game_item (game_item_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT uq_item_market_snapshot_business
        UNIQUE (platform_id, game_item_id, observed_at),

    CONSTRAINT chk_item_market_snapshot_listings_count_nonnegative
        CHECK (listings_count >= 0),

    CONSTRAINT chk_item_market_snapshot_min_price_nonnegative
        CHECK (min_price IS NULL OR min_price >= 0),

    CONSTRAINT chk_item_market_snapshot_median_price_nonnegative
        CHECK (median_price IS NULL OR median_price >= 0),

    CONSTRAINT chk_item_market_snapshot_avg_price_nonnegative
        CHECK (avg_price IS NULL OR avg_price >= 0),

    CONSTRAINT chk_item_market_snapshot_max_price_nonnegative
        CHECK (max_price IS NULL OR max_price >= 0),

    CONSTRAINT chk_item_market_snapshot_sold_estimate_24h_nonnegative
        CHECK (sold_estimate_24h IS NULL OR sold_estimate_24h >= 0),

    CONSTRAINT chk_item_market_snapshot_sold_estimate_7d_nonnegative
        CHECK (sold_estimate_7d IS NULL OR sold_estimate_7d >= 0),

    CONSTRAINT chk_item_market_snapshot_scm_reference_price_nonnegative
        CHECK (scm_reference_price IS NULL OR scm_reference_price >= 0),

    CONSTRAINT chk_item_market_snapshot_scm_reference_volume_nonnegative
        CHECK (scm_reference_volume IS NULL OR scm_reference_volume >= 0)
);

