const guardedStreams = new WeakSet()

function guardParentPipe(stream, { scheduleThrow = setImmediate } = {}) {
  if (!stream || typeof stream.on !== 'function') return false
  if (guardedStreams.has(stream)) return true

  guardedStreams.add(stream)
  stream.on('error', (error) => {
    if (error?.code === 'EPIPE') return
    scheduleThrow(() => {
      throw error
    })
  })
  return true
}

function writeLineSafely(stream, message) {
  if (!stream || typeof stream.write !== 'function') return false
  if (stream.destroyed || stream.writableEnded) return false

  const text = String(message)
  const line = text.endsWith('\n') ? text : `${text}\n`
  try {
    stream.write(line)
    return true
  } catch (error) {
    if (error?.code === 'EPIPE') return false
    throw error
  }
}

module.exports = { guardParentPipe, writeLineSafely }
