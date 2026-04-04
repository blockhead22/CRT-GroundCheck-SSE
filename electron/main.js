/**
 * Aether Desktop — Main Process
 *
 * Orchestrates: backend lifecycle, window management, system tray, global hotkey.
 */

const {
  app,
  BrowserWindow,
  Menu,
  Notification,
  globalShortcut,
  ipcMain,
  shell,
  session,
} = require('electron');
const path = require('path');
const http = require('http');
const Store = require('electron-store');
const { BackendManager } = require('./backend');
const { AetherTray } = require('./tray');
const { ClipboardMonitor } = require('./clipboard-monitor');
const { AmbientMonitor } = require('./ambient-monitor');
const { DesktopPet } = require('./pet-window');

// ── Config ────────────────────────────────────────────────────────────

const IS_DEV = process.env.NODE_ENV === 'development';
const REPO_ROOT = path.resolve(__dirname, '..');
const BACKEND_PORT = parseInt(process.env.PORT || '8000', 10);
const BACKEND_HOST = process.env.CRT_HOST || '127.0.0.1';
const FRONTEND_DEV_URL = `http://localhost:5173`;
// In production, we load the frontend through the backend (which serves dist/)
// This avoids file:// protocol issues with absolute asset paths
const FRONTEND_PROD_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;

// ── Persistent settings ──────────────────────────────────────────────

const store = new Store({
  defaults: {
    windowBounds: { width: 1200, height: 800 },
    windowPosition: null,   // { x, y } or null for centered
    displayId: null,         // last display id
  },
});

function getSavedWindowBounds() {
  const { screen } = require('electron');
  const saved = store.get('windowBounds', { width: 1200, height: 800 });
  const pos = store.get('windowPosition');
  const savedDisplayId = store.get('displayId');

  // Validate that the saved position is still on a connected display
  if (pos) {
    const displays = screen.getAllDisplays();
    const targetDisplay = savedDisplayId
      ? displays.find(d => d.id === savedDisplayId)
      : screen.getDisplayNearestPoint(pos);

    if (targetDisplay) {
      const { x, y, width, height } = targetDisplay.workArea;
      // Ensure at least 100px of the window is visible on this display
      if (
        pos.x + saved.width > x + 100 &&
        pos.x < x + width - 100 &&
        pos.y + saved.height > y + 100 &&
        pos.y < y + height - 100
      ) {
        return { ...saved, x: pos.x, y: pos.y };
      }
    }
  }

  // Fall back to centered on primary display
  return saved;
}

// ── State ─────────────────────────────────────────────────────────────

let mainWindow = null;
let tray = null;
let backendManager = null;
let clipboardMonitor = null;
let ambientMonitor = null;
let desktopPet = null;
let frontendLoaded = false;

async function installContextMenu(window) {
  try {
    const mod = await import('electron-context-menu');
    const contextMenu = mod.default || mod;
    contextMenu({
      window,
      showSearchWithGoogle: true,
      showCopyImage: false,
      showSaveImageAs: false,
      showSelectAll: true,
      showInspectElement: IS_DEV,
      showLookUpSelection: false,
      // Spellcheck suggestions appear automatically when right-clicking misspelled words
    });
    console.log('[main] Spellcheck + context menu enabled');
  } catch (error) {
    console.warn('[main] Failed to enable context menu:', error?.message || error);
  }
}

// ── Window ────────────────────────────────────────────────────────────

function createWindow() {
  // Remove default menu bar
  Menu.setApplicationMenu(null);

  const bounds = getSavedWindowBounds();

  mainWindow = new BrowserWindow({
    width: bounds.width,
    height: bounds.height,
    ...(bounds.x !== undefined ? { x: bounds.x, y: bounds.y } : {}),
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

  // Hide instead of close (tray keeps running) — show pet
  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
      if (desktopPet) desktopPet.show();
    }
  });

  // Persist window bounds and display on resize/move
  const saveBounds = () => {
    if (mainWindow.isMinimized() || mainWindow.isMaximized()) return;
    const { screen } = require('electron');
    const [w, h] = mainWindow.getSize();
    const [x, y] = mainWindow.getPosition();
    store.set('windowBounds', { width: w, height: h });
    store.set('windowPosition', { x, y });
    const display = screen.getDisplayNearestPoint({ x, y });
    store.set('displayId', display.id);
  };
  mainWindow.on('resize', saveBounds);
  mainWindow.on('move', saveBounds);

  // Open external links in default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Prevent navigation when files are dropped (Electron tries to load file:// URLs)
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (url.startsWith('file://')) {
      event.preventDefault();
    }
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

    // Inject drop zone overlay CSS
    mainWindow.webContents.insertCSS(`
      #aether-drop-overlay {
        display: none;
        position: fixed;
        inset: 0;
        z-index: 99999;
        background: rgba(99, 102, 241, 0.12);
        backdrop-filter: blur(2px);
        border: 3px dashed rgba(99, 102, 241, 0.5);
        align-items: center;
        justify-content: center;
        pointer-events: none;
      }
      #aether-drop-overlay.active {
        display: flex;
      }
      #aether-drop-overlay .drop-label {
        background: rgba(10, 10, 15, 0.85);
        color: #c4b5fd;
        padding: 16px 32px;
        border-radius: 12px;
        font-size: 18px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        font-weight: 500;
        letter-spacing: 0.02em;
      }
      #aether-drop-toast {
        display: none;
        position: fixed;
        bottom: 24px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 99999;
        background: rgba(10, 10, 15, 0.9);
        border: 1px solid rgba(99, 102, 241, 0.3);
        color: #a0a0b0;
        padding: 10px 20px;
        border-radius: 8px;
        font-size: 13px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        transition: opacity 0.3s;
      }
      #aether-drop-toast.success { border-color: rgba(34, 197, 94, 0.4); color: #86efac; }
      #aether-drop-toast.error { border-color: rgba(239, 68, 68, 0.4); color: #fca5a5; }
    `);

    // Inject drop zone overlay + drag/drop event handlers
    mainWindow.webContents.executeJavaScript(`
      (function setupFileDrop() {
        // Create overlay
        if (document.getElementById('aether-drop-overlay')) return;
        const overlay = document.createElement('div');
        overlay.id = 'aether-drop-overlay';
        overlay.innerHTML = '<div class="drop-label">Drop to remember</div>';
        document.body.appendChild(overlay);

        // Create toast
        const toast = document.createElement('div');
        toast.id = 'aether-drop-toast';
        document.body.appendChild(toast);

        let dragCounter = 0;

        document.addEventListener('dragenter', (e) => {
          e.preventDefault();
          e.stopPropagation();
          dragCounter++;
          if (e.dataTransfer && e.dataTransfer.types.includes('Files')) {
            overlay.classList.add('active');
          }
        });

        document.addEventListener('dragover', (e) => {
          e.preventDefault();
          e.stopPropagation();
        });

        document.addEventListener('dragleave', (e) => {
          e.preventDefault();
          e.stopPropagation();
          dragCounter--;
          if (dragCounter <= 0) {
            dragCounter = 0;
            overlay.classList.remove('active');
          }
        });

        document.addEventListener('drop', (e) => {
          e.preventDefault();
          e.stopPropagation();
          dragCounter = 0;
          overlay.classList.remove('active');

          const files = e.dataTransfer ? e.dataTransfer.files : [];
          for (const file of files) {
            if (file.path) {
              window.aether && window.aether._sendFileIngest
                ? window.aether._sendFileIngest(file.path)
                : null;
            }
          }
        });

        // Listen for ingest results
        if (window.aether && window.aether.onFileDrop) {
          window.aether.onFileDrop((result) => {
            toast.style.display = 'block';
            toast.style.opacity = '1';
            if (result.success) {
              toast.className = 'success';
              toast.textContent = 'Remembered ' + result.filename + ' (' + result.memories + ' memories)';
            } else {
              toast.className = 'error';
              toast.textContent = 'Failed: ' + (result.error || result.filename);
            }
            setTimeout(() => {
              toast.style.opacity = '0';
              setTimeout(() => { toast.style.display = 'none'; }, 300);
            }, 3000);
          });
        }
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
      if (desktopPet) desktopPet.show();
    } else {
      if (desktopPet) desktopPet.hide();
      mainWindow.show();
      mainWindow.focus();
    }
  });

  ipcMain.on('app:minimize-to-tray', () => {
    mainWindow.hide();
    if (desktopPet) desktopPet.show();
  });

  // Pet mouse interaction — toggle click-through
  ipcMain.on('pet:mouse-enter', () => {
    if (desktopPet) desktopPet.enableClicks();
  });
  ipcMain.on('pet:mouse-leave', () => {
    if (desktopPet) desktopPet.disableClicks();
  });

  // Pet hide
  ipcMain.on('pet:hide', () => {
    if (desktopPet) desktopPet.hide();
  });

  // Pet chat — send message to backend, return short response
  ipcMain.on('pet:chat', (_event, message) => {
    console.log('[pet] Chat request:', message);
    const petPrompt = `[SYSTEM: You are Aether's desktop pet companion. Respond in 1-2 short sentences max. Be playful, brief, personality-forward. No markdown, no lists, no formatting. Just casual speech like a tiny AI buddy.]\n\nUser: ${message}`;
    const payload = JSON.stringify({
      thread_id: 'desktop_pet',
      message: petPrompt,
      channel: 'desktop_pet',
    });

    const req = http.request(
      {
        hostname: BACKEND_HOST,
        port: BACKEND_PORT,
        path: '/api/chat/send',
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) },
        timeout: 15000,
      },
      (res) => {
        let body = '';
        res.on('data', (chunk) => { body += chunk; });
        res.on('end', () => {
          try {
            const data = JSON.parse(body);
            const answer = data.answer || data.detail || 'hmm...';
            console.log('[pet] Chat response:', answer.slice(0, 80));
            if (desktopPet && desktopPet.win && !desktopPet.win.isDestroyed()) {
              desktopPet.win.webContents.send('pet:response', { type: 'chat', text: answer });
            }
          } catch (err) {
            console.error('[pet] Chat parse error:', err.message, body.slice(0, 200));
            if (desktopPet && desktopPet.win && !desktopPet.win.isDestroyed()) {
              desktopPet.win.webContents.send('pet:response', { type: 'chat', text: 'brain glitch... try again?' });
            }
          }
        });
      }
    );
    req.on('error', () => {
      if (desktopPet && desktopPet.win && !desktopPet.win.isDestroyed()) {
        desktopPet.win.webContents.send('pet:response', { type: 'chat', text: "can't reach my brain rn..." });
      }
    });
    req.write(payload);
    req.end();
  });

  // Pet think — generate a context-aware thought
  ipcMain.on('pet:think', () => {
    const hour = new Date().getHours();
    const timeOfDay = hour < 6 ? 'late night' : hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : hour < 21 ? 'evening' : 'night';

    const thinkPrompt = `[SYSTEM: You are Aether's desktop pet. Generate ONE short casual thought (max 8 words) that a tiny AI buddy might have right now. It's ${timeOfDay}. Be cute, random, philosophical, or observational. No quotes, no punctuation drama. Just the thought.]\n\nGenerate a thought:`;

    const payload = JSON.stringify({
      thread_id: 'desktop_pet',
      message: thinkPrompt,
      channel: 'desktop_pet',
    });

    const req = http.request(
      {
        hostname: BACKEND_HOST,
        port: BACKEND_PORT,
        path: '/api/chat/send',
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) },
        timeout: 15000,
      },
      (res) => {
        let body = '';
        res.on('data', (chunk) => { body += chunk; });
        res.on('end', () => {
          try {
            const data = JSON.parse(body);
            const thought = (data.answer || '...').slice(0, 60);
            if (desktopPet && desktopPet.win && !desktopPet.win.isDestroyed()) {
              desktopPet.win.webContents.send('pet:response', { type: 'think', text: thought });
            }
          } catch {
            if (desktopPet && desktopPet.win && !desktopPet.win.isDestroyed()) {
              desktopPet.win.webContents.send('pet:response', { type: 'think', text: 'hmm...' });
            }
          }
        });
      }
    );
    req.on('error', () => {
      if (desktopPet && desktopPet.win && !desktopPet.win.isDestroyed()) {
        desktopPet.win.webContents.send('pet:response', { type: 'think', text: 'brain offline...' });
      }
    });
    req.write(payload);
    req.end();
  });

  // Forward clipboard events to pet window
  ipcMain.on('clipboard:capture', (_event, text) => {
    if (desktopPet && desktopPet.win && !desktopPet.win.isDestroyed()) {
      desktopPet.win.webContents.send('pet:context', { type: 'clipboard', preview: text.slice(0, 40) });
    }
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

  // ── Clipboard IPC ──────────────────────────────────────────────────
  ipcMain.on('clipboard:toggle', (_event, enabled) => {
    if (clipboardMonitor) {
      clipboardMonitor.toggle(enabled);
    }
  });

  ipcMain.on('clipboard:remember', (_event, text) => {
    storeClipboardMemory(text);
  });

  // ── Ambient IPC ────────────────────────────────────────────────────
  ipcMain.on('ambient:toggle', (_event, enabled) => {
    if (ambientMonitor) {
      ambientMonitor.toggle(enabled);
    }
  });

  ipcMain.on('ambient:capture-now', () => {
    if (ambientMonitor) {
      ambientMonitor.captureNow();
    }
  });

  // ── File Ingest IPC ───────────────────────────────────────────────
  ipcMain.on('file:ingest', (_event, filePath) => {
    console.log(`[file-drop] Ingesting: ${filePath}`);
    ingestFile(filePath);
  });
}

// ── Global Hotkey ─────────────────────────────────────────────────────

function registerDevTools() {
  globalShortcut.register('F12', () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.toggleDevTools();
    }
  });
  globalShortcut.register('CmdOrCtrl+Shift+I', () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.toggleDevTools();
    }
  });
}

function registerHotkey() {
  const accelerator = process.platform === 'darwin' ? 'Cmd+Space' : 'Ctrl+Space';

  const hotkeyAction = () => {
    if (!mainWindow) return;
    if (mainWindow.isVisible() && mainWindow.isFocused()) {
      mainWindow.hide();
      if (desktopPet) desktopPet.show();
    } else {
      if (desktopPet) desktopPet.hide();
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

// ── Clipboard Memory ──────────────────────────────────────────────────

function storeClipboardMemory(text) {
  const payload = JSON.stringify({
    text,
    source: 'clipboard',
    confidence: 0.8,
    user_marked_important: false,
    context: { captured_by: 'clipboard-monitor' },
  });

  const req = http.request(
    {
      hostname: BACKEND_HOST,
      port: BACKEND_PORT,
      path: '/api/memory/store',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload),
      },
      timeout: 5000,
    },
    (res) => {
      let body = '';
      res.on('data', (chunk) => { body += chunk; });
      res.on('end', () => {
        if (res.statusCode === 200) {
          console.log('[clipboard] Memory stored successfully');
        } else {
          console.warn(`[clipboard] Memory store failed (${res.statusCode}): ${body}`);
        }
      });
    }
  );
  req.on('error', (err) => {
    console.warn('[clipboard] Memory store request failed:', err.message);
  });
  req.write(payload);
  req.end();
}

// ── File Ingest ──────────────────────────────────────────────────────

function ingestFile(filePath) {
  const payload = JSON.stringify({
    file_path: filePath,
    thread_id: 'default',
  });

  const req = http.request(
    {
      hostname: BACKEND_HOST,
      port: BACKEND_PORT,
      path: '/api/ingest/file',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload),
      },
      timeout: 30000, // file ingestion can take a moment
    },
    (res) => {
      let body = '';
      res.on('data', (chunk) => { body += chunk; });
      res.on('end', () => {
        let result;
        try {
          result = JSON.parse(body);
        } catch {
          result = { success: false, error: body };
        }

        if (res.statusCode === 200 && result.success) {
          console.log(`[file-drop] Ingested ${result.filename}: ${result.chars_ingested} chars, ${result.memory_count} memories`);
        } else {
          console.warn(`[file-drop] Ingest failed (${res.statusCode}):`, result.error || result.detail || body);
        }

        // Notify renderer of result
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('file:dropped', {
            success: res.statusCode === 200 && result.success,
            filename: result.filename || path.basename(filePath),
            chars: result.chars_ingested || 0,
            memories: result.memory_count || 0,
            error: result.error || result.detail || null,
          });
        }
      });
    }
  );
  req.on('error', (err) => {
    console.warn('[file-drop] Ingest request failed:', err.message);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('file:dropped', {
        success: false,
        filename: path.basename(filePath),
        error: err.message,
      });
    }
  });
  req.write(payload);
  req.end();
}

function setupClipboardMonitor() {
  clipboardMonitor = new ClipboardMonitor();

  clipboardMonitor.on('capture', (text) => {
    const preview = text.length > 60 ? text.slice(0, 57) + '...' : text;
    console.log(`[clipboard] Captured: "${preview}"`);

    // Show native notification
    if (Notification.isSupported()) {
      const notif = new Notification({
        title: 'Aether',
        body: `Want me to remember that?\n${preview}`,
        silent: true,
      });
      notif.on('click', () => {
        storeClipboardMemory(text);
        // Also bring the window up
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.show();
          mainWindow.focus();
        }
      });
      notif.show();
    }

    // Forward to renderer for inline UI
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('clipboard:capture', text);
    }
  });

  // Do NOT auto-start — user must enable via tray or settings
  console.log('[clipboard] Monitor created (disabled by default)');
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

// ── WebSocket Notification Listener ──────────────────────────────────

const WebSocket = require('ws');
let notifWs = null;
let wsReconnectTimer = null;
let wsReconnectAttempts = 0;
const WS_MAX_RECONNECT = 20;

function startWSListener() {
  if (notifWs) return;

  function connect() {
    const url = `ws://${BACKEND_HOST}:${BACKEND_PORT}/ws`;
    console.log(`[main] Connecting to WebSocket at ${url}...`);

    try {
      notifWs = new WebSocket(url);
    } catch (e) {
      console.warn('[main] WS connection failed:', e.message);
      scheduleWSReconnect();
      return;
    }

    notifWs.on('open', () => {
      console.log('[main] WebSocket connected');
      wsReconnectAttempts = 0;
      // Subscribe to notifications channel
      notifWs.send(JSON.stringify({ type: 'subscribe', channels: ['notifications'] }));
    });

    notifWs.on('message', (raw) => {
      try {
        const data = JSON.parse(raw.toString());

        // Handle notifications (same events as SSE)
        if (data.type === 'notification' && data.subtype === 'commitment') {
          // Commitment notification — show native OS notification
          if (Notification.isSupported()) {
            const notif = new Notification({
              title: 'Aether Reminder',
              body: (data.content || '').slice(0, 200),
            });
            notif.show();
          }
        } else if (data.type === 'heartbeat_contradiction' ||
                   (data.type === 'notification' && data.subtype === 'heartbeat_contradiction')) {
          showContradictionNotification(data);
        }
      } catch { /* ignore parse errors */ }
    });

    notifWs.on('close', () => {
      console.log('[main] WebSocket closed');
      notifWs = null;
      scheduleWSReconnect();
    });

    notifWs.on('error', (err) => {
      console.warn('[main] WebSocket error:', err.message);
      if (notifWs) {
        notifWs.close();
        notifWs = null;
      }
    });
  }

  function scheduleWSReconnect() {
    if (wsReconnectAttempts >= WS_MAX_RECONNECT) {
      console.warn('[main] Max WS reconnect attempts reached, falling back to SSE');
      startSSEListener();
      return;
    }
    const delay = Math.min(1000 * Math.pow(2, wsReconnectAttempts), 30000);
    wsReconnectAttempts++;
    wsReconnectTimer = setTimeout(connect, delay);
  }

  connect();
}

// ── SSE Notification Listener (fallback) ─────────────────────────────

let sseReq = null;

function startSSEListener() {
  if (sseReq) return;

  function connect() {
    console.log('[main] Connecting to notification SSE stream (fallback)...');
    sseReq = http.get(
      {
        hostname: BACKEND_HOST,
        port: BACKEND_PORT,
        path: '/api/notifications/stream',
        timeout: 0,
      },
      (res) => {
        if (res.statusCode !== 200) {
          console.warn(`[main] SSE stream returned ${res.statusCode}, retrying in 15s`);
          sseReq = null;
          setTimeout(connect, 15000);
          return;
        }

        let buffer = '';
        res.on('data', (chunk) => {
          buffer += chunk.toString();
          const parts = buffer.split('\n\n');
          buffer = parts.pop() || '';
          for (const part of parts) {
            const dataLine = part.split('\n').find(l => l.startsWith('data:'));
            if (!dataLine) continue;
            try {
              const data = JSON.parse(dataLine.slice(5).trim());
              if (data.type === 'heartbeat_contradiction') {
                showContradictionNotification(data);
              }
            } catch { /* ignore parse errors */ }
          }
        });

        res.on('end', () => {
          console.log('[main] SSE stream ended, reconnecting in 10s');
          sseReq = null;
          setTimeout(connect, 10000);
        });

        res.on('error', () => {
          sseReq = null;
          setTimeout(connect, 15000);
        });
      }
    );
    sseReq.on('error', () => {
      sseReq = null;
      setTimeout(connect, 15000);
    });
  }

  connect();
}

function showContradictionNotification(data) {
  if (!Notification.isSupported()) return;

  const body = (data.content || 'A belief contradiction was detected').slice(0, 200);
  const notif = new Notification({
    title: 'Aether noticed something',
    body,
    silent: false,
  });

  notif.on('click', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });

  notif.show();
  console.log('[main] Showed contradiction notification');
}

app.whenReady().then(async () => {
  console.log('[main] Aether Desktop starting...');
  console.log(`[main] Repo root: ${REPO_ROOT}`);
  console.log(`[main] Mode: ${IS_DEV ? 'development' : 'production'}`);

  // 1. Create window with loading screen
  createWindow();

  // ── Spellcheck + Context Menu ────────────────────────────────────────
  // Enable Chromium's built-in spellchecker
  session.defaultSession.setSpellCheckerLanguages(['en-US']);

  // Custom right-click context menu with spellcheck suggestions
  await installContextMenu(mainWindow);

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

  // 4. Setup clipboard monitor (off by default)
  setupClipboardMonitor();

  // 4b. Setup ambient monitor (off by default)
  ambientMonitor = new AmbientMonitor({
    backendHost: BACKEND_HOST,
    backendPort: BACKEND_PORT,
  });
  ambientMonitor.on('context', (data) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('ambient:context', data);
    }
  });
  console.log('[ambient] Monitor created (disabled by default)');

  // 5. Create desktop pet (shown when main window is hidden)
  desktopPet = new DesktopPet();

  // 6. Create tray (after backendManager, clipboardMonitor, ambientMonitor exist)
  tray = new AetherTray(mainWindow, backendManager, clipboardMonitor, ambientMonitor);
  tray.create();

  // 7. Register global hotkey + dev tools toggle
  registerHotkey();
  registerDevTools();

  // 8. Start WebSocket listener for native OS notifications (contradictions, etc.)
  // Falls back to SSE if WS connection fails after max retries.
  // Defer until backend is confirmed healthy to avoid triple-connect on startup.
  if (backendManager.healthy) {
    startWSListener();
  } else {
    backendManager.once('status', (status) => {
      if (status === 'healthy') startWSListener();
    });
  }
});

app.on('will-quit', async () => {
  globalShortcut.unregisterAll();
  if (notifWs) {
    notifWs.close();
    notifWs = null;
  }
  if (wsReconnectTimer) {
    clearTimeout(wsReconnectTimer);
    wsReconnectTimer = null;
  }
  if (sseReq) {
    sseReq.destroy();
    sseReq = null;
  }
  if (clipboardMonitor) {
    clipboardMonitor.stop();
  }
  if (ambientMonitor) {
    ambientMonitor.stop();
  }
  if (desktopPet) {
    desktopPet.destroy();
  }
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
    if (desktopPet) desktopPet.hide();
    mainWindow.show();
    mainWindow.focus();
  }
});

// Keep app running when all windows closed (tray mode)
app.on('window-all-closed', () => {
  // Don't quit — tray keeps running
});
