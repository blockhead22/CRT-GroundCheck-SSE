// ==UserScript==
// @name         CRT Browser Bridge (Local Only)
// @namespace    http://tampermonkey.net/
// @version      0.1.0
// @description  Local-only WebSocket bridge for read-only research helpers.
// @match        *://*/*
// @grant        none
// ==/UserScript==

(function () {
  'use strict';

  // --------- CONFIG ---------
  const WS_URL = 'ws://127.0.0.1:8765';
  const TOKEN = 'change-me'; // must match BROWSER_BRIDGE_TOKEN

  // Allowlist domains where commands may execute.
  // Examples: ['example.com', 'wikipedia.org']
  const ALLOWLIST = ['localhost'];

  // Write actions require confirmation by default.
  const CONFIRM_WRITE_ACTIONS = true;

  // --------- HELPERS ---------
  function domainAllowed() {
    try {
      const host = window.location.hostname || '';
      return ALLOWLIST.some(d => host === d || host.endsWith('.' + d));
    } catch (e) {
      return false;
    }
  }

  function safeText(s) {
    return (s || '').toString();
  }

  function pageText(maxChars = 20000) {
    const txt = document.body ? (document.body.innerText || '') : '';
    return txt.length > maxChars ? (txt.slice(0, maxChars) + '\n…') : txt;
  }

  function selectionText() {
    const sel = window.getSelection();
    return sel ? sel.toString() : '';
  }

  function querySelectorText(selector) {
    const el = document.querySelector(selector);
    if (!el) return '';
    return (el.innerText || el.textContent || '').toString();
  }

  function isWriteCommand(name) {
    return ['click_selector', 'type_selector', 'navigate'].includes(name);
  }

  // --------- WS ---------
  if (!domainAllowed()) {
    return;
  }

  let ws;

  function send(obj) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify(obj));
  }

  function connect() {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      send({
        type: 'hello',
        token: TOKEN,
        tab: { url: window.location.href, title: document.title }
      });
    };

    ws.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }

      if (msg.type !== 'command') return;

      const id = safeText(msg.id);
      const name = safeText(msg.name);
      const args = msg.args || {};

      if (!domainAllowed()) {
        send({ type: 'result', id, ok: false, error: 'domain_not_allowed' });
        return;
      }

      if (CONFIRM_WRITE_ACTIONS && isWriteCommand(name)) {
        const ok = window.confirm(`CRT bridge: allow command "${name}" on ${window.location.hostname}?`);
        if (!ok) {
          send({ type: 'result', id, ok: false, error: 'user_denied' });
          return;
        }
      }

      try {
        if (name === 'get_page_text') {
          send({ type: 'result', id, ok: true, data: { text: pageText() } });
          return;
        }
        if (name === 'get_selection') {
          send({ type: 'result', id, ok: true, data: { text: selectionText() } });
          return;
        }
        if (name === 'query_selector_text') {
          const selector = safeText(args.selector);
          send({ type: 'result', id, ok: true, data: { text: querySelectorText(selector), selector } });
          return;
        }

        send({ type: 'result', id, ok: false, error: 'unknown_command' });
      } catch (e) {
        send({ type: 'result', id, ok: false, error: 'exception', details: safeText(e && e.message) });
      }
    };

    ws.onclose = () => {
      // Reconnect with backoff
      setTimeout(connect, 2000);
    };
  }

  connect();
})();
