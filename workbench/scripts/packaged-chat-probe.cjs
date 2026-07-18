const fs = require('node:fs')
const path = require('node:path')

async function main() {
  const port = Number(process.argv[2] || 8765)
  const message = process.argv[3] || 'Compute nine plus four. Digits only.'
  const outputPath = process.argv[4] ? path.resolve(process.argv[4]) : ''
  const response = await fetch(`http://127.0.0.1:${port}/v1/chat/stream`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ message, model: 'qwen3:14b', voice_profile: 'warm' }),
  })
  if (!response.ok) throw new Error(`chat probe failed with HTTP ${response.status}`)
  const body = await response.text()
  if (outputPath) fs.writeFileSync(outputPath, body)
  const doneLines = body
    .split(/\r?\n/)
    .filter((line) => line === 'event: done' || line.startsWith('data: {"answer"'))
  console.log(doneLines.slice(-4).join('\n'))
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
