import {
   getFullStats, 
   getReferences, 
   getCatalog, 
   getMarket, 
   getTraders, 
   getMLStats, 
   trainModel,
   getPriceCoverage,
  } from "./API/apiService.js";
import type { NavItem } from "./API/type";

const navItems: NavItem[] = [
  { id: "main",     label: "Главная",   icon: "⌂" },
  { id: "projects", label: "Проекты",   icon: "▣" },
  { id: "tasks",    label: "Задачи",    icon: "✓" },
  { id: "ml",       label: "ML",        icon: "🤖" }, 
  { id: "settings", label: "Настройки", icon: "⚙" },
];

function renderNav(items: NavItem[]): void {
  const nav = document.getElementById("nav");
  if (!nav) return;
  nav.innerHTML = "";
  const currentPath = window.location.pathname;
  items.forEach((item) => {
    const btn = document.createElement("button");
    btn.className = "nav-button";
    if (
      currentPath.includes(`${item.id}.html`) ||
      (item.id === "main" && currentPath.includes("index.html"))
    ) btn.classList.add("active");
    btn.innerHTML = `<span class="nav-icon">${item.icon}</span><span>${item.label}</span>`;
    btn.addEventListener("click", () => window.desktopAPI.navigateTo(item.id));
    nav.appendChild(btn);
  });
}

function set(id: string, value: string | number | null | undefined): void {
  const el = document.getElementById(id);
  if (el) el.textContent = value == null ? "—" : String(value);
}

function setProgress(id: string, pct: number): void {
  const el = document.getElementById(id) as HTMLElement | null;
  if (el) el.style.width = `${Math.min(100, pct)}%`;
}

// ── API статус ────────────────────────────────────────────────────────────────
let apiOnline = false;

function setApiStatus(online: boolean): void {
  apiOnline = online;
  const dot  = document.getElementById("status-dot");
  const text = document.getElementById("status-text");
  if (!dot || !text) return;
  if (online) {
    dot.className  = "status-dot dot-online";
    text.textContent = "API подключено";
  } else {
    dot.className  = "status-dot dot-offline";
    text.textContent = "API не включено";
  }
}

// ── Главная страница ──────────────────────────────────────────────────────────
async function loadDashboard(): Promise<void> {
  const stats = await getFullStats();

  if (!stats) {
    setApiStatus(false);
    // Сбрасываем карточки в "нет данных"
    ["card-unique-items","card-total-listings","card-sold-listings",
     "card-unique-traders","card-total-actions"].forEach(id => set(id, "—"));
    return;
  }

  setApiStatus(true);

  set("card-unique-items",   stats.summary.unique_items.toLocaleString("ru-RU"));
  set("card-total-listings", stats.summary.total_listings.toLocaleString("ru-RU"));
  set("card-sold-listings",  stats.summary.sold_listings.toLocaleString("ru-RU"));
  set("card-unique-traders", stats.summary.unique_traders.toLocaleString("ru-RU"));
  set("card-total-actions",  stats.summary.total_actions.toLocaleString("ru-RU"));

  const [refs, catalog, market, traders, prices] = await Promise.all([
    getReferences(),
    getCatalog(),
    getMarket(),
    getTraders(),
    getPriceCoverage(),  
  ]);

  if (refs) {
    set("ref-weapons",   refs.weapons);
    set("ref-skins",     refs.skins);
    set("ref-stickers",  refs.stickers);
    set("ref-qualities", refs.qualities);
  }
  if (catalog) {
    set("cat-game-items",    catalog.game_items);
    set("cat-instances",     catalog.item_instances);
    set("cat-with-float",    catalog.items_with_float);
    set("cat-with-stickers", catalog.items_with_stickers);
    set("cat-stattrak",      catalog.stattrak_items);
    set("cat-souvenir",      catalog.souvenir_items);
  }
  if (market) {
    set("mkt-total",   market.listings.total);
    set("mkt-active",  market.listings.active);
    set("mkt-sold",    market.listings.sold);
    set("mkt-history", market.price_history_records);
    set("mkt-avg",     market.avg_price_usd != null ? `$${market.avg_price_usd}` : "—");
    set("mkt-max",     market.max_price_usd  != null ? `$${market.max_price_usd}` : "—");
  }
  if (traders) {
    set("tr-traders",   traders.platform_accounts);
    set("tr-snapshots", traders.inventory_snapshots);
    set("tr-listed",    traders.actions.listed);
    set("tr-sold",      traders.actions.sold);
    set("tr-unlisted",  traders.actions.not_listed);
  }
  if (prices) {
    set("price-cf-with",   prices.csfloat.items_with_price.toLocaleString("ru-RU"));
    set("price-cf-total",  prices.csfloat.total_items.toLocaleString("ru-RU"));
    set("price-cf-pct",    `${prices.csfloat.coverage_pct}%`);
    set("price-cf-updated",                                              // ← добавили
    prices.csfloat.last_updated
      ? new Date(prices.csfloat.last_updated).toLocaleString("ru-RU", { timeZone: "Europe/Minsk" })
      : "Никогда"
  );

    set("price-st-with",   prices.steam.game_items_with_history.toLocaleString("ru-RU"));
    set("price-st-total",  prices.steam.total_game_items.toLocaleString("ru-RU"));
    set("price-st-count",  Number(prices.steam.count_item_have_steam_price).toLocaleString("ru-RU"));
    set("price-st-inv",    Number(prices.steam.steam_total).toLocaleString("ru-RU"));
    set("price-st-pct",    `${prices.steam.coverage_pct}%`);
    set("price-st-updated",
      prices.steam.last_updated
        ? new Date(prices.steam.last_updated).toLocaleString("ru-RU", { timeZone: "Europe/Minsk" })
        : "Никогда"
    );

    set("price-cross-both",  prices.cross_platform.game_items_on_both.toLocaleString("ru-RU"));
    set("price-cross-total", prices.cross_platform.total_game_items.toLocaleString("ru-RU"));
    set("price-cross-pct",   `${prices.cross_platform.coverage_pct}%`);
  }

  const ml = stats.ml_readiness;
  set("ml-samples",       ml.ml_ready_samples.toLocaleString("ru-RU"));
  set("ml-level",         ml.level);
  set("ml-target",        ml.next_target.toLocaleString("ru-RU"));
  set("ml-sold-ratio",    `${ml.sold_ratio_pct}%`);
  set("ml-rec",           ml.recommendation);
  set("ml-progress-label", `${ml.progress_to_next_pct}%`);
  setProgress("ml-progress-bar", ml.progress_to_next_pct);

  const badge = document.getElementById("ml-badge");
  if (badge) {
    badge.textContent = ml.can_start_ml ? "✅ Можно запускать" : "⏳ Ещё не готово";
    badge.className   = `ml-badge ${ml.can_start_ml ? "badge-ready" : "badge-wait"}`;
  }
}

// ── Страница проектов (Docker) ─────────────────────────────────────────────────
async function loadDockerPage(): Promise<void> {
  const container = document.getElementById("docker-list");
  if (!container) return;

  container.innerHTML = `<div class="docker-loading">Получение статуса...</div>`;

  const result = await window.desktopAPI.dockerStatus();

  if (!result || (result as any).error) {
    container.innerHTML = `<div class="docker-error">⚠️ Docker недоступен: ${(result as any)?.error ?? "нет ответа"}</div>`;
    return;
  }

  const services: any[] = Array.isArray(result) ? result : [];

  if (services.length === 0) {
    container.innerHTML = `<div class="docker-empty">Нет запущенных сервисов. Запустите <code>docker compose up -d</code></div>`;
    return;
  }

  container.innerHTML = services.map(s => {
    const running = (s.State ?? s.Status ?? "").toLowerCase().includes("running");
    const rawName = s.Names ?? s.Name ?? s.Service ?? s.ContainerName ?? "unknown";
    const shortName = Array.isArray(rawName)
      ? rawName[0]
      : String(rawName).replace(/^\//, "");
    const state   = s.State ?? s.Status ?? "unknown";
    const ports   = (s.Publishers ?? []).map((p: any) => `${p.PublishedPort}→${p.TargetPort}`).join(", ") || "—";
    return `
      <div class="docker-row" data-service="${shortName}">
        <div class="docker-info">
          <span class="docker-dot ${running ? "dot-online" : "dot-offline"}"></span>
          <div>
            <div class="docker-name">${shortName}</div>
            <div class="docker-state">${state} ${ports !== "—" ? `· порты: ${ports}` : ""}</div>
          </div>
        </div>
        <div class="docker-actions">
          ${running
            ? `<button class="docker-btn btn-stop"  onclick="dockerAction('stop','${shortName}')">■ Стоп</button>
               <button class="docker-btn btn-restart" onclick="dockerAction('restart','${shortName}')">↺ Рестарт</button>`
            : `<button class="docker-btn btn-start" onclick="dockerAction('start','${shortName}')">▶ Старт</button>`
          }
        </div>
      </div>`;
  }).join("");
}

(window as any).showDockerLogs = async (service: string) => {
  const box = document.getElementById("docker-logs");
  if (box) box.textContent = "Загрузка логов...";

  const result = await window.desktopAPI.dockerLogs(service);

  if (!box) return;

  if (!result || (result as any).error) {
    box.textContent = `Ошибка: ${(result as any)?.error ?? "нет ответа"}`;
    return;
  }

  box.textContent = result.stdout || "Логи пустые";
};

(window as any).dockerAction = async (action: string, service: string) => {
  const btn = document.querySelector(`[data-service="${service}"] button`) as HTMLButtonElement | null;
  if (btn) { btn.disabled = true; btn.textContent = "..."; }
  await window.desktopAPI.dockerAction(action, service);
  await loadDockerPage(); // перерисовываем
};

(window as any).dockerActionAll = async (action: string) => {
  const allBtns = document.querySelectorAll<HTMLButtonElement>(".docker-btn");
  allBtns.forEach(b => { b.disabled = true; });
  await window.desktopAPI.dockerAction(action, "");
  await loadDockerPage();
};

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  renderNav(navItems);

  const versionText = document.getElementById("version-text");
  if (window.desktopAPI?.version && versionText)
    versionText.textContent = `v${window.desktopAPI.version}`;

  if (document.getElementById("card-unique-items")) {
    setApiStatus(false);
    loadDashboard();
    setInterval(loadDashboard, 30_000);
  }

  if (document.getElementById("docker-list")) {
    loadDockerPage();
    setInterval(loadDockerPage, 15_000);
  }

  // ← добавь это
  if (document.getElementById("ml2-samples")) {
    setApiStatus(false);
    loadMLPage();
    setInterval(loadMLPage, 60_000);
  }
});

async function loadMLPage(): Promise<void> {
  const stats = await getMLStats();

  if (!stats) {
    setApiStatus(false);
    set("ml2-samples", "—");
    set("ml2-level", "—");
    set("ml2-rec", "API недоступно");
    return;
  }

  setApiStatus(true);

  // Готовность данных
  set("ml2-samples",    stats.db.ml_ready_samples.toLocaleString("ru-RU"));
  set("ml2-level",      stats.ml_readiness.level);
  set("ml2-target",     stats.ml_readiness.next_target.toLocaleString("ru-RU"));
  set("ml2-sold-ratio", `${stats.ml_readiness.sold_ratio_pct}%`);
  set("ml2-rec",        stats.ml_readiness.recommendation);
  set("ml2-progress-label", `${stats.ml_readiness.progress_pct}%`);
  setProgress("ml2-progress-bar", stats.ml_readiness.progress_pct);

  const badge = document.getElementById("ml2-badge");
  if (badge) {
    badge.textContent = stats.ml_readiness.can_start_ml ? "✅ Можно запускать" : "⏳ Ещё не готово";
    badge.className = `ml-badge ${stats.ml_readiness.can_start_ml ? "badge-ready" : "badge-wait"}`;
  }

  // Метрики модели
  const modelBlock = document.getElementById("ml2-model-block");
  if (modelBlock) {
    if (stats.model.trained) {
      modelBlock.innerHTML = `
        <div class="stat-row"><span class="stat-label">Качество</span><span class="stat-value">${stats.model.quality_label}</span></div>
        <div class="stat-row"><span class="stat-label">MAE (ошибка в $)</span><span class="stat-value">$${stats.model.mae_usd}</span></div>
        <div class="stat-row"><span class="stat-label">MAPE (ошибка в %)</span><span class="stat-value">${stats.model.mape_pct}%</span></div>
        <div class="stat-row"><span class="stat-label">R² (точность)</span><span class="stat-value">${stats.model.r2}</span></div>
        <div class="stat-row"><span class="stat-label">Проверено на</span><span class="stat-value">${stats.model.samples_eval?.toLocaleString("ru-RU")} скинах</span></div>
      `;
    } else {
      modelBlock.innerHTML = `<div class="ml-rec">Модель ещё не обучена. Нажми кнопку ниже.</div>`;
    }
  }
  const trainBtn = document.getElementById("ml2-train-btn") as HTMLButtonElement | null;
  if (trainBtn && !trainBtn.dataset.bound) {
    trainBtn.dataset.bound = "1";   // не вешаем обработчик дважды
    trainBtn.addEventListener("click", handleTrainClick);
  }
}

async function handleTrainClick(): Promise<void> {
  const btn = document.getElementById("ml2-train-btn") as HTMLButtonElement | null;
  const log = document.getElementById("ml2-train-log");

  if (btn) { btn.disabled = true; btn.textContent = "⏳ Обучение..."; }
  if (log) { log.textContent = "Запускаем обучение модели..."; log.style.color = "#94a3b8"; }

  const result = await trainModel();

  if (btn) { btn.disabled = false; btn.textContent = "🚀 Запустить обучение"; }

  if (!result) {
    if (log) { log.textContent = "❌ Ошибка: API недоступно"; log.style.color = "#ef4444"; }
    return;
  }

  if (!result.success) {
    if (log) { log.textContent = `❌ Ошибка: ${result.error}`; log.style.color = "#ef4444"; }
    return;
  }

  if (log) {
    const total_train = result.results.reduce((sum, r) => sum + r.train_samples, 0);
    const total_test = result.results.reduce((sum, r) => sum + r.test_samples, 0);
    const avg_mae = (result.results.reduce((sum, r) => sum + r.mae_usd, 0) / result.results.length).toFixed(2);
    const avg_mape = (result.results.reduce((sum, r) => sum + r.mape_pct, 0) / result.results.length).toFixed(1);

    log.textContent = [
      `✅ Обучение завершено!`,
      `Оружий: ${result.weapons_trained}`,
      `Пропущено: ${result.weapons_skipped}`,
      `Средний MAE: $${avg_mae}`,
      `Средний MAPE: ${avg_mape}%`,
      `Обучающих: ${total_train.toLocaleString("ru-RU")}`,
      `Тестовых: ${total_test.toLocaleString("ru-RU")}`,
    ].join("  ·  ");
  }

  await loadMLPage();  // обновляем метрики
}


(window as any).startTraining = async () => {
  const btn = document.getElementById("ml2-train-btn") as HTMLButtonElement | null;
  const log = document.getElementById("ml2-train-log");

  if (btn) { btn.disabled = true; btn.textContent = "⏳ Обучение..."; }
  if (log) log.textContent = "Запускаем обучение модели...";

  const result = await trainModel();

  if (btn) { btn.disabled = false; btn.textContent = "🚀 Запустить обучение"; }

  if (!result) {
    if (log) log.textContent = "❌ Ошибка: API недоступно";
    return;
  }

  if (!result.success) {
    if (log) log.textContent = `❌ Ошибка: ${result.error}`;
    return;
  }

  if (log) {
    const total_train = result.results.reduce((sum, r) => sum + r.train_samples, 0);
    const total_test = result.results.reduce((sum, r) => sum + r.test_samples, 0);
    const avg_mae = (result.results.reduce((sum, r) => sum + r.mae_usd, 0) / result.results.length).toFixed(2);
    const avg_mape = (result.results.reduce((sum, r) => sum + r.mape_pct, 0) / result.results.length).toFixed(1);

    log.textContent = [
      `✅ Обучение завершено!`,
      `Оружий: ${result.weapons_trained}`,
      `Пропущено: ${result.weapons_skipped}`,
      `Средний MAE: $${avg_mae}`,
      `Средний MAPE: ${avg_mape}%`,
      `Обучающих: ${total_train.toLocaleString("ru-RU")}`,
      `Тестовых: ${total_test.toLocaleString("ru-RU")}`,
    ].join("  ·  ");
  }

  await loadMLPage(); // обновляем метрики после обучения
};


