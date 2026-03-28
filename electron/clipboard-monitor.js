/**
 * ClipboardMonitor — watches the system clipboard for interesting content.
 *
 * Polls clipboard.readText() on an interval, deduplicates, and emits
 * 'capture' events when something worth remembering is detected.
 *
 * OFF by default (privacy-sensitive). Call start() to begin monitoring.
 */

const { clipboard } = require('electron');
const { EventEmitter } = require('events');

class ClipboardMonitor extends EventEmitter {
  /**
   * @param {object} opts
   * @param {number} opts.interval  Poll interval in ms (default 2000)
   * @param {number} opts.minLength Ignore strings shorter than this (default 10)
   * @param {number} opts.maxLength Ignore strings longer than this (default 5000)
   */
  constructor(opts = {}) {
    super();
    this.interval = opts.interval || 2000;
    this.minLength = opts.minLength || 10;
    this.maxLength = opts.maxLength || 5000;

    this._timer = null;
    this._lastContent = '';
    this._enabled = false;
  }

  /** Start polling the clipboard. */
  start() {
    if (this._timer) return;
    this._enabled = true;
    // Snapshot current clipboard so we don't immediately trigger on whatever's there
    this._lastContent = clipboard.readText() || '';
    this._timer = setInterval(() => this._poll(), this.interval);
    console.log('[clipboard] Monitor started');
  }

  /** Stop polling. */
  stop() {
    this._enabled = false;
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
    console.log('[clipboard] Monitor stopped');
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

  // ── Private ──────────────────────────────────────────────────────────

  _poll() {
    if (!this._enabled) return;

    let text;
    try {
      text = clipboard.readText();
    } catch {
      return; // clipboard not available
    }

    if (!text || text === this._lastContent) return;
    this._lastContent = text;

    // Length gates
    if (text.length < this.minLength || text.length > this.maxLength) return;

    if (this._isInteresting(text)) {
      this.emit('capture', text);
    }
  }

  /**
   * Heuristics for "interesting" clipboard content.
   * Returns true for multi-sentence text, code snippets, or structured data.
   */
  _isInteresting(text) {
    const trimmed = text.trim();

    // Skip single words (no spaces)
    if (!trimmed.includes(' ') && !trimmed.includes('\n')) return false;

    // Skip URL-only content
    if (/^https?:\/\/\S+$/i.test(trimmed)) return false;

    // Skip file paths only
    if (/^[A-Za-z]:\\[\w\\.\-]+$/.test(trimmed) || /^\/[\w/.\-]+$/.test(trimmed)) return false;

    // Detect code snippets: has newlines + code-like patterns
    if (trimmed.includes('\n')) {
      const codePatterns = [
        /function\s/,
        /const\s|let\s|var\s/,
        /def\s+\w+/,
        /class\s+\w+/,
        /import\s+/,
        /=>/,
        /\{[\s\S]*\}/,
        /if\s*\(/,
        /for\s*\(/,
        /return\s/,
      ];
      if (codePatterns.some((p) => p.test(trimmed))) return true;
    }

    // Detect structured data (JSON or YAML-like)
    if (/^\s*[\[{]/.test(trimmed) && /[\]}]\s*$/.test(trimmed)) return true;
    if (/^\w+:\s*.+/m.test(trimmed) && (trimmed.match(/^\w+:/gm) || []).length >= 2) return true;

    // Multi-sentence text (2+ sentence-ending punctuation marks)
    const sentenceEndings = (trimmed.match(/[.!?]\s/g) || []).length;
    if (sentenceEndings >= 1) return true;

    // Multi-line text with decent length (likely a paragraph or note)
    const lines = trimmed.split('\n').filter((l) => l.trim().length > 0);
    if (lines.length >= 3 && trimmed.length >= 80) return true;

    return false;
  }
}

module.exports = { ClipboardMonitor };
