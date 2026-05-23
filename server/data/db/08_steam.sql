CREATE TABLE IF NOT EXISTS steam_price_history (
    steam_price_history_id  BIGSERIAL PRIMARY KEY,
    game_item_id            BIGINT NOT NULL REFERENCES game_item(game_item_id),
    recorded_at             TIMESTAMPTZ NOT NULL,    -- день с Steam
    median_price_usd        NUMERIC(12, 4) NOT NULL, -- средняя цена за день
    volume                  INT NOT NULL,             -- объём продаж за день
    UNIQUE (game_item_id, recorded_at)               -- не дублируем дни
);

CREATE INDEX IF NOT EXISTS idx_sph_game_item ON steam_price_history (game_item_id);
CREATE INDEX IF NOT EXISTS idx_sph_date ON steam_price_history (recorded_at DESC);