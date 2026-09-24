/**
 * Replay the memory lifecycle in the Codex browser, using a dedicated QA backend.
 * No dependencies or model download. The caller verifies backend isolation.
 * Each step is bounded; finishTurn can be called again while a hosted call runs.
 *
 * const flow = new MemoryLifecycleBrowser(tab, { assertIsolated: async () => ... })
 * await flow.start(); await flow.submitSeed(); // then poll finishTurn('seed')
 * await flow.submitCorrection(); // finishTurn('correction')
 * await flow.submitHistory(); // finishTurn('history')
 * await flow.quarantineEmployer();
 * // Caller restarts the SAME isolated backend/profile, then:
 * await flow.submitRecall(); // finishTurn('restart')
 */
export class MemoryLifecycleBrowser {
  constructor(tab, { assertIsolated }) {
    if (typeof assertIsolated !== 'function') throw new Error('Isolation verifier required')
    this.tab = tab
    this.assertIsolated = assertIsolated
    this.results = []
    this.ready = false
    this.pending = false
  }
  role(role, name) { return this.tab.playwright.getByRole(role, { name, exact: true }) }
  async start() {
    await this.assertIsolated()
    await this.role('button', 'New chat').click()
    this.ready = true
    return { step: 'start', passed: true }
  }
  async submit(prompt) {
    if (!this.ready || this.pending) throw new Error('Start the isolated replay and finish the previous turn first')
    const before = await this.tab.playwright.domSnapshot()
    this.previousTurn = [...before.matchAll(/Why this answer for turn ([^"]+)/g)].at(-1)?.[1]
    await this.role('textbox', 'Message Aether').fill(prompt)
    await this.role('button', 'Send message').click()
    this.pending = true
  }
  submitSeed() { return this.submit('My name is Mara. My favorite color is teal. I work at Northstar Studio.') }
  submitCorrection() { return this.submit('Actually, my favorite color is violet now.') }
  submitHistory() { return this.submit('What was my favorite color before I changed it?') }
  submitRecall() { return this.submit('What are my saved name, favorite color, and employer?') }
  async finishTurn(step) {
    if (!this.pending) throw new Error('No submitted turn to verify')
    const dom = await this.tab.playwright.domSnapshot()
    if (dom.includes('button "Stop answering"')) return { step, pending: true }
    const latestTurn = [...dom.matchAll(/Why this answer for turn ([^"]+)/g)].at(-1)?.[1]
    if (!latestTurn || latestTurn === this.previousTurn) return { step, pending: true }
    const start = dom.lastIndexOf('  - generic: Æ')
    if (start < 0) throw new Error('No completed Aether answer found')
    const answer = dom.slice(start, dom.indexOf('  - textbox "Message Aether"', start))
    const expected = {
      seed: ['Mara', 'teal', 'Northstar Studio'],
      correction: ['violet'], history: ['teal'], restart: ['Mara', 'violet'],
    }[step]
    if (!expected) throw new Error('Unknown lifecycle step: '+step)
    const forbidden = {
      seed: [], correction: ['violet now'], history: ['violet'],
      restart: ['Northstar Studio'],
    }[step]
    const passed = expected.every(v => answer.includes(v)) &&
      forbidden.every(v => !answer.includes(v)) &&
      !answer.includes('Not released — failed a hard check') &&
      (step !== 'restart' || /not|withheld|unconfirmed|unknown|review/i.test(answer))
    const result = { step, passed, answer }
    this.results.push(result)
    this.pending = false
    if (!passed) throw new Error(JSON.stringify(result))
    return result
  }
  async quarantineEmployer() {
    if (this.pending) throw new Error('Finish the current turn first')
    const close = this.role('button', 'Close drawer')
    if (await close.count()) await close.click()
    await this.role('button', 'Knows').click()
    await this.role('button', 'Employer Northstar Studio OK').click()
    await this.role('button', 'Mark not trusted').click()
    const dom = await this.tab.playwright.domSnapshot()
    if (!dom.includes('Needs review')) throw new Error('Quarantine did not render')
    await this.role('button', 'Close drawer').click()
    const result = { step: 'quarantine', passed: true }
    this.results.push(result)
    return result
  }
}
