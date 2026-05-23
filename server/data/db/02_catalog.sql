-- =========================================================
-- 2. Каталог предметов
-- =========================================================

--все оружия по полям из reference tables
CREATE TABLE IF NOT EXISTS game_item (
    game_item_id         BIGSERIAL PRIMARY KEY,
    weapon_id            INT NOT NULL,
    skin_id              INT NOT NULL,
    quality_id           INT NOT NULL,
    is_stattrak          BOOLEAN NOT NULL DEFAULT FALSE,
    is_souvenir          BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT fk_game_item_weapon
        FOREIGN KEY (weapon_id)
        REFERENCES weapon (weapon_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT fk_game_item_skin
        FOREIGN KEY (skin_id)
        REFERENCES skin (skin_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT fk_game_item_quality
        FOREIGN KEY (quality_id)
        REFERENCES item_quality (quality_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT uq_game_item_business
        UNIQUE (weapon_id, skin_id, quality_id, is_stattrak, is_souvenir)
);

CREATE TABLE IF NOT EXISTS item_instance (
    item_instance_id     BIGSERIAL PRIMARY KEY,
    game_item_id         BIGINT NOT NULL,
    origin_platform_id   BIGINT,
    origin_asset_id      TEXT,
    float_value          NUMERIC(8,6),
    paint_seed           INTEGER,
    inspect_link         TEXT,
    first_seen_at        TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_item_instance_game_item
        FOREIGN KEY (game_item_id)
        REFERENCES game_item (game_item_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT fk_item_instance_origin_platform
        FOREIGN KEY (origin_platform_id)
        REFERENCES platform (platform_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT uq_item_instance_origin
        UNIQUE (origin_platform_id, origin_asset_id),

    CONSTRAINT chk_item_instance_float_value CHECK (
        float_value IS NULL OR (float_value >= 0 AND float_value <= 1)
    )
);

CREATE TABLE IF NOT EXISTS container_item (
    container_item_id BIGSERIAL PRIMARY KEY,
    container_id      BIGINT NOT NULL,
    item_id      BIGINT,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT fk_container_item_container
        FOREIGN KEY (container_id)
        REFERENCES container (container_id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,

    CONSTRAINT uq_container_item_business
        UNIQUE (container_id, item_id, is_active)
);