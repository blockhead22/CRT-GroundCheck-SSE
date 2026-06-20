const test = require('node:test')
const assert = require('node:assert/strict')
const { dockBounds } = require('./window.cjs')
const { SidecarManager } = require('./sidecar.cjs')

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
