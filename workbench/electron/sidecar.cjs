const { EventEmitter } = require('node:events')
const { spawn } = require('node:child_process')
const http = require('node:http')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { resolveSidecarPort } = require('./data-lifecycle.cjs')

class SidecarManager extends EventEmitter {
  constructor(options = {}) {
    super()
    this.env = options.env || process.env
    this.python = options.python || this.env.AETHER_PYTHON || 'python'
    this.isPackaged = options.isPackaged ?? false
    this.resourcesPath = options.resourcesPath || process.resourcesPath || ''
    this.platform = options.platform || process.platform
    this.existsSync = options.existsSync || fs.existsSync
    this.dataRoot = options.dataRoot || this.env.AETHER_HOME || ''
    this.profileId = options.profileId || this.env.AETHER_PROFILE_ID || ''
    this.host = options.host || '127.0.0.1'
    this.port = options.port || resolveSidecarPort(this.env)
    this.spawnImpl = options.spawnImpl || spawn
    this.process = null
    this.stopping = false
    this.profileMismatch = ''
  }

  start() {
    if (this.process) return this.process
    this.stopping = false
    this.emit('status', 'starting')
    const sourceCore = path.resolve(__dirname, '..', '..', 'aether-core')
    let runtime
    try {
      runtime = resolveSidecarRuntime({
        env: this.env,
        python: this.python,
        isPackaged: this.isPackaged,
        resourcesPath: this.resourcesPath,
        platform: this.platform,
        existsSync: this.existsSync,
      })
    } catch (error) {
      this.emit('log', `${error.message}\n`)
      this.emit('status', 'failed')
      throw error
    }
    const pythonPath = !this.isPackaged && this.existsSync(sourceCore)
      ? [sourceCore, this.env.PYTHONPATH].filter(Boolean).join(path.delimiter)
      : undefined
    const configuredRoots = this.env.AETHER_WORKSPACE_ROOTS
    const defaultRoots = this.isPackaged ? [] : [
      path.resolve(sourceCore, '..'),
      path.join(os.homedir(), 'Downloads', 'src', 'src'),
    ].filter((candidate) => this.existsSync(candidate))
    const workspaceRoots = configuredRoots || defaultRoots.join(path.delimiter)
    const continuityDevEnv = this.env.NODE_ENV === 'development'
      ? {
          AETHER_CONTINUITY_ENABLED: this.env.AETHER_CONTINUITY_ENABLED ?? '1',
          AETHER_CONTINUITY_MODEL_RENDER_ENABLED:
            this.env.AETHER_CONTINUITY_MODEL_RENDER_ENABLED ?? '1',
          AETHER_CONTINUITY_ROOT: this.env.AETHER_CONTINUITY_ROOT ?? sourceCore,
        }
      : {}
    const childEnv = { ...this.env }
    if (this.isPackaged) delete childEnv.PYTHONPATH
    this.process = this.spawnImpl(
      runtime.command,
      runtime.args,
      {
        env: {
          ...childEnv,
          ...continuityDevEnv,
          AETHER_SIDECAR_HOST: this.host,
          AETHER_SIDECAR_PORT: String(this.port),
          ...(this.dataRoot ? { AETHER_HOME: this.dataRoot } : {}),
          ...(this.profileId ? { AETHER_PROFILE_ID: this.profileId } : {}),
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
      if (this.profileMismatch) {
        this.emit('status', 'failed')
        throw new Error(this.profileMismatch)
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
          let body = ''
          response.setEncoding('utf8')
          response.on('data', (chunk) => {
            if (body.length < 1024 * 1024) body += chunk
          })
          response.on('end', () => {
            if (response.statusCode !== 200) {
              resolve(false)
              return
            }
            try {
              const health = JSON.parse(body)
              const mismatch = this.expectedProfileMismatch(health)
              if (mismatch) {
                this.profileMismatch = mismatch
                resolve(false)
                return
              }
              this.profileMismatch = ''
              resolve(true)
            } catch {
              resolve(false)
            }
          })
        },
      )
      request.on('error', () => resolve(false))
      request.on('timeout', () => {
        request.destroy()
        resolve(false)
      })
    })
  }

  expectedProfileMismatch(health) {
    if (!this.dataRoot) return ''
    const expectedProfileId = this.profileId || 'default'
    const expectedScope = this.profileId ? 'profile_root' : 'default_root'
    const expectedPath = this.profileId
      ? path.join(this.dataRoot, 'profiles', this.profileId, 'substrate.json')
      : path.join(this.dataRoot, 'substrate.json')
    const actualProfileId = String(health?.profile?.id || '')
    const actualScope = String(health?.profile?.storage_scope || '')
    const actualPath = String(health?.substrate?.path || '')
    const normalize = (value) => {
      const flavor = this.platform === 'win32' ? path.win32 : path
      const normalized = flavor.resolve(value)
      return this.platform === 'win32' ? normalized.toLowerCase() : normalized
    }
    if (
      actualProfileId === expectedProfileId
      && actualScope === expectedScope
      && actualPath
      && normalize(actualPath) === normalize(expectedPath)
    ) return ''
    return (
      `Wrong Aether profile connected on ${this.host}:${this.port}. `
      + `Expected ${expectedProfileId} at ${expectedPath}; `
      + `received ${actualProfileId || 'unknown'} at ${actualPath || 'unknown'}.`
    )
  }

  stop() {
    this.stopping = true
    if (!this.process) return
    this.process.kill()
  }
}

function resolveSidecarRuntime({
  env = process.env,
  python = env.AETHER_PYTHON || 'python',
  isPackaged = false,
  resourcesPath = process.resourcesPath || '',
  platform = process.platform,
  existsSync = fs.existsSync,
} = {}) {
  const platformPath = platform === 'win32' ? path.win32 : path.posix
  const executableName = platform === 'win32' ? 'aether-sidecar.exe' : 'aether-sidecar'
  const explicitExecutable = String(env.AETHER_SIDECAR_EXECUTABLE || '').trim()
  if (explicitExecutable) {
    const command = platformPath.resolve(explicitExecutable)
    if (!existsSync(command)) {
      throw new Error(`Configured Aether sidecar executable was not found: ${command}`)
    }
    return { command, args: [], kind: 'configured-executable' }
  }

  if (isPackaged && resourcesPath) {
    const command = platformPath.join(resourcesPath, 'sidecar', executableName)
    if (existsSync(command)) return { command, args: [], kind: 'bundled-executable' }
  }

  const configuredPython = String(env.AETHER_PYTHON || '').trim()
  if (configuredPython) {
    return {
      command: configuredPython,
      args: ['-m', 'aether.sidecar'],
      kind: 'configured-python',
    }
  }

  if (isPackaged) {
    throw new Error(
      'Packaged Aether Workbench has no bundled sidecar. Reinstall it or set AETHER_SIDECAR_EXECUTABLE/AETHER_PYTHON explicitly.',
    )
  }

  return { command: python, args: ['-m', 'aether.sidecar'], kind: 'development-python' }
}

module.exports = { SidecarManager, resolveSidecarRuntime }
