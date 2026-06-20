const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('aetherDesktop', {
  setExpanded: (value) => ipcRenderer.invoke('window:set-expanded', value),
  setFloating: (value) => ipcRenderer.invoke('window:set-floating', value),
  setAlwaysOnTop: (value) => ipcRenderer.invoke('window:set-always-on-top', value),
  minimize: () => ipcRenderer.send('window:minimize'),
  close: () => ipcRenderer.send('window:close'),
  onSidecarStatus: (callback) => {
    const listener = (_event, status) => callback(status)
    ipcRenderer.on('sidecar:status', listener)
    return () => ipcRenderer.removeListener('sidecar:status', listener)
  },
})
