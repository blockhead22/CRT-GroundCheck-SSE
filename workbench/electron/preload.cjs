const { contextBridge, ipcRenderer } = require('electron')

const sidecarApiArgument = process.argv.find((argument) =>
  argument.startsWith('--aether-sidecar-api-base='),
)
if (!sidecarApiArgument) {
  throw new Error('Electron did not provide the Aether sidecar API base')
}
const sidecarApiBase = sidecarApiArgument.slice(sidecarApiArgument.indexOf('=') + 1)

contextBridge.exposeInMainWorld('aetherDesktop', {
  apiBase: sidecarApiBase,
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
