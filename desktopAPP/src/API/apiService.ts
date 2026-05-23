const BASE_URL = "http://localhost:8080";

const HEADERS = {
  "Content-Type": "application/json",
  "ngrok-skip-browser-warning": "true",
};

async function fetchJSON<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${BASE_URL}${path}`, { method: "GET", headers: HEADERS });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as T;
  } catch (e) {
    console.error(`[API] ${path}:`, e);
    return null;
  }
}

export interface ReferencesData {
  weapons: number;
  skins: number;
  stickers: number;
  qualities: number;
  event_types: number;
  platforms: number;
  currencies: number;
  containers: number;
}

export interface CatalogData {
  game_items: number;
  item_instances: number;
  items_with_float: number;
  items_with_stickers: number;
  stattrak_items: number;
  souvenir_items: number;
}

export interface MarketData {
  listings: {
    total: number;
    active: number;
    sold: number;
    not_listed: number;
  };
  price_history_records: number;
  market_snapshots: number;
  avg_price_usd: number | null;
  max_price_usd: number | null;
}

export interface TradersData {
  unique_traders: number;
  platform_accounts: number;
  inventory_snapshots: number;
  inventory_item_snapshots: number;
  actions: {
    total: number;
    listed: number;
    sold: number;
    not_listed: number;
  };
}

export interface PriceCoverageData {
  csfloat: {
    items_with_price: number;
    total_items: number;
    coverage_pct: number;
    last_updated: string | null;
  };
  steam: {
    game_items_with_history: number;
    total_game_items: number;
    count_item_have_steam_price: Number;
    steam_total: Number;
    coverage_pct: number;
    last_updated: string | null;
  };
    cross_platform: {            // ← новое
    game_items_on_both: number;
    total_game_items: number;
    coverage_pct: number;
  };
}

export interface StatsData {
  summary: {
    unique_items: number;
    total_listings: number;
    sold_listings: number;
    unique_traders: number;
    total_actions: number;
  };
  ml_readiness: {
    ml_ready_samples: number;
    can_start_ml: boolean;
    level: string;
    progress_to_next_pct: number;
    next_target: number;
    sold_ratio_pct: number;
    recommendation: string;
  };
}

export interface MLStatsData {
  db: {
    unique_items: number;
    total_listings: number;
    sold_listings: number;
    ml_ready_samples: number;
  };
  ml_readiness: {
    level: string;
    progress_pct: number;
    next_target: number;
    recommendation: string;
    sold_ratio_pct: number;
    sold_ok: boolean;
    can_start_ml: boolean;
  };
  model: {
    trained: boolean;
    mae_usd: number | null;
    mape_pct: number | null;
    r2: number | null;
    samples_eval: number | null;
    quality_label: string | null;
  };
}

export interface TrainResult {
  success: boolean;
  error: string | null;
  weapons_trained: number;
  weapons_skipped: number;
  results: {
    weapon_id: number;
    mae_usd: number;
    mape_pct: number;
    train_samples: number;
    test_samples: number;
    model_path: string;
    success: boolean;
    error: string | null;
  }[];
}

export const getMLStats = () => fetchJSON<MLStatsData>("/ml/stats");

export async function trainModel(): Promise<TrainResult | null> {
  try {
    const res = await fetch(`${BASE_URL}/ml/train`, {
      method: "POST",
      headers: HEADERS,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as TrainResult;
  } catch (e) {
    console.error("[API] /ml/train:", e);
    return null;
  }
}

export const getReferences  = () => fetchJSON<ReferencesData>("/stats/references");
export const getCatalog     = () => fetchJSON<CatalogData>("/stats/catalog");
export const getMarket      = () => fetchJSON<MarketData>("/stats/market");
export const getTraders     = () => fetchJSON<TradersData>("/stats/traders");
export const getFullStats   = () => fetchJSON<StatsData>("/stats");
export const getPriceCoverage = () => fetchJSON<PriceCoverageData>("/stats/prices");