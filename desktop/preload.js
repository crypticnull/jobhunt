// The only bridge. contextIsolation stays on and the renderer gets three verbs
// rather than a node runtime, because the views it hosts render text written by
// strangers and a job posting must never be one step from the file system.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("jobhunt", {
  onGo: (cb) => ipcRenderer.on("go", (_e, where) => cb(where)),
  consoleState: () => ipcRenderer.invoke("console-state"),
  startSite: () => ipcRenderer.invoke("start-site"),
  siteUp: () => ipcRenderer.invoke("site-up"),
});
