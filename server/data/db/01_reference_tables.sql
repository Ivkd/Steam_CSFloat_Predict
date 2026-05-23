-- =========================================================
-- 1. Справочники
-- =========================================================

--платформы
CREATE TABLE IF NOT EXISTS platform (
    platform_id          BIGSERIAL PRIMARY KEY,
    code                 TEXT NOT NULL, 
    name                 TEXT NOT NULL,
    CONSTRAINT uq_platform_code UNIQUE (code),
    CONSTRAINT uq_platform_name UNIQUE (name),
    CONSTRAINT chk_platform_code_not_blank CHECK (btrim(code) <> ''),
    CONSTRAINT chk_platform_name_not_blank CHECK (btrim(name) <> '')
);

--цены на пушки
CREATE TABLE IF NOT EXISTS currency (
    currency_id          BIGSERIAL PRIMARY KEY,
    code                 CHAR(3) NOT NULL,
    name                 TEXT NOT NULL,
    CONSTRAINT uq_currency_code UNIQUE (code),
    CONSTRAINT chk_currency_code_upper CHECK (code = upper(code)),
    CONSTRAINT chk_currency_name_not_blank CHECK (btrim(name) <> '')
);

--качества оружия
CREATE TABLE IF NOT EXISTS item_quality (
    quality_id           BIGSERIAL PRIMARY KEY,
    code                 TEXT NOT NULL, -- FN BS
    name                 TEXT NOT NULL,
    min_float            NUMERIC(8,6),
    max_float            NUMERIC(8,6),
    CONSTRAINT uq_item_quality_code UNIQUE (code),
    CONSTRAINT uq_item_quality_name UNIQUE (name),
    CONSTRAINT chk_item_quality_code_not_blank CHECK (btrim(code) <> ''),
    CONSTRAINT chk_item_quality_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT chk_item_quality_min_float CHECK (
        min_float IS NULL OR (min_float >= 0 AND min_float <= 1)
    ),
    CONSTRAINT chk_item_quality_max_float CHECK (
        max_float IS NULL OR (max_float >= 0 AND max_float <= 1)
    ),
    CONSTRAINT chk_item_quality_float_range CHECK (
        min_float IS NULL OR max_float IS NULL OR min_float <= max_float
    )
);

--названия пушек
CREATE TABLE IF NOT EXISTS weapon (
    weapon_id            BIGSERIAL PRIMARY KEY,
    name                 TEXT NOT NULL,
    weapon_group         TEXT,
    CONSTRAINT uq_weapon_name UNIQUE (name),
    CONSTRAINT chk_weapon_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT chk_weapon_group_not_blank CHECK (
        weapon_group IS NULL OR btrim(weapon_group) <> ''
    )
);

--скрины пушек
CREATE TABLE IF NOT EXISTS skin (
    skin_id              BIGSERIAL PRIMARY KEY,
    name                 TEXT NOT NULL,
    CONSTRAINT uq_skin_name UNIQUE (name),
    CONSTRAINT chk_skin_name_not_blank CHECK (btrim(name) <> '')
);

--стикеры с пушек
CREATE TABLE IF NOT EXISTS sticker (
    sticker_id           BIGSERIAL PRIMARY KEY,
    name                 TEXT NOT NULL,
    price                NUMERIC(12,2),
    CONSTRAINT chk_sticker_price_nonnegative CHECK (price >= 0),
    CONSTRAINT uq_sticker_name UNIQUE (name),
    CONSTRAINT chk_sticker_name_not_blank CHECK (btrim(name) <> '')
);

--типы событий 
--пока не реализовано
CREATE TABLE IF NOT EXISTS event_type (
    event_type_id        BIGSERIAL PRIMARY KEY, -- купил продал 
    code                 TEXT NOT NULL,
    name                 TEXT NOT NULL,
    CONSTRAINT uq_event_type_code UNIQUE (code),
    CONSTRAINT uq_event_type_name UNIQUE (name),
    CONSTRAINT chk_event_type_code_not_blank CHECK (btrim(code) <> ''),
    CONSTRAINT chk_event_type_name_not_blank CHECK (btrim(name) <> '')
);


CREATE TABLE IF NOT EXISTS container (
    container_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    def_index INTEGER,

    CONSTRAINT uq_container_name UNIQUE (name),
    CONSTRAINT uq_container_def_index UNIQUE (def_index),
    CONSTRAINT chk_container_name_not_blank CHECK (btrim(name) <> '')
);