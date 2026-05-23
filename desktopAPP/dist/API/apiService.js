const BASE_URL = "http://localhost:8080";
const HEADERS = {
    "Content-Type": "application/json",
    "ngrok-skip-browser-warning": "true",
};
async function fetchJSON(path) {
    try {
        const res = await fetch(`${BASE_URL}${path}`, { method: "GET", headers: HEADERS });
        if (!res.ok)
            throw new Error(`HTTP ${res.status}`);
        return (await res.json());
    }
    catch (e) {
        console.error(`[API] ${path}:`, e);
        return null;
    }
}
export const getMLStats = () => fetchJSON("/ml/stats");
export async function trainModel() {
    try {
        const res = await fetch(`${BASE_URL}/ml/train`, {
            method: "POST",
            headers: HEADERS,
        });
        if (!res.ok)
            throw new Error(`HTTP ${res.status}`);
        return (await res.json());
    }
    catch (e) {
        console.error("[API] /ml/train:", e);
        return null;
    }
}
export const getReferences = () => fetchJSON("/stats/references");
export const getCatalog = () => fetchJSON("/stats/catalog");
export const getMarket = () => fetchJSON("/stats/market");
export const getTraders = () => fetchJSON("/stats/traders");
export const getFullStats = () => fetchJSON("/stats");
export const getPriceCoverage = () => fetchJSON("/stats/prices");
