-- =========================================================
-- 4. Листинги и история рынка
-- =========================================================

CREATE TABLE IF NOT EXISTS market_listing (
    market_listing_id     BIGSERIAL PRIMARY KEY,
    platform_id           BIGINT NOT NULL,
    external_listing_id   TEXT NOT NULL,
    item_instance_id      BIGINT NOT NULL,
    seller_account_id     BIGINT,
    currency_id           BIGINT NOT NULL,
    listed_price          NUMERIC(12,2) NOT NULL,
    listed_at             TIMESTAMPTZ NOT NULL,
    first_seen_at         TIMESTAMPTZ NOT NULL,
    last_seen_at          TIMESTAMPTZ NOT NULL,
    current_status        TEXT NOT NULL,

    CONSTRAINT fk_market_listing_platform
        FOREIGN KEY (platform_id)
        REFERENCES platform (platform_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT fk_market_listing_item_instance
        FOREIGN KEY (item_instance_id)
        REFERENCES item_instance (item_instance_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT fk_market_listing_seller_account
        FOREIGN KEY (seller_account_id)
        REFERENCES trader_platform_account (trader_platform_account_id)
        ON UPDATE RESTRICT
        ON DELETE SET NULL,

    CONSTRAINT fk_market_listing_currency
        FOREIGN KEY (currency_id)
        REFERENCES currency (currency_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT uq_market_listing_platform_external
        UNIQUE (platform_id, external_listing_id),

    CONSTRAINT chk_market_listing_external_listing_id_not_blank
        CHECK (btrim(external_listing_id) <> ''),

    CONSTRAINT chk_market_listing_price_nonnegative
        CHECK (listed_price >= 0),

    CONSTRAINT chk_market_listing_status_not_blank
        CHECK (btrim(current_status) <> ''),

    CONSTRAINT chk_market_listing_seen_order
        CHECK (first_seen_at <= last_seen_at)
);

CREATE TABLE IF NOT EXISTS market_listing_price_history (
    market_listing_price_history_id BIGSERIAL PRIMARY KEY,
    market_listing_id               BIGINT NOT NULL,
    observed_at                     TIMESTAMPTZ NOT NULL,
    price_amount                    NUMERIC(12,2) NOT NULL,
    currency_id                     BIGINT NOT NULL,

    CONSTRAINT fk_market_listing_price_history_listing
        FOREIGN KEY (market_listing_id)
        REFERENCES market_listing (market_listing_id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,

    CONSTRAINT fk_market_listing_price_history_currency
        FOREIGN KEY (currency_id)
        REFERENCES currency (currency_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT uq_market_listing_price_history_listing_observed
        UNIQUE (market_listing_id, observed_at),

    CONSTRAINT chk_market_listing_price_history_price_nonnegative
        CHECK (price_amount >= 0)
);

CREATE TABLE IF NOT EXISTS market_listing_status_history (
    market_listing_status_history_id BIGSERIAL PRIMARY KEY,
    market_listing_id                BIGINT NOT NULL,
    event_type_id                    BIGINT NOT NULL,
    event_time                       TIMESTAMPTZ NOT NULL,
    old_status                       TEXT,
    new_status                       TEXT,

    CONSTRAINT fk_market_listing_status_history_listing
        FOREIGN KEY (market_listing_id)
        REFERENCES market_listing (market_listing_id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,

    CONSTRAINT fk_market_listing_status_history_event_type
        FOREIGN KEY (event_type_id)
        REFERENCES event_type (event_type_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT uq_market_listing_status_history_business
        UNIQUE (market_listing_id, event_time, event_type_id)
);

CREATE TABLE IF NOT EXISTS market_observation_snapshot (
    market_observation_snapshot_id BIGSERIAL PRIMARY KEY,
    market_listing_id              BIGINT NOT NULL,
    observed_at                    TIMESTAMPTZ NOT NULL,
    position_in_search             INTEGER,
    watchers_count                 INTEGER,
    min_offer_price                NUMERIC(12,2),
    scm_reference_price            NUMERIC(12,2),
    scm_reference_volume           INTEGER,
    is_visible                     BOOLEAN NOT NULL,

    CONSTRAINT fk_market_observation_snapshot_listing
        FOREIGN KEY (market_listing_id)
        REFERENCES market_listing (market_listing_id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,

    CONSTRAINT uq_market_observation_snapshot_listing_observed
        UNIQUE (market_listing_id, observed_at),

    CONSTRAINT chk_market_observation_snapshot_position_nonnegative
        CHECK (position_in_search IS NULL OR position_in_search >= 0),

    CONSTRAINT chk_market_observation_snapshot_watchers_nonnegative
        CHECK (watchers_count IS NULL OR watchers_count >= 0),

    CONSTRAINT chk_market_observation_snapshot_min_offer_nonnegative
        CHECK (min_offer_price IS NULL OR min_offer_price >= 0),

    CONSTRAINT chk_market_observation_snapshot_scm_price_nonnegative
        CHECK (scm_reference_price IS NULL OR scm_reference_price >= 0),

    CONSTRAINT chk_market_observation_snapshot_scm_volume_nonnegative
        CHECK (scm_reference_volume IS NULL OR scm_reference_volume >= 0)
);

CREATE TABLE IF NOT EXISTS container_market_snapshot (
    container_market_snapshot_id BIGSERIAL PRIMARY KEY,
    container_id                 BIGINT NOT NULL,
    platform_id                  BIGINT NOT NULL,
    observed_at                  TIMESTAMPTZ NOT NULL,
    listings_count               INTEGER NOT NULL,
    min_price                    NUMERIC(12,2),
    median_price                 NUMERIC(12,2),
    avg_price                    NUMERIC(12,2),
    max_price                    NUMERIC(12,2),
    sold_estimate_24h            INTEGER,
    sold_estimate_7d             INTEGER,

    CONSTRAINT fk_container_market_snapshot_container
        FOREIGN KEY (container_id)
        REFERENCES container (container_id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,

    CONSTRAINT fk_container_market_snapshot_platform
        FOREIGN KEY (platform_id)
        REFERENCES platform (platform_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT uq_container_market_snapshot_business
        UNIQUE (container_id, platform_id, observed_at),

    CONSTRAINT chk_container_market_snapshot_listings_count_nonnegative
        CHECK (listings_count >= 0),

    CONSTRAINT chk_container_market_snapshot_min_price_nonnegative
        CHECK (min_price IS NULL OR min_price >= 0),

    CONSTRAINT chk_container_market_snapshot_median_price_nonnegative
        CHECK (median_price IS NULL OR median_price >= 0),

    CONSTRAINT chk_container_market_snapshot_avg_price_nonnegative
        CHECK (avg_price IS NULL OR avg_price >= 0),

    CONSTRAINT chk_container_market_snapshot_max_price_nonnegative
        CHECK (max_price IS NULL OR max_price >= 0),

    CONSTRAINT chk_container_market_snapshot_sold_estimate_24h_nonnegative
        CHECK (sold_estimate_24h IS NULL OR sold_estimate_24h >= 0),

    CONSTRAINT chk_container_market_snapshot_sold_estimate_7d_nonnegative
        CHECK (sold_estimate_7d IS NULL OR sold_estimate_7d >= 0)
);