const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

const preloadSource = fs.readFileSync(path.join(__dirname, 'preload.cjs'), 'utf8')

function executePreload(argv) {
  let exposed
  const electron = {
    contextBridge: {
      exposeInMainWorld(name, value) {
        exposed = { name, value }
      },
    },
    ipcRenderer: {
      invoke() {},
      send() {},
      on() {},
      removeListener() {},
    },
  }
  const context = {
    process: { argv },
    require(moduleId) {
      if (moduleId === 'electron') return electron
      throw new Error(`Sandboxed preload cannot require ${moduleId}`)
    },
  }

  vm.runInNewContext(preloadSource, context, { filename: 'preload.cjs' })
  return exposed
}

test('sandboxed preload receives the sidecar API base without local module imports', () => {
  const exposed = executePreload([
    'electron.exe',
    '--aether-sidecar-api-base=http://127.0.0.1:8878',
  ])

  assert.equal(exposed.name, 'aetherDesktop')
  assert.equal(exposed.value.apiBase, 'http://127.0.0.1:8878')
})

test('sandboxed preload fails closed when the main process omits the API base', () => {
  assert.throws(
    () => executePreload(['electron.exe']),
    /did not provide the Aether sidecar API base/,
  )
})
