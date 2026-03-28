/**
 * System tray for Aether.
 * Shows status icon, right-click menu with basic controls.
 */

const { Tray, Menu, nativeImage } = require('electron');
const path = require('path');

class AetherTray {
  constructor(mainWindow, backendManager) {
    this.mainWindow = mainWindow;
    this.backendManager = backendManager;
    this.tray = null;
    this.status = 'loading';
  }

  create() {
    const icon = this.getIcon('loading');
    this.tray = new Tray(icon);
    this.tray.setToolTip('Aether - Starting...');
    this.updateMenu();

    // Click to toggle window
    this.tray.on('click', () => {
      if (this.mainWindow.isVisible()) {
        this.mainWindow.hide();
      } else {
        this.mainWindow.show();
        this.mainWindow.focus();
      }
    });

    // Listen to backend status changes
    this.backendManager.on('status', (status) => {
      this.setStatus(status);
    });
  }

  setStatus(status) {
    this.status = status;
    if (!this.tray || this.tray.isDestroyed()) return;

    const statusMap = {
      starting: { icon: 'loading', tip: 'Aether - Starting backend...' },
      healthy: { icon: 'healthy', tip: 'Aether - Ready' },
      unhealthy: { icon: 'unhealthy', tip: 'Aether - Backend unresponsive' },
      restarting: { icon: 'loading', tip: 'Aether - Restarting...' },
      stopped: { icon: 'unhealthy', tip: 'Aether - Backend stopped' },
      failed: { icon: 'unhealthy', tip: 'Aether - Backend failed (max restarts)' },
      error: { icon: 'unhealthy', tip: 'Aether - Backend error' },
      timeout: { icon: 'unhealthy', tip: 'Aether - Backend startup timeout' },
      stopping: { icon: 'loading', tip: 'Aether - Shutting down...' },
    };

    const info = statusMap[status] || { icon: 'loading', tip: `Aether - ${status}` };
    this.tray.setImage(this.getIcon(info.icon));
    this.tray.setToolTip(info.tip);
    this.updateMenu();
  }

  getIcon(name) {
    // Use simple colored circles as tray icons
    // 16x16 PNG data URIs for cross-platform compatibility
    const icons = {
      healthy: this.createColorIcon('#22c55e'),   // green
      unhealthy: this.createColorIcon('#ef4444'), // red
      loading: this.createColorIcon('#f59e0b'),   // amber
    };
    return icons[name] || icons.loading;
  }

  createColorIcon(hexColor) {
    // Create a simple 16x16 icon using nativeImage
    // We'll use a small PNG buffer - a filled circle
    const size = 16;
    const canvas = Buffer.alloc(size * size * 4); // RGBA

    const r = parseInt(hexColor.slice(1, 3), 16);
    const g = parseInt(hexColor.slice(3, 5), 16);
    const b = parseInt(hexColor.slice(5, 7), 16);

    const cx = size / 2;
    const cy = size / 2;
    const radius = 6;

    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        const idx = (y * size + x) * 4;
        const dist = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2);
        if (dist <= radius) {
          canvas[idx] = r;
          canvas[idx + 1] = g;
          canvas[idx + 2] = b;
          canvas[idx + 3] = 255;
        } else if (dist <= radius + 1) {
          // Anti-aliased edge
          const alpha = Math.max(0, 1 - (dist - radius)) * 255;
          canvas[idx] = r;
          canvas[idx + 1] = g;
          canvas[idx + 2] = b;
          canvas[idx + 3] = Math.round(alpha);
        } else {
          canvas[idx] = 0;
          canvas[idx + 1] = 0;
          canvas[idx + 2] = 0;
          canvas[idx + 3] = 0;
        }
      }
    }

    return nativeImage.createFromBuffer(canvas, {
      width: size,
      height: size,
    });
  }

  updateMenu() {
    if (!this.tray || this.tray.isDestroyed()) return;

    const isHealthy = this.status === 'healthy';

    const contextMenu = Menu.buildFromTemplate([
      {
        label: `Aether ${isHealthy ? '(Ready)' : `(${this.status})`}`,
        enabled: false,
      },
      { type: 'separator' },
      {
        label: 'Show/Hide',
        click: () => {
          if (this.mainWindow.isVisible()) {
            this.mainWindow.hide();
          } else {
            this.mainWindow.show();
            this.mainWindow.focus();
          }
        },
      },
      {
        label: 'Restart Backend',
        click: () => {
          this.backendManager.restart();
        },
      },
      { type: 'separator' },
      {
        label: 'Quit Aether',
        click: () => {
          const { app } = require('electron');
          app.quit();
        },
      },
    ]);

    this.tray.setContextMenu(contextMenu);
  }

  destroy() {
    if (this.tray && !this.tray.isDestroyed()) {
      this.tray.destroy();
    }
  }
}

module.exports = { AetherTray };
