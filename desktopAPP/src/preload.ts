const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld("desktopAPI", {
  appName: "CSFloat Parser",
  version: "0.1.0",
  navigateTo: (page: string) => ipcRenderer.send(`navigate-to-${page}`),
  // Docker управление
  dockerAction: (action: string, service: string) => 
    ipcRenderer.invoke("docker-action", { action, service }),
  dockerStatus: () => ipcRenderer.invoke("docker-status"),
  dockerLogs: (service: string) => ipcRenderer.invoke("docker-logs", service),
});