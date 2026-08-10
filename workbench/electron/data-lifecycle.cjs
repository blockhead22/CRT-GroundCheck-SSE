const path = require('node:path')
const os = require('node:os')

const DEFAULT_PROFILE_ID = ''
const DEFAULT_SIDECAR_PORT = 8765
const PROFILE_ID_PATTERN = /^[a-z0-9][a-z0-9_-]{0,63}$/

function resolveAetherDataRoot({ env = process.env, homePath = os.homedir() }) {
  const explicitRoot = String(env.AETHER_HOME || '').trim()
  if (explicitRoot) return path.resolve(explicitRoot)
  if (!homePath) throw new Error('A stable home path is required for Aether data')
  return path.join(path.resolve(homePath), '.aether')
}

function resolveProfileId(env = process.env) {
  const value = String(env.AETHER_PROFILE_ID || DEFAULT_PROFILE_ID).trim().toLowerCase()
  if (!value) return DEFAULT_PROFILE_ID
  if (!PROFILE_ID_PATTERN.test(value)) {
    throw new Error('AETHER_PROFILE_ID must be 1-64 lowercase letters, digits, underscores, or hyphens')
  }
  return value
}

function resolveSidecarPort(env = process.env) {
  const value = Number(env.AETHER_SIDECAR_PORT || DEFAULT_SIDECAR_PORT)
  if (!Number.isInteger(value) || value < 1 || value > 65535) {
    throw new Error('AETHER_SIDECAR_PORT must be an integer from 1 through 65535')
  }
  return value
}

function resolveSidecarApiBase(env = process.env) {
  return `http://127.0.0.1:${resolveSidecarPort(env)}`
}

module.exports = {
  DEFAULT_PROFILE_ID,
  DEFAULT_SIDECAR_PORT,
  resolveAetherDataRoot,
  resolveProfileId,
  resolveSidecarApiBase,
  resolveSidecarPort,
}
