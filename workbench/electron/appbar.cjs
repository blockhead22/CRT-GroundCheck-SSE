const path = require('node:path')
const { spawnSync } = require('node:child_process')

function nativeWindowHandle(browserWindow) {
  const value = browserWindow.getNativeWindowHandle()
  if (!Buffer.isBuffer(value) || value.length < 4) {
    throw new Error('Electron did not provide a native window handle')
  }
  return value.length >= 8
    ? value.readBigUInt64LE(0).toString()
    : String(value.readUInt32LE(0))
}

class AppBarManager {
  constructor(options = {}) {
    this.platform = options.platform || process.platform
    this.spawnSyncImpl = options.spawnSyncImpl || spawnSync
    this.scriptPath = options.scriptPath || path.join(__dirname, 'appbar.ps1')
    this.activeHwnd = null
    this.lastError = null
  }

  reserve(browserWindow, displayBounds, width) {
    if (this.platform !== 'win32') return null
    const hwnd = nativeWindowHandle(browserWindow)
    const register = this.activeHwnd === hwnd ? 0 : 1
    if (this.activeHwnd && this.activeHwnd !== hwnd) this.release(browserWindow)
    const result = this._run([
      '-Action', 'reserve',
      '-Hwnd', hwnd,
      '-Left', String(displayBounds.x),
      '-Top', String(displayBounds.y),
      '-Right', String(displayBounds.x + displayBounds.width),
      '-Bottom', String(displayBounds.y + displayBounds.height),
      '-Width', String(width),
      '-Register', String(register),
    ])
    this.activeHwnd = hwnd
    return result
  }

  release(_browserWindow) {
    if (this.platform !== 'win32' || !this.activeHwnd) return false
    this._run(['-Action', 'remove', '-Hwnd', this.activeHwnd])
    this.activeHwnd = null
    return true
  }

  _run(args) {
    const result = this.spawnSyncImpl(
      'powershell.exe',
      [
        '-NoProfile',
        '-NonInteractive',
        '-ExecutionPolicy', 'Bypass',
        '-File', this.scriptPath,
        ...args,
      ],
      { encoding: 'utf8', windowsHide: true },
    )
    if (result.error || result.status !== 0) {
      const detail = result.error?.message || String(result.stderr || '').trim()
      this.lastError = detail || `AppBar helper exited with status ${result.status}`
      throw new Error(this.lastError)
    }
    const line = String(result.stdout || '').trim().split(/\r?\n/).filter(Boolean).at(-1)
    try {
      this.lastError = null
      return JSON.parse(line || '{}')
    } catch {
      this.lastError = 'AppBar helper returned invalid JSON'
      throw new Error(this.lastError)
    }
  }
}

module.exports = { AppBarManager, nativeWindowHandle }
