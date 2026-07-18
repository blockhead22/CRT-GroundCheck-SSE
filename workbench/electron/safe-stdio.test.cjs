const assert = require('node:assert/strict')
const { EventEmitter } = require('node:events')
const test = require('node:test')

const { guardParentPipe, writeLineSafely } = require('./safe-stdio.cjs')

function writableStream(overrides = {}) {
  const stream = new EventEmitter()
  stream.destroyed = false
  stream.writableEnded = false
  stream.writes = []
  stream.write = (value) => {
    stream.writes.push(value)
    return true
  }
  return Object.assign(stream, overrides)
}

test('guardParentPipe contains EPIPE and leaves the stream usable', () => {
  const stream = writableStream()
  let scheduled = 0

  assert.equal(guardParentPipe(stream, { scheduleThrow: () => { scheduled += 1 } }), true)
  stream.emit('error', Object.assign(new Error('broken pipe'), { code: 'EPIPE' }))

  assert.equal(scheduled, 0)
  assert.equal(writeLineSafely(stream, 'sidecar ready'), true)
  assert.deepEqual(stream.writes, ['sidecar ready\n'])
})

test('writeLineSafely skips an ended parent stream', () => {
  const stream = writableStream({ writableEnded: true })

  assert.equal(writeLineSafely(stream, 'ignored'), false)
  assert.deepEqual(stream.writes, [])
})

test('writeLineSafely contains a synchronous EPIPE write', () => {
  const stream = writableStream({
    write() {
      throw Object.assign(new Error('broken pipe'), { code: 'EPIPE' })
    },
  })

  assert.equal(writeLineSafely(stream, 'ignored'), false)
})

test('guardParentPipe surfaces unexpected stream errors', () => {
  const stream = writableStream()
  let scheduledThrow
  const error = Object.assign(new Error('device failure'), { code: 'EIO' })

  guardParentPipe(stream, { scheduleThrow: (callback) => { scheduledThrow = callback } })
  stream.emit('error', error)

  assert.equal(typeof scheduledThrow, 'function')
  assert.throws(scheduledThrow, error)
})
