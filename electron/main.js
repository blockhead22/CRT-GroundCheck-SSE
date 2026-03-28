/**
 * Aether Desktop — Main Process
 *
 * Orchestrates: backend lifecycle, window management, system tray, global hotkey.
 */

const {
  app,
  BrowserWindow,
  Menu,
  globalShortcut,
  ipcMain,
  shell,
} = require('electron');
const path = require('path');
const http = require('http');
const { BackendManager } = require('./backend');
const { AetherTray } = require('./tray');

// ── Config ────────────────────────────────────────────────────────────

const IS_DEV = process.env.NODE_ENV === 'development';
const REPO_ROOT = path.resolve(__dirname, '..');
const BACKEND_PORT = parseInt(process.env.PORT || '8000', 10);
const BACKEND_HOST = process.env.CRT_HOST || '127.0.0.1';
const FRONTEND_DEV_URL = `http://localhost:5173`;
// In production, we load the frontend through the backend (which serves dist/)
// This avoids file:// protocol issues with absolute asset paths
const FRONTEND_PROD_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;

// ── State ─────────────────────────────────────────────────────────────

let mainWindow = null;
let tray = null;
let backendManager = null;
let frontendLoaded = false;

// ── Window ────────────────────────────────────────────────────────────

function createWindow() {
  // Remove default menu bar
  Menu.setApplicationMenu(null);

  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 480,
    minHeight: 600,
    title: 'Aether',
    show: false,
    frame: false,
    titleBarStyle: 'hidden',
    // Native window controls overlaid on frameless window (Windows/Linux)
    ...(process.platform !== 'darwin' ? {
      titleBarOverlay: {
        color: '#0e0d0b',
        symbolColor: '#ffffff66',
        height: 36,
      },
    } : {}),
    // macOS: traffic lights inset
    ...(process.platform === 'darwin' ? {
      trafficLightPosition: { x: 12, y: 12 },
    } : {}),
    backgroundColor: '#0b0f1a',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  // Hide instead of close (tray keeps running)
  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  // Open external links in default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Inject frameless window styles after page loads
  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow.webContents.insertCSS(`
      /* Drag region — the top bar area becomes the window handle */
      body::before {
        content: '';
        display: block;
        position: fixed;
        top: 0;
        left: 0;
        right: 140px; /* Leave space for window controls */
        height: 36px;
        -webkit-app-region: drag;
        z-index: 9998;
        pointer-events: none;
      }

      /* Make all interactive elements in the top bar clickable (not draggable) */
      button, a, input, select, [role="button"], [onclick],
      .search-input, nav a, .sidebar a, .sidebar button {
        -webkit-app-region: no-drag;
      }

      /* Electron: no-drag on the sidebar so it stays interactive */
      [class*="sidebar"], [class*="Sidebar"] {
        -webkit-app-region: no-drag;
      }
    `);

    // Inject JS to pad the topbar for window controls
    mainWindow.webContents.executeJavaScript(`
      (function padTopbar() {
        document.body.classList.add('electron-app');

        function findAndPadTopbar() {
          // The topbar is a flex row with justify-between and a border-bottom
          const candidates = document.querySelectorAll('div');
          for (const el of candidates) {
            const style = el.getAttribute('style') || '';
            const cls = el.className || '';
            if (
              style.includes('border-bottom') &&
              cls.includes('flex') &&
              cls.includes('items-center') &&
              cls.includes('justify-between')
            ) {
              el.style.paddingRight = '140px';
              return true;
            }
          }
          return false;
        }

        // Retry until React renders
        let attempts = 0;
        const interval = setInterval(() => {
          if (findAndPadTopbar() || ++attempts > 20) clearInterval(interval);
        }, 250);
      })();
    `);
  });

  return mainWindow;
}

function loadFrontend() {
  if (!mainWindow || frontendLoaded) return;
  frontendLoaded = true;

  if (IS_DEV) {
    console.log(`[main] Loading dev frontend: ${FRONTEND_DEV_URL}`);
    mainWindow.loadURL(FRONTEND_DEV_URL);
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    // Load frontend through the backend server — avoids file:// path issues
    console.log(`[main] Loading production frontend: ${FRONTEND_PROD_URL}`);
    mainWindow.loadURL(FRONTEND_PROD_URL);
  }
}

// ── Backend ───────────────────────────────────────────────────────────

/** Check if backend is already running externally */
function checkExistingBackend() {
  return new Promise((resolve) => {
    const req = http.get(
      { hostname: BACKEND_HOST, port: BACKEND_PORT, path: '/health', timeout: 2000 },
      (res) => { resolve(res.statusCode === 200); res.resume(); }
    );
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
  });
}

async function startBackend() {
  backendManager = new BackendManager(REPO_ROOT);

  // Forward status to renderer
  backendManager.on('status', (status) => {
    console.log(`[main] Backend status: ${status}`);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('backend:status', status);
    }

    // Load frontend once backend is healthy
    if (status === 'healthy') {
      loadFrontend();
    }
  });

  // Forward logs to renderer
  backendManager.on('log', (log) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('backend:log', log);
    }
  });

  // Check if backend is already running (user started it manually)
  const alreadyRunning = await checkExistingBackend();
  if (alreadyRunning) {
    console.log('[main] Backend already running on port ' + BACKEND_PORT + ', attaching...');
    backendManager.healthy = true;
    backendManager.emit('status', 'healthy');
    // Start health monitoring without spawning
    backendManager.startHealthCheck();
  } else {
    backendManager.start();
  }
}

// ── IPC Handlers ──────────────────────────────────────────────────────

function setupIPC() {
  ipcMain.on('backend:restart', () => {
    console.log('[main] Backend restart requested');
    backendManager.restart();
  });

  ipcMain.on('app:toggle', () => {
    if (mainWindow.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow.show();
      mainWindow.focus();
    }
  });

  ipcMain.on('app:minimize-to-tray', () => {
    mainWindow.hide();
  });

  ipcMain.on('window:minimize', () => {
    mainWindow.minimize();
  });

  ipcMain.on('window:maximize', () => {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
  });

  ipcMain.on('window:close', () => {
    mainWindow.close();
  });
}

// ── Global Hotkey ─────────────────────────────────────────────────────

function registerHotkey() {
  const accelerator = process.platform === 'darwin' ? 'Cmd+Space' : 'Ctrl+Space';

  const hotkeyAction = () => {
    if (!mainWindow) return;
    if (mainWindow.isVisible() && mainWindow.isFocused()) {
      mainWindow.hide();
    } else {
      mainWindow.show();
      mainWindow.focus();
    }
  };

  const registered = globalShortcut.register(accelerator, hotkeyAction);

  if (registered) {
    console.log(`[main] Global hotkey registered: ${accelerator}`);
  } else {
    // Ctrl+Space might conflict with IME — try Alt+Space
    const fallback = process.platform === 'darwin' ? 'Option+Space' : 'Alt+Space';
    const fallbackOk = globalShortcut.register(fallback, hotkeyAction);
    if (fallbackOk) {
      console.log(`[main] Fallback hotkey registered: ${fallback}`);
    } else {
      console.warn('[main] Could not register any global hotkey');
    }
  }
}

// ── App Lifecycle ─────────────────────────────────────────────────────

// Single instance lock — only one Aether at a time
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  console.log('[main] Another instance is running, quitting');
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

app.whenReady().then(async () => {
  console.log('[main] Aether Desktop starting...');
  console.log(`[main] Repo root: ${REPO_ROOT}`);
  console.log(`[main] Mode: ${IS_DEV ? 'development' : 'production'}`);

  // 1. Create window with loading screen
  createWindow();

  mainWindow.loadURL(`data:text/html,${encodeURIComponent(`<!DOCTYPE html>
<html><head><style>
  body {
    margin: 0; display: flex; align-items: center; justify-content: center;
    height: 100vh; background: #0a0a0f; color: #a0a0b0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    flex-direction: column; gap: 16px;
  }
  .spinner {
    width: 32px; height: 32px; border: 3px solid #1a1a2e;
    border-top-color: #6366f1; border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  h2 { margin: 0; font-weight: 400; font-size: 18px; }
  p { margin: 0; font-size: 13px; color: #606070; }
</style></head><body>
  <div class="spinner"></div>
  <h2>Starting Aether...</h2>
  <p>Loading models and warming up the backend</p>
</body></html>`)}`);
  mainWindow.show();

  // 2. Setup IPC
  setupIPC();

  // 3. Start backend (detects if already running)
  await startBackend();

  // 4. Create tray (after backendManager exists)
  tray = new AetherTray(mainWindow, backendManager);
  tray.create();

  // 5. Register global hotkey
  registerHotkey();
});

app.on('will-quit', async () => {
  globalShortcut.unregisterAll();
  if (backendManager) {
    await backendManager.stop();
  }
  if (tray) {
    tray.destroy();
  }
});

app.on('before-quit', () => {
  app.isQuitting = true;
});

// macOS: re-show window when dock icon clicked
app.on('activate', () => {
  if (mainWindow) {
    mainWindow.show();
    mainWindow.focus();
  }
});

// Keep app running when all windows closed (tray mode)
app.on('window-all-closed', () => {
  // Don't quit — tray keeps running
});
