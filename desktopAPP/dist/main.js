import { app, BrowserWindow, ipcMain } from "electron";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { exec } from "node:child_process";
import { promisify } from "node:util";
const execAsync = promisify(exec);
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const __dirhtml = path.join(__dirname, "pages");
let mainWindow = null;
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1280, height: 800,
        minWidth: 1000, minHeight: 640,
        backgroundColor: "#0f172a",
        webPreferences: {
            preload: path.join(__dirname, "preload.js"),
            contextIsolation: true,
            nodeIntegration: false,
        },
    });
    loadMainPage();
}
const loadMainPage = () => mainWindow?.loadFile(path.join(__dirhtml, "index.html"));
const loadSettingsPage = () => mainWindow?.loadFile(path.join(__dirhtml, "settings.html"));
const loadProjectsPage = () => mainWindow?.loadFile(path.join(__dirhtml, "projects.html"));
const loadMLPage = () => mainWindow?.loadFile(path.join(__dirhtml, "ml.html"));
const loadTasksPage = () => mainWindow?.loadFile(path.join(__dirhtml, "tasks.html"));
// ── Docker IPC ────────────────────────────────────────────────────────────────
ipcMain.handle("docker-status", async () => {
    try {
        const { stdout } = await execAsync("docker ps -a --format json", {
            cwd: process.cwd(),
        });
        const lines = stdout.trim().split("\n").filter(Boolean);
        return lines
            .map((l) => {
            try {
                return JSON.parse(l);
            }
            catch {
                return null;
            }
        })
            .filter(Boolean);
    }
    catch (e) {
        return { error: String(e) };
    }
});
ipcMain.handle("docker-action", async (_event, { action, service }) => {
    const allowed = ["start", "stop", "restart"];
    if (!allowed.includes(action))
        return { error: "Недопустимое действие" };
    if (!service)
        return { error: "Не указан контейнер" };
    try {
        const cmd = `docker ${action} ${service}`;
        const { stdout, stderr } = await execAsync(cmd, { cwd: process.cwd() });
        return { ok: true, stdout, stderr };
    }
    catch (e) {
        return { error: e.message };
    }
});
ipcMain.handle("docker-logs", async (_event, container) => {
    try {
        if (!container)
            return { error: "Не указан контейнер" };
        const { stdout, stderr } = await execAsync(`docker logs --tail 300 ${container}`, { cwd: process.cwd() });
        return { ok: true, stdout, stderr };
    }
    catch (e) {
        return { error: e.message };
    }
});
app.whenReady().then(() => {
    createWindow();
    ipcMain.on("navigate-to-main", loadMainPage);
    ipcMain.on("navigate-to-settings", loadSettingsPage);
    ipcMain.on("navigate-to-projects", loadProjectsPage);
    ipcMain.on("navigate-to-ml", loadMLPage);
    ipcMain.on("navigate-to-tasks", loadTasksPage);
    app.on("activate", () => {
        if (BrowserWindow.getAllWindows().length === 0)
            createWindow();
    });
});
app.on("window-all-closed", () => {
    if (process.platform !== "darwin")
        app.quit();
});
