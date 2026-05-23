--стикеры на конректном предмете
CREATE TABLE IF NOT EXISTS item_instance_sticker (
    item_instance_sticker_id BIGSERIAL PRIMARY KEY,
    item_instance_id         BIGINT NOT NULL,
    sticker_id               BIGINT NOT NULL,
    slot_no                  SMALLINT NOT NULL,
    wear_value               NUMERIC(8,6),

    CONSTRAINT fk_item_instance_sticker_item_instance
        FOREIGN KEY (item_instance_id)
        REFERENCES item_instance (item_instance_id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,

    CONSTRAINT fk_item_instance_sticker_sticker
        FOREIGN KEY (sticker_id)
        REFERENCES sticker (sticker_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT uq_item_instance_sticker_item_slot
        UNIQUE (item_instance_id, slot_no),

    CONSTRAINT chk_item_instance_sticker_slot_no_range
        CHECK (slot_no BETWEEN 1 AND 5),

    CONSTRAINT chk_item_instance_sticker_wear_value_range
        CHECK (wear_value IS NULL OR (wear_value >= 0 AND wear_value <= 1))
);

--атрибуты на конкретном предмете
CREATE TABLE IF NOT EXISTS item_instance_attribute (
    item_instance_attribute_id BIGSERIAL PRIMARY KEY,
    item_instance_id           BIGINT NOT NULL,
    attr_name                  TEXT NOT NULL,
    attr_value                 TEXT NOT NULL,

    CONSTRAINT fk_item_instance_attribute_item_instance
        FOREIGN KEY (item_instance_id)
        REFERENCES item_instance (item_instance_id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,

    CONSTRAINT uq_item_instance_attribute_item_attr
        UNIQUE (item_instance_id, attr_name),

    CONSTRAINT chk_item_instance_attribute_attr_name_not_blank
        CHECK (btrim(attr_name) <> ''),

    CONSTRAINT chk_item_instance_attribute_attr_value_not_blank
        CHECK (btrim(attr_value) <> '')
);