/**
 * AetherSocket — WebSocket client for Aether.
 *
 * Replaces both:
 *   - streamFromCrtApi() (chat SSE streaming)
 *   - EventSource notification SSE
 *
 * One persistent bidirectional connection per client.
 * Auto-reconnects with exponential backoff.
 * Queues outbound messages while disconnected.
 */

import { getEffectiveApiBaseUrl, getAuthToken } from './api'
import { dispatchStreamEvent, isStreamEventType, type StreamCallbacks, type StreamEvent } from './streamEvents'

// ── Types ────────────────────────────────────────────────────────────

export type ClientMessage =
  | { type: 'ping' }
  | { type: 'subscribe'; channels: string[] }
  | { type: 'chat'; thread_id: string; message: string }

export type ServerEvent = {
  type: string
  content?: string
  phase?: string
  thread_id?: string
  subtype?: string
  metadata?: Record<string, unknown>
  ts?: number
  [key: string]: unknown
}

export type NotificationHandler = (event: ServerEvent) => void

// ── AetherSocket ─────────────────────────────────────────────────────

export class AetherSocket {
  private ws: WebSocket | null = null
  private url: string = ''
  private reconnectAttempts = 0
  private maxReconnectAttempts = 20
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private pingTimer: ReturnType<typeof setInterval> | null = null
  private outboundQueue: string[] = []
  private eventHandlers: Map<string, Array<(data: ServerEvent) => void>> = new Map()
  private globalHandlers: Array<(data: ServerEvent) => void> = []
  private _connected = false
  private _intentionalClose = false
  private subscribedChannels: Set<string> = new Set(['notifications'])

  /** Current active thread subscription for chat streaming */
  private activeThreadId: string | null = null
  /** StreamCallbacks wired for the active chat stream */
  private streamCallbacks: StreamCallbacks | null = null

  get connected(): boolean {
    return this._connected
  }

  // ── Lifecycle ────────────────────────────────────────────────────

  connect(url?: string): void {
    if (this.ws && this._connected) return

    this._intentionalClose = false

    if (url) {
      this.url = url
    } else {
      // Derive WS URL from API base
      const httpBase = getEffectiveApiBaseUrl()
      this.url = httpBase.replace(/^http/, 'ws') + '/ws'
      const token = getAuthToken()
      if (token) {
        this.url += `?token=${encodeURIComponent(token)}`
      }
    }

    this._doConnect()
  }

  disconnect(): void {
    this._intentionalClose = true
    this._cleanup()
  }

  // ── Messaging ────────────────────────────────────────────────────

  send(message: ClientMessage): void {
    if (message.type === 'subscribe') {
      for (const channel of message.channels) {
        const clean = String(channel || '').trim()
        if (clean) this.subscribedChannels.add(clean)
      }
    }
    const raw = JSON.stringify(message)
    if (this.ws && this._connected) {
      this.ws.send(raw)
    } else {
      this.outboundQueue.push(raw)
    }
  }

  /**
   * Stream a chat message through WS, dispatching to StreamCallbacks.
   * Drop-in replacement for streamFromCrtApi().
   */
  streamChat(threadId: string, message: string, callbacks: StreamCallbacks): void {
    this.activeThreadId = threadId
    this.streamCallbacks = callbacks

    // Subscribe to thread events
    this.subscribeToThread(threadId)
    // Send chat
    this.send({ type: 'chat', thread_id: threadId, message })
  }

  subscribe(channels: string[]): void {
    const unique = Array.from(
      new Set(
        channels
          .map((channel) => String(channel || '').trim())
          .filter(Boolean),
      ),
    )
    if (unique.length === 0) return
    this.send({ type: 'subscribe', channels: unique })
  }

  subscribeToThread(threadId: string): void {
    const clean = String(threadId || '').trim()
    if (!clean) return
    this.subscribe([`thread:${clean}`])
  }

  // ── Event subscription ──────────────────────────────────────────

  /** Subscribe to a specific event type */
  onEvent(type: string, handler: (data: ServerEvent) => void): () => void {
    if (!this.eventHandlers.has(type)) {
      this.eventHandlers.set(type, [])
    }
    this.eventHandlers.get(type)!.push(handler)
    return () => {
      const arr = this.eventHandlers.get(type)
      if (arr) {
        const idx = arr.indexOf(handler)
        if (idx >= 0) arr.splice(idx, 1)
      }
    }
  }

  /** Subscribe to all events */
  onAny(handler: (data: ServerEvent) => void): () => void {
    this.globalHandlers.push(handler)
    return () => {
      const idx = this.globalHandlers.indexOf(handler)
      if (idx >= 0) this.globalHandlers.splice(idx, 1)
    }
  }

  // ── Internals ────────────────────────────────────────────────────

  private _doConnect(): void {
    try {
      this.ws = new WebSocket(this.url)
    } catch (e) {
      console.error('[AetherSocket] Failed to create WebSocket:', e)
      this._scheduleReconnect()
      return
    }

    this.ws.onopen = () => {
      console.log('[AetherSocket] Connected')
      this._connected = true
      this.reconnectAttempts = 0
      this._startPing()
      this._flushQueue()
      this._resubscribe()
    }

    this.ws.onmessage = (evt) => {
      try {
        const event: ServerEvent = JSON.parse(evt.data)
        this._dispatch(event)
      } catch (e) {
        console.warn('[AetherSocket] Failed to parse message:', evt.data, e)
      }
    }

    this.ws.onclose = () => {
      this._connected = false
      this._stopPing()
      if (!this._intentionalClose) {
        console.log('[AetherSocket] Disconnected, will reconnect...')
        this._scheduleReconnect()
      }
    }

    this.ws.onerror = (e) => {
      console.error('[AetherSocket] Error:', e)
    }
  }

  private _dispatch(event: ServerEvent): void {
    const type = event.type

    // Forward to global handlers
    for (const handler of this.globalHandlers) {
      try { handler(event) } catch (e) { console.error('[AetherSocket] Handler error:', e) }
    }

    // Forward to type-specific handlers
    const handlers = this.eventHandlers.get(type)
    if (handlers) {
      for (const handler of handlers) {
        try { handler(event) } catch (e) { console.error('[AetherSocket] Handler error:', e) }
      }
    }

    // Dispatch to StreamCallbacks if active chat stream
    if (this.streamCallbacks) {
      this._dispatchToStreamCallbacks(event)
    }
  }

  /**
   * Map WS events to the same StreamCallbacks interface used by SSE.
   * This is the bridge that makes WS a drop-in replacement.
   */
  private _dispatchToStreamCallbacks(event: ServerEvent): void {
    const cb = this.streamCallbacks
    if (!cb) return
    if (!isStreamEventType(String(event.type ?? ''))) return

    dispatchStreamEvent(event as StreamEvent, cb)

    if (event.type === 'done' || event.type === 'error') {
      this.streamCallbacks = null
      this.activeThreadId = null
    }
  }

  private _startPing(): void {
    this._stopPing()
    this.pingTimer = setInterval(() => {
      if (this.ws && this._connected) {
        this.ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 25_000) // 25s, under Cloudflare's 30s timeout
  }

  private _stopPing(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer)
      this.pingTimer = null
    }
  }

  private _flushQueue(): void {
    while (this.outboundQueue.length > 0) {
      const msg = this.outboundQueue.shift()!
      if (this.ws && this._connected) {
        this.ws.send(msg)
      }
    }
  }

  private _resubscribe(): void {
    const channels = Array.from(this.subscribedChannels)
    if (channels.length === 0) return
    if (this.ws && this._connected) {
      this.ws.send(JSON.stringify({ type: 'subscribe', channels }))
    }
  }

  private _scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[AetherSocket] Max reconnect attempts reached')
      return
    }

    // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30_000)
    this.reconnectAttempts++
    console.log(`[AetherSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)

    this.reconnectTimer = setTimeout(() => {
      this._doConnect()
    }, delay)
  }

  private _cleanup(): void {
    this._stopPing()
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.onopen = null
      this.ws.onmessage = null
      this.ws.onclose = null
      this.ws.onerror = null
      this.ws.close()
      this.ws = null
    }
    this._connected = false
  }
}

// ── Singleton ────────────────────────────────────────────────────────

let _instance: AetherSocket | null = null

export function getAetherSocket(): AetherSocket {
  if (!_instance) {
    _instance = new AetherSocket()
  }
  return _instance
}
