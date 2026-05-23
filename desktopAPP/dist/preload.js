"use strict";
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld("desktopAPI", {
    appName: "CSFloat Parser",
    version: "0.1.0",
    navigateTo: (page) => ipcRenderer.send(`navigate-to-${page}`),
    // Docker управление
    dockerAction: (action, service) => ipcRenderer.invoke("docker-action", { action, service }),
    dockerStatus: () => ipcRenderer.invoke("docker-status"),
    dockerLogs: (service) => ipcRenderer.invoke("docker-logs", service),
});
