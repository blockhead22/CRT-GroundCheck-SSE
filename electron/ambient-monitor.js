/**
 * AmbientMonitor — periodic screen capture for contextual awareness.
 *
 * Uses Electron's desktopCapturer to take screenshots at a configurable
 * interval, sends them to the backend vision endpoint for analysis, and
 * emits the resulting context description.
 *
 * OFF by default — privacy critical. Must be explicitly enabled.
 * Screenshots are never written to disk; processed in memory only.
 */

const { desktopCapturer, screen } = require('electron');
const { EventEmitter } = require('events');
const http = require('http');

class AmbientMonitor extends EventEmitter {
  /**
   * @param {object} opts
   * @param {number} opts.interval    Capture interval in ms (default 60000 = 1 min)
   * @param {number} opts.maxWidth    Max image width in px (default 1280 — token cost)
   * @param {string} opts.backendHost Backend hostname (default '127.0.0.1')
   * @param {number} opts.backendPort Backend port (default 8000)
   * @param {string} opts.threadId    Thread ID for memory storage (default 'default')
   */
  constructor(opts = {}) {
    super();
    this.interval = opts.interval || 60000;
    this.maxWidth = opts.maxWidth || 1280;
    this.backendHost = opts.backendHost || '127.0.0.1';
    this.backendPort = opts.backendPort || 8000;
    this.threadId = opts.threadId || 'default';

    this._timer = null;
    this._enabled = false;
    this._capturing = false; // guard against overlapping captures
  }

  /** Start periodic screen capture. */
  start() {
    if (this._timer) return;
    this._enabled = true;
    this._timer = setInterval(() => this._captureAndAnalyze(), this.interval);
    console.log(`[ambient] Monitor started (interval=${this.interval}ms)`);
  }

  /** Stop periodic capture. */
  stop() {
    this._enabled = false;
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
    console.log('[ambient] Monitor stopped');
  }

  /** Toggle on/off. Returns new enabled state. */
  toggle(enabled) {
    if (typeof enabled === 'boolean') {
      enabled ? this.start() : this.stop();
    } else {
      this._enabled ? this.stop() : this.start();
    }
    return this._enabled;
  }

  get enabled() {
    return this._enabled;
  }

  /** Manual single capture (used by IPC 'ambient:capture-now'). */
  async captureNow() {
    return this._captureAndAnalyze();
  }

  // ── Private ──────────────────────────────────────────────────────────

  async _captureAndAnalyze() {
    if (this._capturing) {
      console.log('[ambient] Skipping — previous capture still in progress');
      return;
    }
    this._capturing = true;

    try {
      const base64 = await this._captureScreen();
      if (!base64) {
        console.warn('[ambient] Screen capture returned empty');
        return;
      }

      this.emit('capture', { timestamp: Date.now() });

      const description = await this._sendToBackend(base64);
      if (description) {
        this.emit('context', { description, timestamp: Date.now() });
        console.log(`[ambient] Context: ${description.slice(0, 80)}...`);
      }
    } catch (err) {
      console.error('[ambient] Capture/analyze error:', err.message);
    } finally {
      this._capturing = false;
    }
  }

  async _captureScreen() {
    try {
      const sources = await desktopCapturer.getSources({
        types: ['screen'],
        thumbnailSize: this._getThumbnailSize(),
      });

      if (!sources || sources.length === 0) {
        console.warn('[ambient] No screen sources found');
        return null;
      }

      // Use primary display (first source)
      const source = sources[0];
      const thumbnail = source.thumbnail;

      if (thumbnail.isEmpty()) {
        console.warn('[ambient] Screenshot thumbnail is empty');
        return null;
      }

      // Convert to PNG base64 — thumbnail is already resized by thumbnailSize
      const pngBuffer = thumbnail.toPNG();
      return pngBuffer.toString('base64');
    } catch (err) {
      console.error('[ambient] desktopCapturer error:', err.message);
      return null;
    }
  }

  /**
   * Calculate thumbnail size that respects maxWidth while preserving aspect ratio.
   */
  _getThumbnailSize() {
    try {
      const primaryDisplay = screen.getPrimaryDisplay();
      const { width, height } = primaryDisplay.size;
      if (width <= this.maxWidth) {
        return { width, height };
      }
      const scale = this.maxWidth / width;
      return {
        width: this.maxWidth,
        height: Math.round(height * scale),
      };
    } catch {
      // Fallback if screen API isn't available
      return { width: this.maxWidth, height: 720 };
    }
  }

  /**
   * Send base64 image to backend for vision analysis.
   * Returns the description string, or null on failure.
   */
  _sendToBackend(imageBase64) {
    return new Promise((resolve) => {
      const payload = JSON.stringify({
        image_base64: imageBase64,
        thread_id: this.threadId,
        timestamp: Date.now() / 1000,
      });

      const req = http.request(
        {
          hostname: this.backendHost,
          port: this.backendPort,
          path: '/api/ambient/analyze',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(payload),
          },
          timeout: 30000, // vision API can be slow
        },
        (res) => {
          let body = '';
          res.on('data', (chunk) => { body += chunk; });
          res.on('end', () => {
            if (res.statusCode === 200) {
              try {
                const data = JSON.parse(body);
                resolve(data.description || null);
              } catch {
                console.warn('[ambient] Failed to parse backend response');
                resolve(null);
              }
            } else {
              console.warn(`[ambient] Backend returned ${res.statusCode}: ${body.slice(0, 200)}`);
              resolve(null);
            }
          });
        }
      );

      req.on('error', (err) => {
        console.warn('[ambient] Backend request failed:', err.message);
        resolve(null);
      });

      req.on('timeout', () => {
        req.destroy();
        console.warn('[ambient] Backend request timed out');
        resolve(null);
      });

      req.write(payload);
      req.end();
    });
  }
}

module.exports = { AmbientMonitor };
