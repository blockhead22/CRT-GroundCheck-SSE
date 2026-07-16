const { app, BrowserWindow, ipcMain, Menu, screen, Tray } = require('electron')
const path = require('node:path')
const { SidecarManager } = require('./sidecar.cjs')
const { configureDevUserData } = require('./dev-config.cjs')
const { buildSpellcheckContextMenuTemplate } = require('./context-menu.cjs')
const { dockBounds } = require('./window.cjs')
const { AppBarManager } = require('./appbar.cjs')

let window
let tray
let sidecar
let floating = false
let expanded = false
let alwaysOnTop = true
const appBar = new AppBarManager()

configureDevUserData(app)

function releaseDockReservation() {
  if (!window) return
  try {
    appBar.release(window)
  } catch (error) {
    console.warn('Could not release the Windows AppBar reservation:', error.message)
  }
}

function applyDockBounds() {
  if (!window || window.isDestroyed()) return
  if (floating || !window.isVisible() || window.isMinimized()) {
    releaseDockReservation()
    return
  }
  const display = screen.getDisplayMatching(window.getBounds())
  const desired = dockBounds(display.bounds, expanded)
  try {
    const reserved = appBar.reserve(window, display.bounds, desired.width)
    window.setBounds(reserved || dockBounds(display.workArea, expanded), true)
  } catch (error) {
    console.warn('Could not reserve the Windows work area:', error.message)
    window.setBounds(dockBounds(display.workArea, expanded), true)
  }
}

function showWindow() {
  window.show()
}

function hideWindow() {
  releaseDockReservation()
  window.hide()
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
      spellcheck: true,
    },
  })
  if (process.env.NODE_ENV === 'development') {
    window.loadURL('http://127.0.0.1:5175')
  } else {
    window.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }
  window.once('ready-to-show', showWindow)
  window.on('show', applyDockBounds)
  window.on('hide', releaseDockReservation)
  window.on('minimize', releaseDockReservation)
  window.on('restore', applyDockBounds)
  window.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault()
      hideWindow()
    }
  })
}

function createTray() {
  tray = new Tray(path.join(__dirname, 'tray-icon.png'))
  tray.setToolTip('Aether Workbench')
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Show Aether', click: showWindow },
    { label: 'Hide', click: hideWindow },
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
    if (window.isVisible()) hideWindow()
    else showWindow()
  })
}

function installContextMenu() {
  app.on('web-contents-created', (_event, contents) => {
    contents.on('context-menu', (_menuEvent, params) => {
      const template = buildSpellcheckContextMenuTemplate(params, contents)
      if (template.length === 0) return
      Menu.buildFromTemplate(template).popup({
        window: BrowserWindow.fromWebContents(contents),
      })
    })
  })
}

app.whenReady().then(async () => {
  installContextMenu()
  sidecar = new SidecarManager()
  sidecar.start()
  createWindow()
  createTray()
  screen.on('display-metrics-changed', applyDockBounds)
  screen.on('display-added', applyDockBounds)
  screen.on('display-removed', applyDockBounds)
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
    releaseDockReservation()
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
ipcMain.on('window:close', hideWindow)

app.on('before-quit', () => {
  app.isQuitting = true
  releaseDockReservation()
  sidecar?.stop()
})
app.on('window-all-closed', (event) => event.preventDefault())
