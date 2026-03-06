CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS all_items_steam ( --это все скины 
  hash_name TEXT PRIMARY KEY,
  name TEXT,
  sell_price NUMERIC(12),
  sell_listings NUMERIC(12),
  icon_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_set_updated_at ON all_items_steam;
CREATE TRIGGER trg_set_updated_at
BEFORE UPDATE ON all_items_steam
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP INDEX IF EXISTS idx_agg_name;
DROP INDEX IF EXISTS idx_agg_trgm;

CREATE UNIQUE INDEX idx_agg_name 
  ON all_items_steam(hash_name); -- используется для WHERE hash_name = *
CREATE INDEX idx_agg_trgm 
  ON all_items_steam USING GIN (hash_name gin_trgm_ops); -- используется для WHERE hash_name LIKE = *
