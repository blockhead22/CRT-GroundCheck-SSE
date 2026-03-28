/**
 * Desktop Pet — Transparent always-on-top mascot that patrols the screen
 * when the main window is hidden. Full companion: chat, think, mood, interactions.
 */

const { BrowserWindow, screen } = require('electron');
const path = require('path');

const PET_HEIGHT = 160; // tall enough for speech bubbles + mascot + menu

class DesktopPet {
  constructor() {
    this.win = null;
  }

  show() {
    if (this.win && !this.win.isDestroyed()) {
      this.win.show();
      return;
    }

    const display = screen.getPrimaryDisplay();
    const { width, height } = display.workAreaSize;

    this.win = new BrowserWindow({
      width: width,
      height: PET_HEIGHT,
      x: 0,
      y: height - PET_HEIGHT,
      transparent: true,
      frame: false,
      alwaysOnTop: true,
      skipTaskbar: true,
      focusable: false,
      hasShadow: false,
      resizable: false,
      movable: false,
      type: 'toolbar',
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
        preload: path.join(__dirname, 'preload.js'),
      },
    });

    // Click-through by default — pet.html toggles this via IPC
    this.win.setIgnoreMouseEvents(true, { forward: true });

    this.win.loadFile(path.join(__dirname, 'pet.html'));
    this.win.show();

    console.log('[pet] Desktop pet shown');
  }

  hide() {
    if (this.win && !this.win.isDestroyed()) {
      this.win.hide();
      console.log('[pet] Desktop pet hidden');
    }
  }

  destroy() {
    if (this.win && !this.win.isDestroyed()) {
      this.win.destroy();
    }
    this.win = null;
  }

  enableClicks() {
    if (this.win && !this.win.isDestroyed()) {
      this.win.setIgnoreMouseEvents(false);
      this.win.setFocusable(true);
      this.win.focus();
    }
  }

  disableClicks() {
    if (this.win && !this.win.isDestroyed()) {
      this.win.setIgnoreMouseEvents(true, { forward: true });
      this.win.setFocusable(false);
    }
  }
}

module.exports = { DesktopPet };
