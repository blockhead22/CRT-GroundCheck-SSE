const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

const workbenchRoot = path.resolve(__dirname, '..')
const coreRoot = path.resolve(workbenchRoot, '..', 'aether-core')
const buildRoot = path.join(workbenchRoot, '.packaging', 'sidecar')
const venvRoot = path.join(buildRoot, 'venv')
const distRoot = path.join(buildRoot, 'dist')
const workRoot = path.join(buildRoot, 'work')
const specRoot = path.join(buildRoot, 'spec')
const venvPython = process.platform === 'win32'
  ? path.join(venvRoot, 'Scripts', 'python.exe')
  : path.join(venvRoot, 'bin', 'python')

function run(command, args) {
  const result = spawnSync(command, args, {
    cwd: workbenchRoot,
    env: process.env,
    stdio: 'inherit',
    windowsHide: true,
  })
  if (result.status !== 0) {
    throw new Error(`${command} exited with status ${result.status}`)
  }
}

fs.mkdirSync(buildRoot, { recursive: true })
if (!fs.existsSync(venvPython)) {
  run(process.env.AETHER_BUILD_PYTHON || 'python', ['-m', 'venv', venvRoot])
}

run(venvPython, [
  '-m', 'pip', 'install', '--disable-pip-version-check',
  'pyinstaller==6.14.2',
  `${coreRoot}[workbench,graph]`,
])

fs.rmSync(distRoot, { recursive: true, force: true })
fs.rmSync(workRoot, { recursive: true, force: true })
fs.rmSync(specRoot, { recursive: true, force: true })
fs.mkdirSync(distRoot, { recursive: true })
fs.mkdirSync(workRoot, { recursive: true })
fs.mkdirSync(specRoot, { recursive: true })

run(venvPython, [
  '-m', 'PyInstaller',
  '--noconfirm',
  '--clean',
  '--onedir',
  '--name', 'aether-sidecar',
  '--distpath', distRoot,
  '--workpath', workRoot,
  '--specpath', specRoot,
  '--hidden-import', 'uvicorn.logging',
  '--hidden-import', 'uvicorn.loops.auto',
  '--hidden-import', 'uvicorn.protocols.http.auto',
  '--hidden-import', 'uvicorn.protocols.websockets.auto',
  '--hidden-import', 'uvicorn.lifespan.on',
  path.join(__dirname, 'sidecar-entry.py'),
])

const bundleRoot = path.join(distRoot, 'aether-sidecar')
const executable = path.join(bundleRoot, process.platform === 'win32' ? 'aether-sidecar.exe' : 'aether-sidecar')
if (!fs.existsSync(executable)) {
  throw new Error(`PyInstaller did not produce ${executable}`)
}
const runtimeProbe = spawnSync(venvPython, [
  '-c',
  'import importlib.metadata,json,platform; print(json.dumps({"coreVersion": importlib.metadata.version("aether-core"), "python": platform.python_version()}))',
], { encoding: 'utf8', windowsHide: true })
if (runtimeProbe.status !== 0) throw new Error('Could not read bundled runtime versions')
const runtimeVersions = JSON.parse(runtimeProbe.stdout.trim())

fs.writeFileSync(
  path.join(bundleRoot, 'runtime.json'),
  `${JSON.stringify({
    format: 'aether.sidecar.runtime.v1',
    ...runtimeVersions,
    extras: ['graph', 'workbench'],
  }, null, 2)}\n`,
)
console.log(`Bundled sidecar ready: ${executable}`)
