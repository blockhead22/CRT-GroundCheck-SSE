/**
 * Preload script — secure bridge between Electron main process and renderer.
 * Exposes a limited API via contextBridge so the React app can interact
 * with native features without direct Node.js access.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('aether', {
  // Backend status
  onBackendStatus: (callback) => {
    ipcRenderer.on('backend:status', (_event, status) => callback(status));
  },

  // Backend logs
  onBackendLog: (callback) => {
    ipcRenderer.on('backend:log', (_event, log) => callback(log));
  },

  // Request backend restart
  restartBackend: () => ipcRenderer.send('backend:restart'),

  // Window controls
  toggleWindow: () => ipcRenderer.send('app:toggle'),
  minimizeToTray: () => ipcRenderer.send('app:minimize-to-tray'),
  minimize: () => ipcRenderer.send('window:minimize'),
  maximize: () => ipcRenderer.send('window:maximize'),
  close: () => ipcRenderer.send('window:close'),

  // Clipboard monitoring
  onClipboardCapture: (callback) => {
    ipcRenderer.on('clipboard:capture', (_event, text) => callback(text));
  },
  toggleClipboard: (enabled) => ipcRenderer.send('clipboard:toggle', enabled),
  rememberClipboard: (text) => ipcRenderer.send('clipboard:remember', text),

  // File drop
  onFileDrop: (callback) => {
    ipcRenderer.on('file:dropped', (_event, result) => callback(result));
  },
  _sendFileIngest: (filePath) => ipcRenderer.send('file:ingest', filePath),

  // Platform info
  platform: process.platform,
  isElectron: true,
});
