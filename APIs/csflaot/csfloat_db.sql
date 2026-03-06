CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- CREATE TABLE IF NOT EXISTS skins_items_new (
--     item_id         BIGINT PRIMARY KEY,                   
--     type            TEXT,                    
--     price           NUMERIC(12),                           
--     float_value     REAL,                    
--     icon_url        TEXT,                                                
--     item_name       TEXT,                    
--     wear_name       TEXT,                                   
    
--     created_at      TIMESTAMP DEFAULT NOW(),
--     updated_at      TIMESTAMP
-- );


-- все контейнеры
CREATE TABLE IF NOT EXISTS containers (
  market_hash_name TEXT PRIMARY KEY,
  price NUMERIC(12),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- все предметы по def_index
CREATE TABLE IF NOT EXISTS skins_items (
    item_id         BIGINT PRIMARY KEY,                   
    type            TEXT,                    
    price           NUMERIC(12),                           
    float_value     REAL,                    
    icon_url        TEXT, 
    market_hash_name TEXT,                                               
    item_name       TEXT,                    
    wear_name       TEXT,                                   
    paint_index     NUMERIC(12),
    
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP
);


-- История проданных предметов
CREATE TABLE IF NOT EXISTS avg_price_where_hashname (
  -- id
  market_hash_name TEXT,
  price NUMERIC(12),
  -- еще добавить позиций 

  created_at      TIMESTAMP DEFAULT NOW(),
  updated_at      TIMESTAMP
);

CREATE TABLE IF NOT EXISTS avg_price_by_name (
  market_hash_name TEXT PRIMARY KEY,
  avg_price NUMERIC(12)
  
);

INSERT INTO avg_price_by_name (market_hash_name, avg_price)
SELECT
  market_hash_name,
  AVG(price)      AS avg_price
  -- может быть добавить COUNT 
FROM avg_price_where_hashname
WHERE market_hash_name IS NOT NULL
GROUP BY market_hash_name
ON CONFLICT (market_hash_name)
DO UPDATE SET
  avg_price    = EXCLUDED.avg_price;


-- похожие действующие предметы
CREATE TABLE IF NOT EXISTS similar_items (
  id  BIGINT PRIMARY KEY,      
  market_hash_name TEXT,
  price NUMERIC(12),
  type text
  -- еще добавить позиций 
);

CREATE TABLE IF NOT EXISTS avg_price_similar_items (
  market_hash_name TEXT PRIMARY KEY,
  avg_price NUMERIC(12)
);

INSERT INTO avg_price_similar_items (market_hash_name, avg_price)
SELECT
  market_hash_name,
  AVG(price)      AS avg_price
FROM similar_items
WHERE type != 'auction'
GROUP BY market_hash_name
ON CONFLICT (market_hash_name)
DO UPDATE SET
  avg_price    = EXCLUDED.avg_price;


-- тригеры и тригерный функции
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_set_updated_at ON containers;
CREATE TRIGGER trg_set_updated_at
BEFORE UPDATE ON containers
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_set_updated_skins_items ON skins_items;
CREATE TRIGGER trg_set_updated_skins_items
BEFORE UPDATE ON skins_items
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_set_updated_avg_price_where_hashname ON avg_price_where_hashname;
CREATE TRIGGER trg_set_updated_avg_price_where_hashname
BEFORE UPDATE ON avg_price_where_hashname
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP INDEX IF EXISTS idx_skins_market_hash_name;
DROP INDEX IF EXISTS idx_skins_market_hash_name_trgm;
DROP INDEX IF EXISTS idx_avg_price_by_name_market_hash_name_trgm;

CREATE INDEX IF NOT EXISTS idx_skins_market_hash_name
  ON skins_items (market_hash_name);
CREATE INDEX IF NOT EXISTS idx_skins_market_hash_name_trgm
  ON avg_price_where_hashname USING GIN (market_hash_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_avg_price_by_name_market_hash_name_trgm
  ON avg_price_by_name USING GIN (market_hash_name gin_trgm_ops);

DROP INDEX IF EXISTS idx_similar_items;
DROP INDEX IF EXISTS idx_avg_price_similar_items;

CREATE INDEX IF NOT EXISTS idx_similar_items
  ON similar_items USING GIN (market_hash_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_avg_price_similar_items
  ON avg_price_similar_items USING GIN (market_hash_name gin_trgm_ops);