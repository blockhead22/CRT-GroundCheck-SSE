const { app, BrowserWindow, ipcMain, Menu, screen, Tray } = require('electron')
const path = require('node:path')
const { SidecarManager } = require('./sidecar.cjs')
const { configureDevUserData } = require('./dev-config.cjs')
const { dockBounds } = require('./window.cjs')

let window
let tray
let sidecar
let floating = false
let expanded = false
let alwaysOnTop = true

configureDevUserData(app)

function applyDockBounds() {
  if (!window || floating) return
  const display = screen.getPrimaryDisplay()
  window.setBounds(dockBounds(display.workArea, expanded), true)
}

function createWindow() {
  const bounds = dockBounds(screen.getPrimaryDisplay().workArea)
  window = new BrowserWindow({
    ...bounds,
    minWidth: 420,
    minHeight: 620,
    frame: false,
    show: false,
    alwaysOnTop,
    backgroundColor: '#111614',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })
  if (process.env.NODE_ENV === 'development') {
    window.loadURL('http://127.0.0.1:5175')
  } else {
    window.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }
  window.once('ready-to-show', () => window.show())
  window.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault()
      window.hide()
    }
  })
}

function createTray() {
  tray = new Tray(path.join(__dirname, 'tray-icon.png'))
  tray.setToolTip('Aether Workbench')
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Show Aether', click: () => window.show() },
    { label: 'Hide', click: () => window.hide() },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        app.isQuitting = true
        app.quit()
      },
    },
  ]))
  tray.on('click', () => {
    if (window.isVisible()) window.hide()
    else window.show()
  })
}

app.whenReady().then(async () => {
  sidecar = new SidecarManager()
  sidecar.start()
  createWindow()
  createTray()
  sidecar.on('status', (status) => window?.webContents.send('sidecar:status', status))
  await sidecar.waitUntilReady()
  const smokeExitMs = Number(process.env.AETHER_SMOKE_EXIT_MS || 0)
  if (smokeExitMs > 0) {
    setTimeout(() => {
      app.isQuitting = true
      app.quit()
    }, smokeExitMs)
  }
})

ipcMain.handle('window:set-expanded', (_event, value) => {
  expanded = Boolean(value)
  applyDockBounds()
  return window.getBounds()
})
ipcMain.handle('window:set-floating', (_event, value) => {
  floating = Boolean(value)
  if (floating) {
    window.setBounds({ width: 780, height: 820 }, true)
    window.center()
  } else {
    applyDockBounds()
  }
  return floating
})
ipcMain.handle('window:set-always-on-top', (_event, value) => {
  alwaysOnTop = Boolean(value)
  window.setAlwaysOnTop(alwaysOnTop)
  return alwaysOnTop
})
ipcMain.on('window:minimize', () => window.minimize())
ipcMain.on('window:close', () => window.hide())

app.on('before-quit', () => {
  app.isQuitting = true
  sidecar?.stop()
})
app.on('window-all-closed', (event) => event.preventDefault())
