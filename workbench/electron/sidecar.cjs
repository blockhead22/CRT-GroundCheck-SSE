const { EventEmitter } = require('node:events')
const { spawn } = require('node:child_process')
const http = require('node:http')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

class SidecarManager extends EventEmitter {
  constructor(options = {}) {
    super()
    this.env = options.env || process.env
    this.python = options.python || this.env.AETHER_PYTHON || 'python'
    this.host = options.host || '127.0.0.1'
    this.port = Number(options.port || this.env.AETHER_SIDECAR_PORT || 8765)
    this.spawnImpl = options.spawnImpl || spawn
    this.process = null
    this.stopping = false
  }

  start() {
    if (this.process) return this.process
    this.stopping = false
    this.emit('status', 'starting')
    const sourceCore = path.resolve(__dirname, '..', '..', 'aether-core')
    const pythonPath = fs.existsSync(sourceCore)
      ? [sourceCore, this.env.PYTHONPATH].filter(Boolean).join(path.delimiter)
      : this.env.PYTHONPATH
    const configuredRoots = this.env.AETHER_WORKSPACE_ROOTS
    const defaultRoots = [
      path.resolve(sourceCore, '..'),
      path.join(os.homedir(), 'Downloads', 'src', 'src'),
    ].filter((candidate) => fs.existsSync(candidate))
    const workspaceRoots = configuredRoots || defaultRoots.join(path.delimiter)
    const continuityDevEnv = this.env.NODE_ENV === 'development'
      ? {
          AETHER_CONTINUITY_ENABLED: this.env.AETHER_CONTINUITY_ENABLED ?? '1',
          AETHER_CONTINUITY_MODEL_RENDER_ENABLED:
            this.env.AETHER_CONTINUITY_MODEL_RENDER_ENABLED ?? '1',
          AETHER_CONTINUITY_ROOT: this.env.AETHER_CONTINUITY_ROOT ?? sourceCore,
        }
      : {}
    this.process = this.spawnImpl(
      this.python,
      ['-m', 'aether.sidecar'],
      {
        env: {
          ...this.env,
          ...continuityDevEnv,
          AETHER_SIDECAR_HOST: this.host,
          AETHER_SIDECAR_PORT: String(this.port),
          ...(pythonPath ? { PYTHONPATH: pythonPath } : {}),
          ...(workspaceRoots ? { AETHER_WORKSPACE_ROOTS: workspaceRoots } : {}),
        },
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'pipe'],
      },
    )
    this.process.stdout?.on('data', (data) => this.emit('log', data.toString()))
    this.process.stderr?.on('data', (data) => this.emit('log', data.toString()))
    this.process.on('exit', () => {
      this.process = null
      this.emit('status', this.stopping ? 'stopped' : 'failed')
    })
    return this.process
  }

  async waitUntilReady(timeoutMs = 45000) {
    const deadline = Date.now() + timeoutMs
    while (Date.now() < deadline) {
      if (await this.checkHealth()) {
        this.emit('status', 'ready')
        return true
      }
      await new Promise((resolve) => setTimeout(resolve, 350))
    }
    this.emit('status', 'timeout')
    return false
  }

  checkHealth() {
    return new Promise((resolve) => {
      const request = http.get(
        {
          hostname: this.host,
          port: this.port,
          path: '/health',
          timeout: 1000,
        },
        (response) => {
          response.resume()
          resolve(response.statusCode === 200)
        },
      )
      request.on('error', () => resolve(false))
      request.on('timeout', () => {
        request.destroy()
        resolve(false)
      })
    })
  }

  stop() {
    this.stopping = true
    if (!this.process) return
    this.process.kill()
  }
}

module.exports = { SidecarManager }
