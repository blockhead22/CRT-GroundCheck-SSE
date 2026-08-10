const test = require('node:test')
const assert = require('node:assert/strict')
const { dockBounds } = require('./window.cjs')
const { SidecarManager, resolveSidecarRuntime } = require('./sidecar.cjs')
const { configureDevUserData, devUserDataPath } = require('./dev-config.cjs')
const { AppBarManager } = require('./appbar.cjs')

test('dock snaps to the full left work area', () => {
  assert.deepEqual(
    dockBounds({ x: 0, y: 20, width: 1920, height: 1060 }),
    { x: 0, y: 20, width: 420, height: 1060 },
  )
  assert.equal(
    dockBounds({ x: -1920, y: 0, width: 1920, height: 1080 }, true).width,
    780,
  )
})

test('Windows AppBar reserves and releases the Electron dock edge', () => {
  const calls = []
  const handle = Buffer.alloc(8)
  handle.writeBigUInt64LE(4660n)
  const browserWindow = {
    getNativeWindowHandle: () => handle,
    isDestroyed: () => false,
  }
  const manager = new AppBarManager({
    platform: 'win32',
    scriptPath: 'C:\\fixture\\appbar.ps1',
    spawnSyncImpl: (_command, args) => {
      calls.push(args)
      const action = args[args.indexOf('-Action') + 1]
      return {
        status: 0,
        stdout: action === 'remove'
          ? '{"removed":true}\n'
          : '{"x":0,"y":40,"width":420,"height":1040}\n',
        stderr: '',
      }
    },
  })

  assert.deepEqual(
    manager.reserve(browserWindow, { x: 0, y: 0, width: 1920, height: 1080 }, 420),
    { x: 0, y: 40, width: 420, height: 1040 },
  )
  manager.reserve(browserWindow, { x: 0, y: 0, width: 1920, height: 1080 }, 780)
  assert.equal(calls[0][calls[0].indexOf('-Register') + 1], '1')
  assert.equal(calls[1][calls[1].indexOf('-Register') + 1], '0')
  assert.equal(manager.release(browserWindow), true)
  assert.equal(calls[2][calls[2].indexOf('-Action') + 1], 'remove')
  assert.equal(manager.activeHwnd, null)
})

test('AppBar is a no-op outside Windows', () => {
  let called = false
  const manager = new AppBarManager({
    platform: 'linux',
    spawnSyncImpl: () => { called = true },
  })
  assert.equal(manager.reserve({}, { x: 0, y: 0, width: 100, height: 100 }, 20), null)
  assert.equal(manager.release({}), false)
  assert.equal(called, false)
})

test('sidecar stop terminates its child process', () => {
  let killed = false
  const child = {
    stdout: { on() {} },
    stderr: { on() {} },
    on() {},
    kill() { killed = true },
  }
  const manager = new SidecarManager({ spawnImpl: () => child })
  manager.start()
  manager.stop()
  assert.equal(killed, true)
})

test('sidecar accepts only the expected canonical memory profile', () => {
  const manager = new SidecarManager({
    dataRoot: 'C:\\Users\\fixture\\.aether',
    profileId: '',
    platform: 'win32',
  })

  assert.equal(manager.expectedProfileMismatch({
    profile: { id: 'default', storage_scope: 'default_root' },
    substrate: { path: 'C:\\Users\\fixture\\.aether\\substrate.json' },
  }), '')
})

test('sidecar rejects a healthy process serving a different memory profile', () => {
  const manager = new SidecarManager({
    dataRoot: 'C:\\Users\\fixture\\.aether',
    profileId: '',
    platform: 'win32',
  })

  assert.match(manager.expectedProfileMismatch({
    profile: { id: 'local', storage_scope: 'profile_root' },
    substrate: {
      path: 'C:\\Temp\\aether-workbench-dev\\aether-state\\profiles\\local\\substrate.json',
    },
  }), /Wrong Aether profile connected/)
})

test('development sidecar enables exact Continuity product flags only for its child', () => {
  let spawnOptions
  const child = {
    stdout: { on() {} },
    stderr: { on() {} },
    on() {},
    kill() {},
  }
  const manager = new SidecarManager({
    env: { NODE_ENV: 'development', PATH: 'fixture-path' },
    spawnImpl: (_python, _args, options) => {
      spawnOptions = options
      return child
    },
  })

  manager.start()

  assert.equal(spawnOptions.env.AETHER_CONTINUITY_ENABLED, '1')
  assert.equal(spawnOptions.env.AETHER_CONTINUITY_MODEL_RENDER_ENABLED, '1')
  assert.match(spawnOptions.env.AETHER_CONTINUITY_ROOT, /aether-core$/)
  assert.equal(process.env.AETHER_CONTINUITY_ENABLED, undefined)
})

test('production sidecar leaves Continuity opt-in and preserves explicit development overrides', () => {
  const captures = []
  const child = {
    stdout: { on() {} },
    stderr: { on() {} },
    on() {},
    kill() {},
  }
  for (const env of [
    { NODE_ENV: 'production' },
    {
      NODE_ENV: 'development',
      AETHER_CONTINUITY_ENABLED: '0',
      AETHER_CONTINUITY_MODEL_RENDER_ENABLED: '0',
    },
  ]) {
    new SidecarManager({
      env,
      spawnImpl: (_python, _args, options) => {
        captures.push(options.env)
        return child
      },
    }).start()
  }

  assert.equal(captures[0].AETHER_CONTINUITY_ENABLED, undefined)
  assert.equal(captures[0].AETHER_CONTINUITY_MODEL_RENDER_ENABLED, undefined)
  assert.equal(captures[1].AETHER_CONTINUITY_ENABLED, '0')
  assert.equal(captures[1].AETHER_CONTINUITY_MODEL_RENDER_ENABLED, '0')
})

test('packaged sidecar uses its bundled executable and isolated profile state', () => {
  let capture
  const resourcesPath = 'C:\\Program Files\\Aether Workbench\\resources'
  const executable = `${resourcesPath}\\sidecar\\aether-sidecar.exe`
  const child = {
    stdout: { on() {} },
    stderr: { on() {} },
    on() {},
    kill() {},
  }
  const manager = new SidecarManager({
    env: { NODE_ENV: 'production', PYTHONPATH: 'D:\\AI_round2\\aether-core' },
    isPackaged: true,
    resourcesPath,
    platform: 'win32',
    existsSync: (candidate) => candidate === executable,
    dataRoot: 'C:\\fixture\\aether-state',
    profileId: 'atlas',
    spawnImpl: (command, args, options) => {
      capture = { command, args, options }
      return child
    },
  })

  manager.start()

  assert.equal(capture.command, executable)
  assert.deepEqual(capture.args, [])
  assert.equal(capture.options.env.AETHER_HOME, 'C:\\fixture\\aether-state')
  assert.equal(capture.options.env.AETHER_PROFILE_ID, 'atlas')
  assert.equal(capture.options.env.PYTHONPATH, undefined)
  assert.equal(capture.options.env.AETHER_WORKSPACE_ROOTS, undefined)
})

test('packaged runtime fails closed unless a bundled or explicit runtime exists', () => {
  assert.throws(
    () => resolveSidecarRuntime({
      env: {},
      isPackaged: true,
      resourcesPath: 'C:\\missing',
      platform: 'win32',
      existsSync: () => false,
    }),
    /no bundled sidecar/,
  )

  assert.deepEqual(
    resolveSidecarRuntime({
      env: { AETHER_PYTHON: 'C:\\AetherRuntime\\python.exe' },
      isPackaged: true,
      resourcesPath: 'C:\\missing',
      platform: 'win32',
      existsSync: () => false,
    }),
    {
      command: 'C:\\AetherRuntime\\python.exe',
      args: ['-m', 'aether.sidecar'],
      kind: 'configured-python',
    },
  )
})

test('development userData uses an isolated temp directory', () => {
  const calls = []
  const app = {
    getPath(name) {
      assert.equal(name, 'temp')
      return 'C:\\Temp'
    },
    setPath(name, value) {
      calls.push([name, value])
    },
  }

  const userDataPath = configureDevUserData(app, { NODE_ENV: 'development' })

  assert.equal(userDataPath, devUserDataPath(app))
  assert.deepEqual(calls, [['userData', 'C:\\Temp\\aether-workbench-dev']])
})

test('production userData is left unchanged', () => {
  const calls = []
  const app = {
    getPath() {
      throw new Error('getPath should not be called outside development')
    },
    setPath(name, value) {
      calls.push([name, value])
    },
  }

  assert.equal(configureDevUserData(app, { NODE_ENV: 'production' }), null)
  assert.deepEqual(calls, [])
})
