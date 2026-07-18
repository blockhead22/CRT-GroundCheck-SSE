const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const {
  DEFAULT_PROFILE_ID,
  resolveAetherDataRoot,
  resolveProfileId,
  resolveSidecarApiBase,
  resolveSidecarPort,
} = require('./data-lifecycle.cjs')

test('packaged data defaults below Electron userData and survives app replacement', () => {
  const userDataPath = path.join('C:', 'Users', 'fixture', 'AppData', 'Roaming', 'Aether Workbench')
  assert.equal(
    resolveAetherDataRoot({ env: {}, userDataPath }),
    path.join(path.resolve(userDataPath), 'aether-state'),
  )
  assert.equal(resolveProfileId({}), DEFAULT_PROFILE_ID)
})

test('an explicit isolated data root and synthetic profile are preserved exactly', () => {
  const explicitRoot = path.join('D:', 'fixture', 'isolated-aether')
  assert.equal(
    resolveAetherDataRoot({ env: { AETHER_HOME: explicitRoot }, userDataPath: 'ignored' }),
    path.resolve(explicitRoot),
  )
  assert.equal(resolveProfileId({ AETHER_PROFILE_ID: 'atlas-upgrade-2' }), 'atlas-upgrade-2')
})

test('unsafe profile identifiers fail before the sidecar is started', () => {
  assert.throws(
    () => resolveProfileId({ AETHER_PROFILE_ID: '../live' }),
    /AETHER_PROFILE_ID/,
  )
  assert.throws(
    () => resolveAetherDataRoot({ env: {}, userDataPath: '' }),
    /userData path/,
  )
})

test('renderer and sidecar share one validated loopback port', () => {
  const env = { AETHER_SIDECAR_PORT: '8878' }
  assert.equal(resolveSidecarPort(env), 8878)
  assert.equal(resolveSidecarApiBase(env), 'http://127.0.0.1:8878')
  assert.throws(() => resolveSidecarPort({ AETHER_SIDECAR_PORT: '0' }), /1 through 65535/)
  assert.throws(() => resolveSidecarPort({ AETHER_SIDECAR_PORT: 'nope' }), /1 through 65535/)
})
