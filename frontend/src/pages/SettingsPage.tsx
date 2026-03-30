import { useState, useEffect } from 'react'
import { getProfile, updateAuthProfile, setProfileFacts, setProfileName, getCloudSettings, updateCloudSettings, getCloudUsage, getAvailableModels } from '../lib/api'
import type { AuthUser, CloudSettings, CloudUsage, AvailableModels } from '../lib/api'

type Props = {
  authUser: AuthUser | null
  threadId: string
  onDisplayNameChanged: (name: string) => void
  onProfileUpdated: () => void
}

type SettingsTab = 'profile' | 'cloud' | 'desktop' | 'browser' | 'heartbeat' | 'behavior' | 'tooling' | 'facts' | 'account'

const ESCALATION_OPTIONS = [
  { value: 'conservative', label: 'Conservative' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'cost_saver', label: 'Cost Saver' },
  { value: 'local_only', label: 'Local Only' },
]

function Toggle({ label, checked, onChange, description }: {
  label: string; checked: boolean; onChange: (v: boolean) => void; description?: string
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex-1">
        <div className="text-sm text-white/80">{label}</div>
        {description && <div className="text-xs text-white/40 mt-0.5">{description}</div>}
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={`relative flex-shrink-0 h-6 w-11 rounded-full transition-colors ${checked ? '' : 'bg-white/10'}`}
        style={checked ? { backgroundColor: 'var(--accent)' } : undefined}
      >
        <span className={`block absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-5' : 'translate-x-0'}`} />
      </button>
    </div>
  )
}

function SectionCard({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="rounded border border-white/10 bg-white/[0.03] p-6">
      <div className="mb-3 text-xs font-medium uppercase tracking-wide text-white/50">{title}</div>
      {description && <p className="mb-4 text-xs text-white/40">{description}</p>}
      {children}
    </div>
  )
}

export function SettingsPage({ authUser, threadId, onDisplayNameChanged, onProfileUpdated }: Props) {
  const [tab, setTab] = useState<SettingsTab>('profile')
  const [displayName, setDisplayName] = useState('')
  const [nickname, setNickname] = useState('')
  const [agentName, setAgentName] = useState('Aether')
  const [slots, setSlots] = useState<Record<string, string>>({})
  const [newFactKey, setNewFactKey] = useState('')
  const [newFactValue, setNewFactValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // Cloud settings state
  const [cloudSettings, setCloudSettingsState] = useState<CloudSettings | null>(null)
  const [cloudUsage, setCloudUsage] = useState<CloudUsage | null>(null)
  const [cloudSaving, setCloudSaving] = useState(false)

  // Tooling tab state
  const [availableModels, setAvailableModels] = useState<AvailableModels | null>(null)

  // Load profile on mount
  useEffect(() => {
    setDisplayName(authUser?.display_name || '')
    setSaved(false)

    getProfile(threadId).then((p) => {
      setSlots(p.slots || {})
    }).catch(() => {})

    // Load cloud settings (includes preferred_nickname and agent_name)
    getCloudSettings().then((cs) => {
      setCloudSettingsState(cs)
      if (cs?.preferred_nickname) setNickname(cs.preferred_nickname)
      if (cs?.agent_name) setAgentName(cs.agent_name)
    }).catch(() => {})
    getCloudUsage().then(setCloudUsage).catch(() => {})
    getAvailableModels().then(setAvailableModels).catch(() => {})
  }, [threadId, authUser])

  // POLLING FIX: cloud-usage interval raised from 10s to 30s; pauses when tab is hidden
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null

    function start() {
      if (interval) return
      interval = setInterval(() => {
        getCloudUsage().then(setCloudUsage).catch(() => {})
      }, 30000)
    }
    function stop() {
      if (interval) { clearInterval(interval); interval = null }
    }
    function onVisibility() {
      if (document.hidden) stop(); else start()
    }

    if (!document.hidden) start()
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      stop()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  async function handleSave() {
    setSaving(true)
    try {
      if (displayName.trim()) {
        try {
          const res = await updateAuthProfile({ display_name: displayName.trim() })
          if (res.ok) onDisplayNameChanged(displayName.trim())
        } catch {
          // No auth session — still update via profile name
        }
        onDisplayNameChanged(displayName.trim())
      }

      // Save nickname and agent name as auth settings
      const settingsToSave: Record<string, string> = {}
      if (nickname.trim() !== (cloudSettings?.preferred_nickname || '')) {
        settingsToSave.preferred_nickname = nickname.trim()
      }
      if (agentName.trim() !== (cloudSettings?.agent_name || 'Aether')) {
        settingsToSave.agent_name = agentName.trim()
      }
      if (Object.keys(settingsToSave).length > 0) {
        await updateCloudSettings(settingsToSave)
        setCloudSettingsState((prev) => prev ? { ...prev, ...settingsToSave } : prev)
      }

      if (displayName.trim()) {
        await setProfileName({ threadId, name: displayName.trim() })
      }

      onProfileUpdated()
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      console.error('Settings save failed:', e)
    } finally {
      setSaving(false)
    }
  }

  async function handleAddFact() {
    if (!newFactKey.trim() || !newFactValue.trim()) return
    setSaving(true)
    try {
      await setProfileFacts(threadId, { [newFactKey.trim()]: newFactValue.trim() })
      setSlots((prev) => ({ ...prev, [newFactKey.trim()]: newFactValue.trim() }))
      setNewFactKey('')
      setNewFactValue('')
      onProfileUpdated()
    } catch (e) {
      console.error('Add fact failed:', e)
    } finally {
      setSaving(false)
    }
  }

  async function handleCloudToggle(key: string, value: boolean) {
    if (!cloudSettings) return
    const useTrueFalse = key.startsWith('cloud_claude_') || key.startsWith('desktop_') || key.startsWith('browser_') || key.startsWith('intuition_check_') || key.startsWith('heartbeat_') || key.startsWith('background_') || key.startsWith('greeting_') || key.startsWith('conflict_') || key.startsWith('provenance_') || key.startsWith('tooling_') || key === 'bypass_crt' || key === 'enable_tooling' || key === 'synthesis_enabled'
    const newVal = useTrueFalse ? (value ? 'true' : 'false') : (value ? 'on' : 'off')
    const oldVal = useTrueFalse ? (value ? 'false' : 'true') : (value ? 'off' : 'on')
    setCloudSettingsState({ ...cloudSettings, [key]: newVal })
    setCloudSaving(true)
    try {
      await updateCloudSettings({ [key]: newVal })
    } catch (e) {
      console.error('Cloud setting update failed:', e)
      setCloudSettingsState({ ...cloudSettings, [key]: oldVal })
    } finally {
      setCloudSaving(false)
    }
  }

  async function handleCloudSelect(key: string, value: string) {
    if (!cloudSettings) return
    setCloudSettingsState({ ...cloudSettings, [key]: value })
    setCloudSaving(true)
    try {
      await updateCloudSettings({ [key]: value })
    } catch (e) {
      console.error('Cloud setting update failed:', e)
    } finally {
      setCloudSaving(false)
    }
  }

  async function handleCloudSlider(key: string, value: string) {
    if (!cloudSettings) return
    setCloudSettingsState({ ...cloudSettings, [key]: value })
  }

  async function commitCloudSlider(key: string) {
    if (!cloudSettings) return
    setCloudSaving(true)
    try {
      await updateCloudSettings({ [key]: cloudSettings[key] })
    } catch (e) {
      console.error('Cloud setting update failed:', e)
    } finally {
      setCloudSaving(false)
    }
  }

  async function handleCloudNumberInput(key: string, value: string) {
    if (!cloudSettings) return
    setCloudSettingsState({ ...cloudSettings, [key]: value })
    setCloudSaving(true)
    try {
      await updateCloudSettings({ [key]: value })
    } catch (e) {
      console.error('Cloud setting update failed:', e)
    } finally {
      setCloudSaving(false)
    }
  }

  // Claude master toggle state for disabling sub-toggles
  const claudeEnabled = cloudSettings?.cloud_claude_enabled === 'true' || cloudSettings?.cloud_claude_enabled === 'on'

  const tabs: Array<{ id: SettingsTab; label: string }> = [
    { id: 'profile', label: 'Profile' },
    { id: 'cloud', label: 'Cloud & Models' },
    { id: 'desktop', label: 'Desktop' },
    { id: 'browser', label: 'Browser' },
    { id: 'heartbeat', label: 'Heartbeat' },
    { id: 'behavior', label: 'Behavior' },
    { id: 'tooling', label: 'Tooling' },
    { id: 'facts', label: 'Facts' },
    { id: 'account', label: 'Account' },
  ]

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
        <div>
          <div className="text-lg font-semibold text-white">Settings</div>
          <div className="mt-1 text-sm text-white/60">Manage your profile, cloud features, and account</div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 rounded border border-white/10 bg-white/5 p-1 flex-wrap">
            {tabs.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={
                  'rounded px-3 py-2 text-xs font-semibold transition-colors ' +
                  (tab === t.id ? 'text-white' : 'text-white/70 hover:bg-white/10')
                }
                style={tab === t.id ? { backgroundColor: 'var(--accent)' } : undefined}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-5">
        <div className={`mx-auto space-y-6 ${tab === 'cloud' ? 'max-w-5xl' : 'max-w-2xl'}`}>
          {/* ═══════════════════ PROFILE TAB ═══════════════════ */}
          {tab === 'profile' && (
            <>
              <SectionCard title="Profile">
                <div className="space-y-4">
                  <div>
                    <label className="mb-1.5 block text-sm text-white/70">Display Name</label>
                    <input
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      placeholder="Your name"
                      className="w-full rounded glass-field px-4 py-2.5 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-1 focus:ring-white/20"
                    />
                    <p className="mt-1 text-xs text-white/40">Shown in the topbar and profile</p>
                  </div>

                  <div>
                    <label className="mb-1.5 block text-sm text-white/70">Preferred Nickname</label>
                    <input
                      value={nickname}
                      onChange={(e) => setNickname(e.target.value)}
                      placeholder="What should the agent call you?"
                      className="w-full rounded glass-field px-4 py-2.5 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-1 focus:ring-white/20"
                    />
                    <p className="mt-1 text-xs text-white/40">The agent will use this name when talking to you</p>
                  </div>

                  <div>
                    <label className="mb-1.5 block text-sm text-white/70">Agent Name</label>
                    <input
                      value={agentName}
                      onChange={(e) => setAgentName(e.target.value)}
                      placeholder="Aether"
                      className="w-full rounded glass-field px-4 py-2.5 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-1 focus:ring-white/20"
                    />
                    <p className="mt-1 text-xs text-white/40">Your AI agent's name — shown in chat and system prompts</p>
                  </div>
                </div>

                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="mt-4 rounded bg-white/10 px-5 py-2 text-sm font-medium text-white transition-all hover:bg-white/20 disabled:opacity-50"
                >
                  {saving ? 'Saving...' : saved ? 'Saved' : 'Save Profile'}
                </button>
              </SectionCard>
            </>
          )}

          {/* ═══════════════════ CLOUD TAB ═══════════════════ */}
          {tab === 'cloud' && (
            <>
              {/* Two-column grid: Cloud Features | Claude */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* LEFT: Cloud Features (Tier 1 / OpenAI) */}
                <SectionCard title="Cloud Features" description="Cloud LLM verification for CRT operations. Uses gpt-4o-mini (Tier 1).">
                  {cloudSettings ? (
                    <div className="space-y-1">
                      <Toggle
                        label="Slot Classification"
                        description="Cloud-powered fact extraction from user statements"
                        checked={cloudSettings.cloud_slot_classification === 'on'}
                        onChange={(v) => handleCloudToggle('cloud_slot_classification', v)}
                      />
                      <Toggle
                        label="NLI Contradiction Detection"
                        description="Natural language inference to catch conflicting facts"
                        checked={cloudSettings.cloud_nli_contradiction === 'on'}
                        onChange={(v) => handleCloudToggle('cloud_nli_contradiction', v)}
                      />
                      <Toggle
                        label="Reflection Validation"
                        description="Epistemic audit of self-model updates"
                        checked={cloudSettings.cloud_reflection_validation === 'on'}
                        onChange={(v) => handleCloudToggle('cloud_reflection_validation', v)}
                      />

                      <div className="pt-3">
                        <label className="mb-1.5 block text-sm text-white/70">Escalation Policy</label>
                        <select
                          value={cloudSettings.cloud_escalation_policy}
                          onChange={(e) => handleCloudSelect('cloud_escalation_policy', e.target.value)}
                          className="w-full rounded glass-field px-4 py-2.5 text-sm text-white bg-transparent focus:outline-none focus:ring-1 focus:ring-white/20"
                        >
                          {ESCALATION_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value} className="bg-gray-900">{opt.label}</option>
                          ))}
                        </select>
                        <p className="mt-1 text-xs text-white/40">Controls when local results escalate to cloud verification</p>
                      </div>

                      <div className="pt-3">
                        <label className="mb-1.5 block text-sm text-white/70">
                          Confidence Threshold: {cloudSettings.cloud_confidence_threshold}
                        </label>
                        <input
                          type="range" min="0.5" max="1.0" step="0.05"
                          value={cloudSettings.cloud_confidence_threshold}
                          onChange={(e) => handleCloudSlider('cloud_confidence_threshold', e.target.value)}
                          onMouseUp={() => commitCloudSlider('cloud_confidence_threshold')}
                          onTouchEnd={() => commitCloudSlider('cloud_confidence_threshold')}
                          className="w-full"
                          style={{ accentColor: 'var(--accent)' }}
                        />
                        <p className="mt-1 text-xs text-white/40">Below this threshold, results may be escalated to cloud</p>
                      </div>

                      <div className="pt-3">
                        <label className="mb-1.5 block text-sm text-white/70">
                          Daily Limit Multiplier: {cloudSettings.cloud_daily_limit_multiplier}x
                        </label>
                        <input
                          type="range" min="0" max="3.0" step="0.5"
                          value={cloudSettings.cloud_daily_limit_multiplier}
                          onChange={(e) => handleCloudSlider('cloud_daily_limit_multiplier', e.target.value)}
                          onMouseUp={() => commitCloudSlider('cloud_daily_limit_multiplier')}
                          onTouchEnd={() => commitCloudSlider('cloud_daily_limit_multiplier')}
                          className="w-full"
                          style={{ accentColor: 'var(--accent)' }}
                        />
                        <p className="mt-1 text-xs text-white/40">Scale daily call limits up or down (0 = disabled)</p>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-white/40">Loading cloud settings...</p>
                  )}
                </SectionCard>

                {/* RIGHT: Claude (Tier 2) */}
                <SectionCard title="Claude (Tier 2)" description="High-quality generation fallback and reflection validation.">
                  <p className="text-xs text-white/40 -mt-2 mb-3">
                    {cloudUsage?.claude_available === false && (
                      <span className="text-amber-400/80">Cookie not configured.</span>
                    )}
                    {cloudUsage?.claude_available === true && (
                      <span className="text-green-400/80">Cookie active.</span>
                    )}
                  </p>

                  {cloudSettings ? (
                    <div className="space-y-1">
                      <Toggle
                        label="Enable Claude"
                        description="Master toggle for all Claude features"
                        checked={claudeEnabled}
                        onChange={(v) => handleCloudToggle('cloud_claude_enabled', v)}
                      />
                      <div className={claudeEnabled ? '' : 'opacity-40 pointer-events-none'}>
                        <Toggle
                          label="Use for generation fallback"
                          description="Escalate to Claude when OpenAI fails or returns low confidence"
                          checked={cloudSettings.cloud_claude_generation === 'true' || cloudSettings.cloud_claude_generation === 'on'}
                          onChange={(v) => handleCloudToggle('cloud_claude_generation', v)}
                        />
                        <Toggle
                          label="Use for reflection validation"
                          description="Use Claude for epistemic audits of self-model updates"
                          checked={cloudSettings.cloud_claude_reflection === 'true' || cloudSettings.cloud_claude_reflection === 'on'}
                          onChange={(v) => handleCloudToggle('cloud_claude_reflection', v)}
                        />

                        <div className="pt-3">
                          <label className="mb-1.5 block text-sm text-white/70">Daily Call Limit</label>
                          <input
                            type="number" min="0" max="100"
                            value={cloudSettings.cloud_claude_daily_limit || '20'}
                            onChange={(e) => {
                              if (!cloudSettings) return
                              setCloudSettingsState({ ...cloudSettings, cloud_claude_daily_limit: e.target.value })
                            }}
                            onBlur={(e) => handleCloudNumberInput('cloud_claude_daily_limit', e.target.value)}
                            className="w-full rounded glass-field px-4 py-2.5 text-sm text-white bg-transparent focus:outline-none focus:ring-1 focus:ring-white/20"
                          />
                          <p className="mt-1 text-xs text-white/40">Maximum Claude calls per day (all features combined)</p>
                        </div>

                        <div className="pt-3">
                          <label className="mb-1.5 block text-sm text-white/70">Max Tokens per Call</label>
                          <input
                            type="number" min="256" max="8192" step="256"
                            value={cloudSettings.cloud_claude_max_tokens || '4096'}
                            onChange={(e) => {
                              if (!cloudSettings) return
                              setCloudSettingsState({ ...cloudSettings, cloud_claude_max_tokens: e.target.value })
                            }}
                            onBlur={(e) => handleCloudNumberInput('cloud_claude_max_tokens', e.target.value)}
                            className="w-full rounded glass-field px-4 py-2.5 text-sm text-white bg-transparent focus:outline-none focus:ring-1 focus:ring-white/20"
                          />
                          <p className="mt-1 text-xs text-white/40">Maximum tokens per Claude API call</p>
                        </div>
                      </div>

                      {cloudUsage && (cloudUsage.claude_calls_today != null || cloudUsage.claude_generation) && (
                        <div className="mt-3 pt-3 border-t border-white/10">
                          <div className="text-xs text-white/50 mb-1">Today's Claude Usage</div>
                          <div className="flex justify-between text-xs text-white/60">
                            <span>Calls</span>
                            <span>{cloudUsage.claude_calls_today ?? 0} / {cloudUsage.claude_daily_limit ?? 20}</span>
                          </div>
                          <div className="flex justify-between text-xs text-white/60">
                            <span>Estimated tokens</span>
                            <span>~{cloudUsage.claude_tokens_today ?? 0}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="text-sm text-white/40">Loading Claude settings...</p>
                  )}
                </SectionCard>
              </div>

              {/* Intuition Check (full width below grid) */}
              <SectionCard title="Intuition Check" description="Lightweight LLM side-channel (~150ms) for situational awareness. Clarifies ambiguous input, suggests next steps after tasks, and reconnects after idle periods.">
                {cloudSettings ? (
                  <div className="space-y-1">
                    <Toggle
                      label="Enable Intuition Check"
                      description="Master toggle for all intuition check features"
                      checked={cloudSettings.intuition_check_enabled === 'true'}
                      onChange={(v) => handleCloudToggle('intuition_check_enabled', v)}
                    />
                    <div className={cloudSettings.intuition_check_enabled === 'true' ? '' : 'opacity-40 pointer-events-none'}>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
                        <div className="rounded border border-white/5 bg-white/[0.02] p-3">
                          <Toggle
                            label="Clarify"
                            description="Ask clarifying questions for ambiguous input before routing"
                            checked={cloudSettings.intuition_check_clarify === 'true'}
                            onChange={(v) => handleCloudToggle('intuition_check_clarify', v)}
                          />
                        </div>
                        <div className="rounded border border-white/5 bg-white/[0.02] p-3">
                          <Toggle
                            label="Suggest Next"
                            description="After a task completes, suggest what to do next"
                            checked={cloudSettings.intuition_check_suggest === 'true'}
                            onChange={(v) => handleCloudToggle('intuition_check_suggest', v)}
                          />
                        </div>
                        <div className="rounded border border-white/5 bg-white/[0.02] p-3">
                          <Toggle
                            label="Reconnect"
                            description="Welcome back with open task context after idle"
                            checked={cloudSettings.intuition_check_reconnect === 'true'}
                            onChange={(v) => handleCloudToggle('intuition_check_reconnect', v)}
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4">
                        <div>
                          <label className="mb-1.5 block text-sm text-white/70">Model</label>
                          <select
                            value={cloudSettings.intuition_check_model || 'gpt-4o-mini'}
                            onChange={(e) => handleCloudSelect('intuition_check_model', e.target.value)}
                            className="w-full rounded glass-field px-4 py-2.5 text-sm text-white bg-transparent focus:outline-none focus:ring-1 focus:ring-white/20"
                          >
                            <option value="gpt-4o-mini" className="bg-gray-900">gpt-4o-mini (fast, cheap)</option>
                            <option value="gpt-4o" className="bg-gray-900">gpt-4o (higher quality)</option>
                            <option value="claude-haiku" className="bg-gray-900">Claude Haiku (via cookie)</option>
                          </select>
                          <p className="mt-1 text-xs text-white/40">Which model handles the intuition check calls</p>
                        </div>
                        <div>
                          <label className="mb-1.5 block text-sm text-white/70">Escalation</label>
                          <select
                            value={cloudSettings.intuition_check_escalation || 'cloud_first'}
                            onChange={(e) => handleCloudSelect('intuition_check_escalation', e.target.value)}
                            className="w-full rounded glass-field px-4 py-2.5 text-sm text-white bg-transparent focus:outline-none focus:ring-1 focus:ring-white/20"
                          >
                            <option value="cloud_first" className="bg-gray-900">Cloud first (default)</option>
                            <option value="local_only" className="bg-gray-900">Local only (no cloud calls)</option>
                            <option value="cloud_required" className="bg-gray-900">Cloud required (skip if unavailable)</option>
                          </select>
                          <p className="mt-1 text-xs text-white/40">When cloud is unavailable: skip check or try local fallback</p>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-white/40">Loading intuition check settings...</p>
                )}
              </SectionCard>

              {/* Usage (full width row below) */}
              {cloudUsage !== null && (
                <SectionCard title="Usage (this session)">
                  <div className="flex items-center justify-between mb-3 -mt-3">
                    <div />
                    <button
                      onClick={() => getCloudUsage().then(setCloudUsage).catch(() => {})}
                      className="text-xs hover:opacity-80 transition-opacity"
                      style={{ color: 'var(--accent)' }}
                    >refresh</button>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-1 text-xs text-white/60">
                    {cloudUsage.slot_classification && (
                      <div className="flex justify-between">
                        <span>Slot Classification</span>
                        <span>{cloudUsage.slot_classification.calls} calls / ~{cloudUsage.slot_classification.est_tokens} tokens</span>
                      </div>
                    )}
                    {cloudUsage.nli_contradiction && (
                      <div className="flex justify-between">
                        <span>NLI Contradiction</span>
                        <span>{cloudUsage.nli_contradiction.calls} calls / ~{cloudUsage.nli_contradiction.est_tokens} tokens</span>
                      </div>
                    )}
                    {cloudUsage.reflection_validation && (
                      <div className="flex justify-between">
                        <span>Reflection Validation</span>
                        <span>{cloudUsage.reflection_validation.calls} calls / ~{cloudUsage.reflection_validation.est_tokens} tokens</span>
                      </div>
                    )}
                    {cloudUsage.claude_generation && (
                      <div className="flex justify-between">
                        <span>Claude Generation</span>
                        <span>{cloudUsage.claude_generation.calls} calls / ~{cloudUsage.claude_generation.est_tokens} tokens</span>
                      </div>
                    )}
                    {cloudUsage.claude_reflection && (
                      <div className="flex justify-between">
                        <span>Claude Reflection</span>
                        <span>{cloudUsage.claude_reflection.calls} calls / ~{cloudUsage.claude_reflection.est_tokens} tokens</span>
                      </div>
                    )}
                    {cloudUsage.total_cost_est != null && (
                      <div className="flex justify-between pt-1 border-t border-white/10 font-medium col-span-full">
                        <span>Estimated Cost</span>
                        <span>${cloudUsage.total_cost_est.toFixed(4)}</span>
                      </div>
                    )}
                    {cloudUsage.daily_limits && Object.keys(cloudUsage.daily_limits).length > 0 && (
                      <div className="pt-1 border-t border-white/10 col-span-full flex flex-wrap gap-x-4">
                        <span className="text-white/50">Daily limits: </span>
                        {Object.entries(cloudUsage.daily_limits).map(([k, v]) => (
                          <span key={k}>{k.replace(/_/g, ' ')}: {v.used}/{v.limit}</span>
                        ))}
                      </div>
                    )}
                    {!cloudUsage.slot_classification && !cloudUsage.nli_contradiction && !cloudUsage.reflection_validation && (
                      <p className="text-white/30 italic col-span-full">No cloud calls yet this session</p>
                    )}
                  </div>
                </SectionCard>
              )}

              {/* ── Pipeline Controls (merged from Advanced) ── */}
              <SectionCard title="Pipeline Controls" description="These settings control CRT pipeline behavior and model capabilities. Changes take effect on the next message.">
                {cloudSettings ? (
                  <div className="space-y-1">
                    <Toggle
                      label="Bypass CRT Loop"
                      description="Skip memory retrieval, contradiction detection, gates, and trust scoring. Sends messages directly to the selected cloud model with no CRT wrapping."
                      checked={cloudSettings.bypass_crt === 'true' || cloudSettings.bypass_crt === 'on'}
                      onChange={(v) => handleCloudToggle('bypass_crt', v)}
                    />
                    {(cloudSettings.bypass_crt === 'true' || cloudSettings.bypass_crt === 'on') && (
                      <div className="ml-2 mb-2 rounded bg-amber-500/10 border border-amber-500/20 px-3 py-2 text-xs text-amber-300/80">
                        CRT bypass is active. Responses will not use memories, contradiction checking, or trust scoring.
                      </div>
                    )}

                    <Toggle
                      label="Enable Tooling"
                      description="Allow the model to use tools and function calls during generation."
                      checked={cloudSettings.enable_tooling === 'true' || cloudSettings.enable_tooling === 'on'}
                      onChange={(v) => handleCloudToggle('enable_tooling', v)}
                    />

                    <Toggle
                      label="Enable Response Synthesis"
                      description="When enabled, the LLM interprets tool results and responds with context and analysis. When disabled, raw tool output is returned."
                      checked={cloudSettings.synthesis_enabled !== 'false'}
                      onChange={(v) => handleCloudToggle('synthesis_enabled', v)}
                    />
                  </div>
                ) : (
                  <p className="text-sm text-white/40">Loading advanced settings...</p>
                )}
              </SectionCard>

              {/* ── Model Selection (merged from Advanced) ── */}
              <SectionCard title="Model Selection" description="Choose which models are used for generation. These override defaults when set.">
                {cloudSettings ? (
                  <div className="space-y-4">
                    <div>
                      <label className="mb-1.5 block text-sm text-white/70">Generation Mode</label>
                      <select
                        value={cloudSettings.generation_mode || 'local'}
                        onChange={(e) => handleCloudSelect('generation_mode', e.target.value)}
                        className="w-full rounded glass-field px-4 py-2.5 text-sm text-white bg-transparent focus:outline-none focus:ring-1 focus:ring-white/20"
                      >
                        <option value="local" className="bg-gray-900">Local (Ollama)</option>
                        <option value="local_network" className="bg-gray-900">Network (Ollama/LAN)</option>
                        <option value="cloud_openai" className="bg-gray-900">Cloud (OpenAI)</option>
                        <option value="cloud_claude" className="bg-gray-900">Cloud (Claude)</option>
                      </select>
                      <p className="mt-1 text-xs text-white/40">Primary model provider for text generation</p>
                    </div>

                    <div>
                      <label className="mb-1.5 block text-sm text-white/70">OpenAI Model</label>
                      <input
                        type="text"
                        defaultValue={cloudSettings.cloud_model_openai || 'gpt-4o-mini'}
                        onBlur={(e) => handleCloudSelect('cloud_model_openai', e.target.value)}
                        placeholder="gpt-4o-mini"
                        className="w-full rounded glass-field px-4 py-2.5 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-1 focus:ring-white/20"
                      />
                      <p className="mt-1 text-xs text-white/40">Model ID for OpenAI API calls (e.g., gpt-4o, gpt-4o-mini)</p>
                    </div>

                    <div>
                      <label className="mb-1.5 block text-sm text-white/70">Claude Model</label>
                      <input
                        type="text"
                        defaultValue={cloudSettings.cloud_model_claude || 'claude-sonnet-4-20250514'}
                        onBlur={(e) => handleCloudSelect('cloud_model_claude', e.target.value)}
                        placeholder="claude-sonnet-4-20250514"
                        className="w-full rounded glass-field px-4 py-2.5 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-1 focus:ring-white/20"
                      />
                      <p className="mt-1 text-xs text-white/40">Model ID for Claude API calls</p>
                    </div>

                    <div>
                      <label className="mb-1.5 block text-sm text-white/70">Routing LLM Model Override</label>
                      <input
                        type="text"
                        defaultValue={cloudSettings.routing_llm_model || ''}
                        onBlur={(e) => handleCloudSelect('routing_llm_model', e.target.value)}
                        placeholder="Leave blank for default"
                        className="w-full rounded glass-field px-4 py-2.5 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-1 focus:ring-white/20"
                      />
                      <p className="mt-1 text-xs text-white/40">Override the model used for intent routing. Leave blank to use the default.</p>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-white/40">Loading model settings...</p>
                )}
              </SectionCard>

              {/* ── Intent Routing (merged from Advanced) ── */}
              <SectionCard title="Intent Routing" description="Controls how user messages are classified and routed to tools. Regex patterns are always tried first (instant, free). The LLM router handles novel phrasings that regex misses.">
                {cloudSettings ? (
                  <div className="space-y-2">
                    {[
                      { value: 'hybrid', label: 'Hybrid (Recommended)', desc: 'Regex -> local LLM -> cloud escalation. Best balance of speed, cost, and accuracy.' },
                      { value: 'local_only', label: 'Local Only', desc: 'Regex + local LLM. No cloud calls for routing. Free but less accurate on novel requests.' },
                      { value: 'cloud_only', label: 'Cloud Only', desc: 'Regex + cloud LLM. Most accurate, uses API tokens for classification.' },
                    ].map((opt) => (
                      <label
                        key={opt.value}
                        className={`flex items-start gap-3 rounded-lg px-4 py-3 cursor-pointer transition-colors ${
                          (cloudSettings.routing_mode || 'hybrid') === opt.value
                            ? 'bg-[var(--accent)]/15 ring-1 ring-[var(--accent)]/30'
                            : 'bg-white/5 hover:bg-white/[0.08]'
                        }`}
                      >
                        <input
                          type="radio"
                          name="routing_mode"
                          value={opt.value}
                          checked={(cloudSettings.routing_mode || 'hybrid') === opt.value}
                          onChange={() => handleCloudSelect('routing_mode', opt.value)}
                          className="mt-0.5 accent-[var(--accent)]"
                        />
                        <div>
                          <div className="text-sm font-medium text-white/90">{opt.label}</div>
                          <div className="text-xs text-white/40 mt-0.5">{opt.desc}</div>
                        </div>
                      </label>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-white/40">Loading routing settings...</p>
                )}
              </SectionCard>
            </>
          )}

          {/* ═══════════════════ DESKTOP TAB ═══════════════════ */}
          {tab === 'desktop' && (
            <SectionCard title="Desktop Control" description="Aether can see and control your desktop via screenshot analysis. When enabled, commands like 'open notepad' or 'search for weather' will use the vision-action loop.">
              {cloudSettings ? (
                <div className="space-y-1">
                  <Toggle
                    label="Enable Desktop Control"
                    description="Allow Aether to take screenshots and control mouse/keyboard to complete tasks."
                    checked={cloudSettings.desktop_control_enabled === 'true'}
                    onChange={(v) => handleCloudToggle('desktop_control_enabled', v)}
                  />
                  {cloudSettings.desktop_control_enabled === 'true' && (
                    <div className="ml-2 mb-2 rounded bg-amber-500/10 border border-amber-500/20 px-3 py-2 text-xs text-amber-300/80">
                      Desktop control is active. Aether can see your screen and interact with it. Move your mouse to the top-left corner (0,0) to emergency-stop all automation.
                    </div>
                  )}

                  <div className="mt-4 mb-2 text-xs font-medium text-white/50 uppercase tracking-wide">Limits</div>

                  <div className="flex items-center justify-between py-2">
                    <div className="flex-1">
                      <div className="text-sm text-white/80">Max steps per task</div>
                      <div className="text-xs text-white/40 mt-0.5">Maximum vision-action loop iterations before aborting. Each step takes 10-25s.</div>
                    </div>
                    <input
                      type="number" min="1" max="50"
                      defaultValue={cloudSettings.desktop_max_steps_per_task || '15'}
                      onBlur={(e) => handleCloudNumberInput('desktop_max_steps_per_task', e.target.value)}
                      className="w-20 rounded bg-white/10 border border-white/10 px-2 py-1 text-sm text-white text-right"
                    />
                  </div>

                  <div className="flex items-center justify-between py-2">
                    <div className="flex-1">
                      <div className="text-sm text-white/80">Max actions per session</div>
                      <div className="text-xs text-white/40 mt-0.5">Total desktop actions allowed per session before requiring re-enable.</div>
                    </div>
                    <input
                      type="number" min="1" max="500"
                      defaultValue={cloudSettings.desktop_max_actions_per_session || '50'}
                      onBlur={(e) => handleCloudNumberInput('desktop_max_actions_per_session', e.target.value)}
                      className="w-20 rounded bg-white/10 border border-white/10 px-2 py-1 text-sm text-white text-right"
                    />
                  </div>

                  <div className="mt-4 mb-2 text-xs font-medium text-white/50 uppercase tracking-wide">Confirmation</div>

                  <div className="flex items-center justify-between py-2">
                    <div className="flex-1">
                      <div className="text-sm text-white/80">Require confirmation</div>
                      <div className="text-xs text-white/40 mt-0.5">When to pause and ask before executing an action.</div>
                    </div>
                    <select
                      value={cloudSettings.desktop_require_confirmation || 'dangerous_only'}
                      onChange={(e) => handleCloudSelect('desktop_require_confirmation', e.target.value)}
                      className="rounded bg-white/10 border border-white/10 px-2 py-1 text-sm text-white"
                    >
                      <option value="never">Never</option>
                      <option value="dangerous_only">Dangerous actions only</option>
                      <option value="always">Every action</option>
                    </select>
                  </div>

                  <div className="mt-4 mb-2 text-xs font-medium text-white/50 uppercase tracking-wide">Vision Provider</div>

                  <div className="flex items-center justify-between py-2">
                    <div className="flex-1">
                      <div className="text-sm text-white/80">Vision model</div>
                      <div className="text-xs text-white/40 mt-0.5">How screenshots are analyzed. Cookie uses your claude.ai session; API key uses ANTHROPIC_API_KEY.</div>
                    </div>
                    <select
                      value={cloudSettings.desktop_vision_provider || 'cookie'}
                      onChange={(e) => handleCloudSelect('desktop_vision_provider', e.target.value)}
                      className="rounded bg-white/10 border border-white/10 px-2 py-1 text-sm text-white"
                    >
                      <option value="cookie">Cookie session</option>
                      <option value="api_key">API key</option>
                    </select>
                  </div>

                  <div className="mt-4 mb-2 text-xs font-medium text-white/50 uppercase tracking-wide">Heartbeat Automation</div>

                  <Toggle
                    label="Idle desktop control"
                    description="When the system is idle (CPU < 10%, no GPU activity), automatically run a desktop task."
                    checked={cloudSettings.desktop_heartbeat_idle_control === 'true'}
                    onChange={(v) => handleCloudToggle('desktop_heartbeat_idle_control', v)}
                  />

                  {cloudSettings.desktop_heartbeat_idle_control === 'true' && (
                    <div className="flex items-center justify-between py-2 ml-2">
                      <div className="flex-1">
                        <div className="text-sm text-white/80">Idle task</div>
                        <div className="text-xs text-white/40 mt-0.5">What to do when idle. E.g. "organize my downloads folder" or "check email".</div>
                      </div>
                      <input
                        type="text"
                        defaultValue={cloudSettings.desktop_idle_task || ''}
                        onBlur={(e) => handleCloudSelect('desktop_idle_task', e.target.value)}
                        placeholder="e.g. organize downloads"
                        className="w-56 rounded bg-white/10 border border-white/10 px-2 py-1 text-sm text-white"
                      />
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-sm text-white/40">Loading desktop settings...</p>
              )}
            </SectionCard>
          )}

          {/* ═══════════════════ BROWSER TAB ═══════════════════ */}
          {tab === 'browser' && (
            <SectionCard title="Browser Control" description="Aether can browse the web autonomously via Playwright. Navigate pages, read content, fill forms, extract data. Uses DOM analysis first, vision fallback for complex pages.">
              {cloudSettings ? (
                <div className="space-y-1">
                  <Toggle
                    label="Enable Browser Control"
                    description="Allow Aether to open a browser, navigate the web, and interact with web pages."
                    checked={cloudSettings.browser_enabled === 'true'}
                    onChange={(v) => handleCloudToggle('browser_enabled', v)}
                  />
                  {cloudSettings.browser_enabled === 'true' && (
                    <div className="ml-2 mb-2 rounded bg-blue-500/10 border border-blue-500/20 px-3 py-2 text-xs text-blue-300/80">
                      Browser control is active. Aether can browse websites and interact with web pages on your behalf.
                    </div>
                  )}

                  <div className="mt-4 mb-2 text-xs font-medium text-white/50 uppercase tracking-wide">Browser Settings</div>

                  <div className="flex items-center justify-between py-2">
                    <div className="flex-1">
                      <div className="text-sm text-white/80">Browser mode</div>
                      <div className="text-xs text-white/40 mt-0.5">Headed shows the browser window; headless runs in background (faster, no UI).</div>
                    </div>
                    <select
                      value={cloudSettings.browser_mode || 'headed'}
                      onChange={(e) => handleCloudSelect('browser_mode', e.target.value)}
                      className="rounded bg-white/10 border border-white/10 px-2 py-1 text-sm text-white"
                    >
                      <option value="headed">Headed (visible)</option>
                      <option value="headless">Headless (background)</option>
                    </select>
                  </div>

                  <div className="flex items-center justify-between py-2">
                    <div className="flex-1">
                      <div className="text-sm text-white/80">Browser engine</div>
                      <div className="text-xs text-white/40 mt-0.5">Which browser engine Playwright uses. Chromium is recommended.</div>
                    </div>
                    <select
                      value={cloudSettings.browser_engine || 'chromium'}
                      onChange={(e) => handleCloudSelect('browser_engine', e.target.value)}
                      className="rounded bg-white/10 border border-white/10 px-2 py-1 text-sm text-white"
                    >
                      <option value="chromium">Chromium</option>
                      <option value="firefox">Firefox</option>
                      <option value="webkit">WebKit</option>
                    </select>
                  </div>

                  <Toggle
                    label="Persist sessions"
                    description="Save cookies and login sessions between browser tasks. When off, each task starts fresh."
                    checked={cloudSettings.browser_persist_sessions !== 'false'}
                    onChange={(v) => handleCloudToggle('browser_persist_sessions', v)}
                  />

                  <div className="mt-4 mb-2 text-xs font-medium text-white/50 uppercase tracking-wide">Limits</div>

                  <div className="flex items-center justify-between py-2">
                    <div className="flex-1">
                      <div className="text-sm text-white/80">Max steps per task</div>
                      <div className="text-xs text-white/40 mt-0.5">Maximum actions the browser agent takes before stopping. Each step is a page read + action.</div>
                    </div>
                    <input
                      type="number" min="5" max="50"
                      defaultValue={cloudSettings.browser_max_steps || '20'}
                      onBlur={(e) => handleCloudNumberInput('browser_max_steps', e.target.value)}
                      className="w-20 rounded bg-white/10 border border-white/10 px-2 py-1 text-sm text-white text-right"
                    />
                  </div>

                  <div className="mt-4 mb-2 text-xs font-medium text-white/50 uppercase tracking-wide">Confirmation</div>

                  <div className="flex items-center justify-between py-2">
                    <div className="flex-1">
                      <div className="text-sm text-white/80">Require confirmation for</div>
                      <div className="text-xs text-white/40 mt-0.5">When to pause and ask before executing a browser action.</div>
                    </div>
                    <select
                      value={cloudSettings.browser_confirm_mode || 'submissions_only'}
                      onChange={(e) => handleCloudSelect('browser_confirm_mode', e.target.value)}
                      className="rounded bg-white/10 border border-white/10 px-2 py-1 text-sm text-white"
                    >
                      <option value="never">Never</option>
                      <option value="submissions_only">Form submissions only</option>
                      <option value="all_actions">Every action</option>
                    </select>
                  </div>

                  <div className="mt-4 mb-2 text-xs font-medium text-white/50 uppercase tracking-wide">Domain Restrictions</div>

                  <div className="py-2">
                    <div className="text-sm text-white/80 mb-1">Domain allowlist</div>
                    <div className="text-xs text-white/40 mb-2">If set, browser can ONLY visit these domains. One per line. Leave empty to allow all non-blocked domains.</div>
                    <textarea
                      defaultValue={cloudSettings.browser_domain_allowlist || ''}
                      onBlur={(e) => handleCloudSelect('browser_domain_allowlist', e.target.value)}
                      placeholder="example.com&#10;docs.python.org"
                      rows={3}
                      className="w-full rounded bg-white/10 border border-white/10 px-2 py-1 text-sm text-white font-mono"
                    />
                  </div>

                  <div className="py-2">
                    <div className="text-sm text-white/80 mb-1">Domain blocklist</div>
                    <div className="text-xs text-white/40 mb-2">Browser will never visit these domains. Banking domains are always blocked regardless of this list.</div>
                    <textarea
                      defaultValue={cloudSettings.browser_domain_blocklist || ''}
                      onBlur={(e) => handleCloudSelect('browser_domain_blocklist', e.target.value)}
                      placeholder="facebook.com&#10;twitter.com"
                      rows={3}
                      className="w-full rounded bg-white/10 border border-white/10 px-2 py-1 text-sm text-white font-mono"
                    />
                  </div>
                </div>
              ) : (
                <p className="text-sm text-white/40">Loading browser settings...</p>
              )}
            </SectionCard>
          )}

          {/* ═══════════════════ HEARTBEAT TAB ═══════════════════ */}
          {tab === 'heartbeat' && cloudSettings && (
            <>
              <SectionCard title="Heartbeat System" description="Proactive background loop that runs periodically per thread. Reads workspace instructions, gathers context, and can take autonomous actions like posting to the Ledger.">
                <Toggle
                  label="Enable Heartbeat"
                  description="Run the heartbeat loop at the configured interval. When disabled, no proactive actions occur."
                  checked={cloudSettings.heartbeat_enabled !== 'false'}
                  onChange={(v) => handleCloudToggle('heartbeat_enabled', v)}
                />

                <div className={cloudSettings.heartbeat_enabled === 'false' ? 'opacity-40 pointer-events-none' : ''}>
                  <div className="mt-4 mb-2 text-xs font-medium text-white/50 uppercase tracking-wide">Timing</div>

                  <div className="flex items-center justify-between py-2">
                    <div className="flex-1">
                      <div className="text-sm text-white/80">Interval (seconds)</div>
                      <div className="text-xs text-white/40 mt-0.5">How often the heartbeat fires. 1800 = 30 minutes, 3600 = 1 hour.</div>
                    </div>
                    <input
                      type="number" min="300" max="86400" step="300"
                      value={cloudSettings.heartbeat_interval_seconds || '1800'}
                      onChange={(e) => {
                        setCloudSettingsState({ ...cloudSettings, heartbeat_interval_seconds: e.target.value })
                      }}
                      onBlur={(e) => handleCloudNumberInput('heartbeat_interval_seconds', e.target.value)}
                      className="w-24 rounded bg-white/10 border border-white/10 px-2 py-1 text-sm text-white text-right"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4 mt-2">
                    <div>
                      <label className="mb-1.5 block text-sm text-white/70">Active hours start</label>
                      <input
                        type="number" min="0" max="23"
                        value={cloudSettings.heartbeat_active_hours_start || ''}
                        placeholder="Any"
                        onChange={(e) => {
                          setCloudSettingsState({ ...cloudSettings, heartbeat_active_hours_start: e.target.value })
                        }}
                        onBlur={(e) => handleCloudNumberInput('heartbeat_active_hours_start', e.target.value)}
                        className="w-full rounded glass-field px-4 py-2.5 text-sm text-white bg-transparent focus:outline-none focus:ring-1 focus:ring-white/20"
                      />
                      <p className="mt-1 text-xs text-white/40">Hour (0-23). Leave blank for always.</p>
                    </div>
                    <div>
                      <label className="mb-1.5 block text-sm text-white/70">Active hours end</label>
                      <input
                        type="number" min="0" max="23"
                        value={cloudSettings.heartbeat_active_hours_end || ''}
                        placeholder="Any"
                        onChange={(e) => {
                          setCloudSettingsState({ ...cloudSettings, heartbeat_active_hours_end: e.target.value })
                        }}
                        onBlur={(e) => handleCloudNumberInput('heartbeat_active_hours_end', e.target.value)}
                        className="w-full rounded glass-field px-4 py-2.5 text-sm text-white bg-transparent focus:outline-none focus:ring-1 focus:ring-white/20"
                      />
                      <p className="mt-1 text-xs text-white/40">Hour (0-23). Leave blank for always.</p>
                    </div>
                  </div>
                </div>
              </SectionCard>

              <SectionCard title="News Monitoring" description="Proactive news fetching on topics you care about. Runs during heartbeat cycles.">
                <Toggle
                  label="Enable News Monitoring"
                  description="Periodically search for news on your configured topics and post summaries."
                  checked={cloudSettings.heartbeat_news_monitoring === 'true'}
                  onChange={(v) => handleCloudToggle('heartbeat_news_monitoring', v)}
                />

                {cloudSettings.heartbeat_news_monitoring === 'true' && (
                  <div className="mt-3">
                    <label className="mb-1.5 block text-sm text-white/70">News Topics</label>
                    <input
                      type="text"
                      defaultValue={cloudSettings.heartbeat_news_topics || ''}
                      onBlur={(e) => handleCloudSelect('heartbeat_news_topics', e.target.value)}
                      placeholder="AI, technology, climate (comma-separated)"
                      className="w-full rounded glass-field px-4 py-2.5 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-1 focus:ring-white/20"
                    />
                    <p className="mt-1 text-xs text-white/40">Comma-separated list of topics to monitor</p>
                  </div>
                )}
              </SectionCard>

              <SectionCard title="Curiosity Engine" description="When enabled, the heartbeat can generate curiosity-driven reflections and questions about recent conversations.">
                <Toggle
                  label="Enable Curiosity"
                  description="Allow the agent to explore tangential ideas and post reflections to the Ledger."
                  checked={cloudSettings.heartbeat_curiosity_enabled !== 'false'}
                  onChange={(v) => handleCloudToggle('heartbeat_curiosity_enabled', v)}
                />
              </SectionCard>
            </>
          )}
          {tab === 'heartbeat' && !cloudSettings && (
            <p className="text-sm text-white/40">Loading heartbeat settings...</p>
          )}

          {/* ═══════════════════ BEHAVIOR TAB ═══════════════════ */}
          {tab === 'behavior' && cloudSettings && (
            <>
              <SectionCard title="Greeting" description="How the agent greets you when you start a conversation or return after being away.">
                <Toggle
                  label="Enable Greetings"
                  description="Show a personalized greeting when you return to chat."
                  checked={cloudSettings.greeting_enabled !== 'false'}
                  onChange={(v) => handleCloudToggle('greeting_enabled', v)}
                />

                {cloudSettings.greeting_enabled !== 'false' && (
                  <div className="mt-3">
                    <label className="mb-1.5 block text-sm text-white/70">Greeting Style</label>
                    <select
                      value={cloudSettings.greeting_style || 'time_based'}
                      onChange={(e) => handleCloudSelect('greeting_style', e.target.value)}
                      className="w-full rounded glass-field px-4 py-2.5 text-sm text-white bg-transparent focus:outline-none focus:ring-1 focus:ring-white/20"
                    >
                      <option value="time_based" className="bg-gray-900">Time-based (considers how long you were away)</option>
                      <option value="time_of_day" className="bg-gray-900">Time of day (good morning/afternoon/evening)</option>
                      <option value="simple" className="bg-gray-900">Simple (minimal greeting)</option>
                    </select>
                  </div>
                )}
              </SectionCard>

              <SectionCard title="Response Behavior" description="Controls how the agent handles uncertainty and verifies information.">
                <Toggle
                  label="Conflict Warnings"
                  description="When the agent isn't sure about something due to conflicting information, show a friendly explanation."
                  checked={cloudSettings.conflict_warning_enabled !== 'false'}
                  onChange={(v) => handleCloudToggle('conflict_warning_enabled', v)}
                />
                <Toggle
                  label="Provenance Footers"
                  description="Add a short provenance note to answers explaining where the information came from."
                  checked={cloudSettings.provenance_enabled !== 'false'}
                  onChange={(v) => handleCloudToggle('provenance_enabled', v)}
                />
                {cloudSettings.provenance_enabled !== 'false' && (
                  <div className="ml-4">
                    <Toggle
                      label="World Check"
                      description="Cross-check facts against public knowledge. Produces warnings, not truth-picking."
                      checked={cloudSettings.provenance_world_check === 'true'}
                      onChange={(v) => handleCloudToggle('provenance_world_check', v)}
                    />
                  </div>
                )}
              </SectionCard>

              <SectionCard title="Background Activity" description="Autonomous tasks that run when the system is idle. These can resolve contradictions, research open questions, and retrain models.">
                <Toggle
                  label="Enable Background Jobs"
                  description="Master toggle for all autonomous background activity."
                  checked={cloudSettings.background_jobs_enabled === 'true'}
                  onChange={(v) => handleCloudToggle('background_jobs_enabled', v)}
                />

                <div className={cloudSettings.background_jobs_enabled !== 'true' ? 'opacity-40 pointer-events-none' : ''}>
                  <Toggle
                    label="Auto-resolve Contradictions"
                    description="Automatically attempt to resolve detected contradictions using evidence and trust scoring."
                    checked={cloudSettings.background_auto_resolve === 'true'}
                    onChange={(v) => handleCloudToggle('background_auto_resolve', v)}
                  />
                  <Toggle
                    label="Auto Web Research"
                    description="Proactively research open questions when idle. Has privacy implications."
                    checked={cloudSettings.background_auto_research === 'true'}
                    onChange={(v) => handleCloudToggle('background_auto_research', v)}
                  />
                  {cloudSettings.background_auto_research === 'true' && (
                    <div className="ml-4 mb-2 rounded bg-amber-500/10 border border-amber-500/20 px-3 py-2 text-xs text-amber-300/80">
                      Auto web research sends queries to external search APIs. Review your privacy preferences before enabling.
                    </div>
                  )}
                  <Toggle
                    label="Auto Learning"
                    description="Background model retraining from accepted suggestions and corrections."
                    checked={cloudSettings.background_auto_learning === 'true'}
                    onChange={(v) => handleCloudToggle('background_auto_learning', v)}
                  />
                </div>
              </SectionCard>

              <SectionCard title="Web Search" description="Settings for web search tool when invoked by the agent.">
                <div className="flex items-center justify-between py-2">
                  <div className="flex-1">
                    <div className="text-sm text-white/80">Max results</div>
                    <div className="text-xs text-white/40 mt-0.5">Maximum number of search results to return per query.</div>
                  </div>
                  <input
                    type="number" min="1" max="20"
                    value={cloudSettings.web_search_max_results || '8'}
                    onChange={(e) => {
                      setCloudSettingsState({ ...cloudSettings, web_search_max_results: e.target.value })
                    }}
                    onBlur={(e) => handleCloudNumberInput('web_search_max_results', e.target.value)}
                    className="w-20 rounded bg-white/10 border border-white/10 px-2 py-1 text-sm text-white text-right"
                  />
                </div>
                <div className="flex items-center justify-between py-2">
                  <div className="flex-1">
                    <div className="text-sm text-white/80">Search region</div>
                    <div className="text-xs text-white/40 mt-0.5">Locale for search results.</div>
                  </div>
                  <select
                    value={cloudSettings.web_search_region || 'us-en'}
                    onChange={(e) => handleCloudSelect('web_search_region', e.target.value)}
                    className="rounded bg-white/10 border border-white/10 px-2 py-1 text-sm text-white"
                  >
                    <option value="us-en">US English</option>
                    <option value="gb-en">UK English</option>
                    <option value="ca-en">Canada English</option>
                    <option value="au-en">Australia English</option>
                    <option value="de-de">Germany</option>
                    <option value="fr-fr">France</option>
                    <option value="jp-jp">Japan</option>
                  </select>
                </div>
              </SectionCard>

              <SectionCard title="Plans & Workflow" description="Multi-step task plans that persist across messages and threads.">
                <div className="flex items-center justify-between py-2">
                  <div className="flex-1">
                    <div className="text-sm text-white/80">Auto-plan creation</div>
                    <div className="text-xs text-white/40 mt-0.5">When should the agent automatically create plans for multi-step requests?</div>
                  </div>
                  <select
                    value={cloudSettings.plan_auto_threshold || 'always_ask'}
                    onChange={(e) => handleCloudSelect('plan_auto_threshold', e.target.value)}
                    className="rounded bg-white/10 border border-white/10 px-2 py-1 text-sm text-white"
                  >
                    <option value="always_ask" className="bg-gray-900">Always ask first (default)</option>
                    <option value="auto_simple" className="bg-gray-900">Auto for 3+ step tasks</option>
                    <option value="auto_all" className="bg-gray-900">Auto for any multi-step task</option>
                  </select>
                </div>
                <Toggle
                  label="Plan Notifications"
                  description="Show step completion and plan progress in chat responses."
                  checked={cloudSettings.plan_notifications !== 'false'}
                  onChange={(v) => handleCloudToggle('plan_notifications', v)}
                />
                <Toggle
                  label="Show Plan Widget in Chat"
                  description="Display a compact plan progress bar above the message input when a plan is active."
                  checked={cloudSettings.plan_chat_visibility !== 'false'}
                  onChange={(v) => handleCloudToggle('plan_chat_visibility', v)}
                />
              </SectionCard>
            </>
          )}
          {tab === 'behavior' && !cloudSettings && (
            <p className="text-sm text-white/40">Loading behavior settings...</p>
          )}

          {/* Advanced tab removed — content merged into Cloud & Models tab above */}

          {/* ═══════════════════ FACTS TAB ═══════════════════ */}
          {tab === 'facts' && (
            <SectionCard title="Known Facts">
              {Object.keys(slots).length > 0 ? (
                <div className="mb-4 space-y-1.5">
                  {Object.entries(slots).map(([key, val]) => (
                    <div key={key} className="flex items-center gap-2 rounded bg-white/5 px-3 py-2 text-sm">
                      <span className="font-medium text-white/70">{key}</span>
                      <span className="text-white/30">=</span>
                      <span className="text-white/90">{val}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mb-4 text-sm text-white/40">No facts stored yet. Chat with Aether to build your profile, or add facts below.</p>
              )}

              <div className="flex items-end gap-2">
                <div className="flex-1">
                  <input
                    value={newFactKey}
                    onChange={(e) => setNewFactKey(e.target.value)}
                    placeholder="Fact name (e.g. hobby)"
                    className="w-full rounded glass-field px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none"
                  />
                </div>
                <div className="flex-1">
                  <input
                    value={newFactValue}
                    onChange={(e) => setNewFactValue(e.target.value)}
                    placeholder="Value (e.g. skateboarding)"
                    className="w-full rounded glass-field px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none"
                    onKeyDown={(e) => { if (e.key === 'Enter') handleAddFact() }}
                  />
                </div>
                <button
                  onClick={handleAddFact}
                  disabled={saving || !newFactKey.trim() || !newFactValue.trim()}
                  className="rounded bg-white/10 px-4 py-2 text-sm text-white hover:bg-white/20 disabled:opacity-30 transition-all"
                >
                  Add
                </button>
              </div>
            </SectionCard>
          )}

          {/* ═══════════════════ TOOLING TAB ═══════════════════ */}
          {tab === 'tooling' && (
            <>
              {/* ── Section A: Model Roles ── */}
              <SectionCard title="Model Roles" description="Assign which model handles each task type. Leave empty to use the default from runtime config.">
                {cloudSettings ? (
                  <div className="space-y-4">
                    {([
                      { key: 'tooling_model_role_fast', label: 'Fast', desc: 'Quick classifications, intent routing' },
                      { key: 'tooling_model_role_reasoning', label: 'Reasoning', desc: 'Complex analysis, multi-step thinking' },
                      { key: 'tooling_model_role_tool_loop', label: 'Tool Loop', desc: 'Agent tool-calling iterations' },
                      { key: 'tooling_model_role_answer', label: 'Answer', desc: 'Final response generation' },
                    ] as const).map(({ key, label, desc }) => (
                      <div key={key}>
                        <label className="mb-1 block text-sm text-white/80">{label}</label>
                        <div className="text-xs text-white/40 mb-1.5">{desc}</div>
                        <select
                          className="glass-field w-full rounded px-3 py-2 text-sm text-white/90"
                          value={cloudSettings[key] || ''}
                          onChange={(e) => handleCloudSelect(key, e.target.value)}
                        >
                          <option value="">Default (runtime config)</option>
                          {availableModels && (
                            <>
                              <optgroup label="Local (Ollama)">
                                {availableModels.local.map((m) => (
                                  <option key={`local:${m.name}`} value={`local:${m.name}`}>
                                    {m.name}{m.size ? ` (${m.size})` : ''}
                                  </option>
                                ))}
                              </optgroup>
                              <optgroup label="Cloud (OpenAI)">
                                {availableModels.cloud.map((m) => (
                                  <option key={`cloud:${m.name}`} value={`cloud:${m.name}`}>
                                    {m.label}
                                  </option>
                                ))}
                              </optgroup>
                              <optgroup label="Anthropic">
                                {availableModels.anthropic.map((m) => (
                                  <option key={`anthropic:${m.name}`} value={`anthropic:${m.name}`}>
                                    {m.label}
                                  </option>
                                ))}
                              </optgroup>
                            </>
                          )}
                        </select>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-white/40">Loading...</p>
                )}
              </SectionCard>

              {/* ── Section B: Fallback Policy ── */}
              <SectionCard title="Fallback Policy" description="Control how the system routes between local and cloud models when the primary is unavailable or returns empty.">
                {cloudSettings ? (
                  <div>
                    <select
                      className="glass-field w-full rounded px-3 py-2 text-sm text-white/90"
                      value={cloudSettings.tooling_fallback_policy || 'local_to_cloud'}
                      onChange={(e) => handleCloudSelect('tooling_fallback_policy', e.target.value)}
                    >
                      <option value="local_to_cloud">Local first, cloud fallback</option>
                      <option value="cloud_to_local">Cloud first, local fallback</option>
                      <option value="local_only">Local only</option>
                      <option value="cloud_only">Cloud only</option>
                    </select>
                    <div className="mt-2 text-xs text-white/40">
                      {cloudSettings.tooling_fallback_policy === 'local_to_cloud' && 'Try local Ollama models first; escalate to cloud if unavailable or returns empty.'}
                      {cloudSettings.tooling_fallback_policy === 'cloud_to_local' && 'Try cloud/Anthropic first; fall back to local if cloud unavailable.'}
                      {cloudSettings.tooling_fallback_policy === 'local_only' && 'Never use cloud models. All requests stay on local Ollama.'}
                      {cloudSettings.tooling_fallback_policy === 'cloud_only' && 'Only use cloud/Anthropic models. Skip local entirely.'}
                      {!cloudSettings.tooling_fallback_policy && 'Try local Ollama models first; escalate to cloud if unavailable or returns empty.'}
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-white/40">Loading...</p>
                )}
              </SectionCard>

              {/* ── Section C: Tool Access ── */}
              <SectionCard title="Tool Access" description="Enable or disable individual tools available to the agent loop.">
                {cloudSettings ? (
                  <div className="space-y-1">
                    {/* Safe / Read-only */}
                    <div className="mb-3">
                      <div className="mb-2 text-xs font-medium uppercase tracking-wide text-white/30">Read-only</div>
                      <Toggle label="System Info" description="Get OS, hardware, and environment details" checked={cloudSettings.tooling_tool_enabled_system_info !== 'false'} onChange={(v) => handleCloudToggle('tooling_tool_enabled_system_info', v)} />
                      <Toggle label="Directory List" description="List files and folders in a directory" checked={cloudSettings.tooling_tool_enabled_dir_list !== 'false'} onChange={(v) => handleCloudToggle('tooling_tool_enabled_dir_list', v)} />
                      <Toggle label="Project Scan" description="Scan project structure and tech stack" checked={cloudSettings.tooling_tool_enabled_project_scan !== 'false'} onChange={(v) => handleCloudToggle('tooling_tool_enabled_project_scan', v)} />
                      <Toggle label="List Commitments" description="List scheduled reminders" checked={cloudSettings.tooling_tool_enabled_list_commitments !== 'false'} onChange={(v) => handleCloudToggle('tooling_tool_enabled_list_commitments', v)} />
                      <Toggle label="Memory Recall" description="Search agent memory and knowledge" checked={cloudSettings.tooling_tool_enabled_memory_recall !== 'false'} onChange={(v) => handleCloudToggle('tooling_tool_enabled_memory_recall', v)} />
                    </div>
                    {/* Network / Passive */}
                    <div className="mb-3">
                      <div className="mb-2 text-xs font-medium uppercase tracking-wide text-white/30">Network</div>
                      <Toggle label="File Read" description="Read file contents from disk" checked={cloudSettings.tooling_tool_enabled_file_read !== 'false'} onChange={(v) => handleCloudToggle('tooling_tool_enabled_file_read', v)} />
                      <Toggle label="Fetch URL" description="HTTP GET request to a URL" checked={cloudSettings.tooling_tool_enabled_fetch_url !== 'false'} onChange={(v) => handleCloudToggle('tooling_tool_enabled_fetch_url', v)} />
                      <Toggle label="Web Search" description="Search the web for information" checked={cloudSettings.tooling_tool_enabled_web_search !== 'false'} onChange={(v) => handleCloudToggle('tooling_tool_enabled_web_search', v)} />
                      <Toggle label="HTTP GET JSON" description="Fetch and parse JSON from a URL" checked={cloudSettings.tooling_tool_enabled_http_get_json !== 'false'} onChange={(v) => handleCloudToggle('tooling_tool_enabled_http_get_json', v)} />
                      <Toggle label="Generate Content" description="Generate text or code via LLM" checked={cloudSettings.tooling_tool_enabled_generate_content !== 'false'} onChange={(v) => handleCloudToggle('tooling_tool_enabled_generate_content', v)} />
                    </div>
                    {/* Write / Modify */}
                    <div className="mb-3">
                      <div className="mb-2 text-xs font-medium uppercase tracking-wide text-white/30">Write / Modify</div>
                      <Toggle label="File Write" description="Write or overwrite files on disk" checked={cloudSettings.tooling_tool_enabled_file_write !== 'false'} onChange={(v) => handleCloudToggle('tooling_tool_enabled_file_write', v)} />
                      <Toggle label="Git Exec" description="Run git commands" checked={cloudSettings.tooling_tool_enabled_git_exec !== 'false'} onChange={(v) => handleCloudToggle('tooling_tool_enabled_git_exec', v)} />
                      <Toggle label="HTTP POST" description="Send POST requests to APIs" checked={cloudSettings.tooling_tool_enabled_http_post !== 'false'} onChange={(v) => handleCloudToggle('tooling_tool_enabled_http_post', v)} />
                      <Toggle label="Store Credential" description="Save credentials to the vault" checked={cloudSettings.tooling_tool_enabled_store_credential !== 'false'} onChange={(v) => handleCloudToggle('tooling_tool_enabled_store_credential', v)} />
                      <Toggle label="Web Browse" description="Navigate and interact with websites" checked={cloudSettings.tooling_tool_enabled_web_browse !== 'false'} onChange={(v) => handleCloudToggle('tooling_tool_enabled_web_browse', v)} />
                      <Toggle label="Create Commitment" description="Create scheduled reminders" checked={cloudSettings.tooling_tool_enabled_create_commitment !== 'false'} onChange={(v) => handleCloudToggle('tooling_tool_enabled_create_commitment', v)} />
                      <Toggle label="Cancel Commitment" description="Cancel existing reminders" checked={cloudSettings.tooling_tool_enabled_cancel_commitment !== 'false'} onChange={(v) => handleCloudToggle('tooling_tool_enabled_cancel_commitment', v)} />
                    </div>
                    {/* System / Dangerous */}
                    <div>
                      <div className="mb-2 text-xs font-medium uppercase tracking-wide text-amber-400/60">System (use with caution)</div>
                      <Toggle label="Shell Exec" description="Run arbitrary shell commands on the host" checked={cloudSettings.tooling_tool_enabled_shell_exec !== 'false'} onChange={(v) => handleCloudToggle('tooling_tool_enabled_shell_exec', v)} />
                      <Toggle label="Desktop Action" description="Mouse, keyboard, and screen automation" checked={cloudSettings.tooling_tool_enabled_desktop_action !== 'false'} onChange={(v) => handleCloudToggle('tooling_tool_enabled_desktop_action', v)} />
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-white/40">Loading...</p>
                )}
              </SectionCard>

              {/* ── Section D: Agent Loop ── */}
              <SectionCard title="Agent Loop" description="Configure the autonomous tool execution loop that runs multi-step tasks.">
                {cloudSettings ? (
                  <div className="space-y-2">
                    <Toggle
                      label="Enable Agent Loop"
                      description="Allow the AI to call tools autonomously in a loop"
                      checked={cloudSettings.tooling_agent_loop_enabled !== 'false'}
                      onChange={(v) => handleCloudToggle('tooling_agent_loop_enabled', v)}
                    />
                    <div>
                      <label className="mb-1 block text-sm text-white/80">Max Iterations</label>
                      <div className="text-xs text-white/40 mb-1.5">Maximum tool calls per task (1-50)</div>
                      <input
                        type="number"
                        min={1}
                        max={50}
                        className="glass-field w-24 rounded px-3 py-2 text-sm text-white/90"
                        defaultValue={cloudSettings.tooling_agent_loop_max_iterations || '10'}
                        onBlur={(e) => handleCloudNumberInput('tooling_agent_loop_max_iterations', e.target.value)}
                      />
                    </div>
                    <Toggle
                      label="Show Thinking"
                      description="Display model's chain-of-thought reasoning in the UI"
                      checked={cloudSettings.tooling_agent_loop_show_thinking !== 'false'}
                      onChange={(v) => handleCloudToggle('tooling_agent_loop_show_thinking', v)}
                    />
                  </div>
                ) : (
                  <p className="text-sm text-white/40">Loading...</p>
                )}
              </SectionCard>
            </>
          )}

          {/* ═══════════════════ ACCOUNT TAB ═══════════════════ */}
          {tab === 'account' && (
            <SectionCard title="Account">
              <div className="space-y-2 text-sm text-white/60">
                <div className="flex items-center gap-3 rounded bg-white/5 px-4 py-3">
                  <span className="text-white/40">Username</span>
                  <span className="text-white/80">{authUser?.username || '\u2014'}</span>
                </div>
                <div className="flex items-center gap-3 rounded bg-white/5 px-4 py-3">
                  <span className="text-white/40">User ID</span>
                  <span className="font-mono text-xs text-white/80">{authUser?.id || '\u2014'}</span>
                </div>
              </div>
            </SectionCard>
          )}
        </div>
      </div>
    </div>
  )
}
