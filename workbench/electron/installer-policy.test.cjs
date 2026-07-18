const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const installerPolicy = fs.readFileSync(path.join(__dirname, '..', 'installer.nsh'), 'utf8')

test('silent uninstall keeps profile data unless removal is explicitly requested', () => {
  assert.match(installerPolicy, /ReadEnvStr \$R0 "AETHER_REMOVE_PROFILE_DATA"/)
  assert.match(installerPolicy, /StrCmp \$R0 "1" remove_aether_profile_data/)
  assert.match(installerPolicy, /IfSilent keep_aether_profile_data/)
})

test('uninstall removal is scoped to the Aether state child only', () => {
  const removeCommands = installerPolicy
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.startsWith('RMDir /r'))

  assert.equal(removeCommands.length, 3)
  for (const command of removeCommands) assert.match(command, /\\aether-state"$/)
})
