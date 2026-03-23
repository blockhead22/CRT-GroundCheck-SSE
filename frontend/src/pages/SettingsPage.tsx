import { useState, useEffect } from 'react'
import { getProfile, updateAuthProfile, setProfileFacts, setProfileName, getCloudSettings, updateCloudSettings, getCloudUsage } from '../lib/api'
import type { AuthUser, CloudSettings, CloudUsage } from '../lib/api'

type Props = {
  authUser: AuthUser | null
  threadId: string
  onDisplayNameChanged: (name: string) => void
  onProfileUpdated: () => void
}

type SettingsTab = 'profile' | 'cloud' | 'facts' | 'account'

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
        className={`relative flex-shrink-0 h-6 w-11 rounded-full transition-colors ${checked ? 'bg-blue-500/80' : 'bg-white/10'}`}
      >
        <span className={`block absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-5' : 'translate-x-0'}`} />
      </button>
    </div>
  )
}

export function SettingsPage({ authUser, threadId, onDisplayNameChanged, onProfileUpdated }: Props) {
  const [tab, setTab] = useState<SettingsTab>('profile')
  const [displayName, setDisplayName] = useState('')
  const [nickname, setNickname] = useState('')
  const [slots, setSlots] = useState<Record<string, string>>({})
  const [newFactKey, setNewFactKey] = useState('')
  const [newFactValue, setNewFactValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // Cloud settings state
  const [cloudSettings, setCloudSettingsState] = useState<CloudSettings | null>(null)
  const [cloudUsage, setCloudUsage] = useState<CloudUsage | null>(null)
  const [cloudSaving, setCloudSaving] = useState(false)

  // Load profile on mount
  useEffect(() => {
    setDisplayName(authUser?.display_name || '')
    setSaved(false)

    getProfile(threadId).then((p) => {
      setNickname(p.slots?.nickname || p.slots?.preferred_name || '')
      setSlots(p.slots || {})
    }).catch(() => {})

    // Load cloud settings
    getCloudSettings().then(setCloudSettingsState).catch(() => {})
    getCloudUsage().then((data) => setCloudUsage(data?.usage ?? data)).catch(() => {})
  }, [threadId, authUser])

  // POLLING FIX: cloud-usage interval raised from 10s to 30s; pauses when tab is hidden
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null

    function start() {
      if (interval) return
      interval = setInterval(() => {
        getCloudUsage().then((data) => setCloudUsage(data?.usage ?? data)).catch(() => {})
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
      if (displayName.trim() && displayName.trim() !== authUser?.display_name) {
        const res = await updateAuthProfile({ display_name: displayName.trim() })
        if (res.ok) onDisplayNameChanged(displayName.trim())
      }

      const factsToSet: Record<string, string> = {}
      if (nickname.trim()) factsToSet.nickname = nickname.trim()

      if (displayName.trim()) {
        await setProfileName({ threadId, name: displayName.trim() })
      }

      if (Object.keys(factsToSet).length > 0) {
        await setProfileFacts(threadId, factsToSet)
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
    // Claude settings use true/false, OpenAI settings use on/off
    const isClaude = key.startsWith('cloud_claude_')
    const newVal = isClaude ? (value ? 'true' : 'false') : (value ? 'on' : 'off')
    const oldVal = isClaude ? (value ? 'false' : 'true') : (value ? 'off' : 'on')
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
    { id: 'cloud', label: 'Cloud' },
    { id: 'facts', label: 'Known Facts' },
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
          <div className="flex items-center gap-1 rounded-sm border border-white/10 bg-white/5 p-1">
            {tabs.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={
                  'rounded px-3 py-2 text-xs font-semibold ' +
                  (tab === t.id ? 'bg-violet-600 text-white' : 'text-white/70 hover:bg-white/10')
                }
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-5">
        <div className="mx-auto max-w-2xl space-y-6">
          {tab === 'profile' && (
            <>
              <div className="rounded-sm border border-white/10 bg-white/[0.03] p-6">
                <div className="mb-4 text-xs font-medium uppercase tracking-wide text-white/50">Profile</div>

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
                      placeholder="What should Aether call you?"
                      className="w-full rounded glass-field px-4 py-2.5 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-1 focus:ring-white/20"
                    />
                    <p className="mt-1 text-xs text-white/40">Aether will use this name when talking to you</p>
                  </div>
                </div>

                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="mt-4 rounded bg-white/10 px-5 py-2 text-sm font-medium text-white transition-all hover:bg-white/20 disabled:opacity-50"
                >
                  {saving ? 'Saving...' : saved ? 'Saved' : 'Save Profile'}
                </button>
              </div>
            </>
          )}

          {tab === 'cloud' && (
            <>
              <div className="rounded-sm border border-white/10 bg-white/[0.03] p-6">
                <div className="mb-3 text-xs font-medium uppercase tracking-wide text-white/50">Cloud Features</div>
                <p className="mb-4 text-xs text-white/40">
                  Enable cloud LLM verification for higher-accuracy CRT operations. Calls use gpt-4o-mini (Tier 1) or Claude (Tier 2).
                </p>

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

                    {/* Escalation Policy */}
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

                    {/* Confidence Threshold */}
                    <div className="pt-3">
                      <label className="mb-1.5 block text-sm text-white/70">
                        Confidence Threshold: {cloudSettings.cloud_confidence_threshold}
                      </label>
                      <input
                        type="range"
                        min="0.5"
                        max="1.0"
                        step="0.05"
                        value={cloudSettings.cloud_confidence_threshold}
                        onChange={(e) => handleCloudSlider('cloud_confidence_threshold', e.target.value)}
                        onMouseUp={() => commitCloudSlider('cloud_confidence_threshold')}
                        onTouchEnd={() => commitCloudSlider('cloud_confidence_threshold')}
                        className="w-full accent-blue-500"
                      />
                      <p className="mt-1 text-xs text-white/40">Below this threshold, results may be escalated to cloud</p>
                    </div>

                    {/* Daily Limit Multiplier */}
                    <div className="pt-3">
                      <label className="mb-1.5 block text-sm text-white/70">
                        Daily Limit Multiplier: {cloudSettings.cloud_daily_limit_multiplier}x
                      </label>
                      <input
                        type="range"
                        min="0"
                        max="3.0"
                        step="0.5"
                        value={cloudSettings.cloud_daily_limit_multiplier}
                        onChange={(e) => handleCloudSlider('cloud_daily_limit_multiplier', e.target.value)}
                        onMouseUp={() => commitCloudSlider('cloud_daily_limit_multiplier')}
                        onTouchEnd={() => commitCloudSlider('cloud_daily_limit_multiplier')}
                        className="w-full accent-blue-500"
                      />
                      <p className="mt-1 text-xs text-white/40">Scale daily call limits up or down (0 = disabled)</p>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-white/40">Loading cloud settings...</p>
                )}
              </div>

              {/* Claude (Tier 2) Section */}
              <div className="rounded-sm border border-white/10 bg-white/[0.03] p-6">
                <div className="mb-3 text-xs font-medium uppercase tracking-wide text-white/50">Claude (Tier 2)</div>
                <p className="mb-4 text-xs text-white/40">
                  Use Claude via cookie session for high-quality generation fallback and reflection validation.
                  {cloudUsage?.claude_available === false && (
                    <span className="ml-1 text-amber-400/80">Cookie session not configured (CLAUDE_SESSION_COOKIE not set).</span>
                  )}
                  {cloudUsage?.claude_available === true && (
                    <span className="ml-1 text-green-400/80">Cookie session active.</span>
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

                      {/* Daily call limit */}
                      <div className="pt-3">
                        <label className="mb-1.5 block text-sm text-white/70">Daily Call Limit</label>
                        <input
                          type="number"
                          min="0"
                          max="100"
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

                      {/* Max tokens per call */}
                      <div className="pt-3">
                        <label className="mb-1.5 block text-sm text-white/70">Max Tokens per Call</label>
                        <input
                          type="number"
                          min="256"
                          max="8192"
                          step="256"
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

                    {/* Claude usage display */}
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
              </div>

              {/* Usage Display */}
              {cloudUsage !== null && (
                <div className="rounded-sm border border-white/10 bg-white/[0.03] p-6">
                  <div className="flex items-center justify-between mb-3">
                    <div className="text-xs font-medium uppercase tracking-wide text-white/50">Usage (this session)</div>
                    <button
                      onClick={() => getCloudUsage().then((data) => setCloudUsage(data?.usage ?? data)).catch(() => {})}
                      className="text-xs text-blue-400 hover:text-blue-300"
                    >refresh</button>
                  </div>
                  <div className="space-y-1 text-xs text-white/60">
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
                      <div className="flex justify-between pt-1 border-t border-white/10 font-medium">
                        <span>Estimated Cost</span>
                        <span>${cloudUsage.total_cost_est.toFixed(4)}</span>
                      </div>
                    )}
                    {cloudUsage.daily_limits && Object.keys(cloudUsage.daily_limits).length > 0 && (
                      <div className="pt-1 border-t border-white/10">
                        <span className="text-white/50">Daily limits: </span>
                        {Object.entries(cloudUsage.daily_limits).map(([k, v]) => (
                          <span key={k} className="mr-3">{k.replace(/_/g, ' ')}: {v.used}/{v.limit}</span>
                        ))}
                      </div>
                    )}
                    {!cloudUsage.slot_classification && !cloudUsage.nli_contradiction && !cloudUsage.reflection_validation && (
                      <p className="text-white/30 italic">No cloud calls yet this session</p>
                    )}
                  </div>
                </div>
              )}
            </>
          )}

          {tab === 'facts' && (
            <div className="rounded-sm border border-white/10 bg-white/[0.03] p-6">
              <div className="mb-3 text-xs font-medium uppercase tracking-wide text-white/50">Known Facts</div>

              {Object.keys(slots).length > 0 ? (
                <div className="mb-4 space-y-1.5">
                  {Object.entries(slots).map(([key, val]) => (
                    <div key={key} className="flex items-center gap-2 rounded-sm bg-white/5 px-3 py-2 text-sm">
                      <span className="font-medium text-white/70">{key}</span>
                      <span className="text-white/30">=</span>
                      <span className="text-white/90">{val}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mb-4 text-sm text-white/40">No facts stored yet. Chat with Aether to build your profile, or add facts below.</p>
              )}

              {/* Add new fact */}
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
            </div>
          )}

          {tab === 'account' && (
            <div className="rounded-sm border border-white/10 bg-white/[0.03] p-6">
              <div className="mb-3 text-xs font-medium uppercase tracking-wide text-white/50">Account</div>
              <div className="space-y-2 text-sm text-white/60">
                <div className="flex items-center gap-3 rounded-sm bg-white/5 px-4 py-3">
                  <span className="text-white/40">Username</span>
                  <span className="text-white/80">{authUser?.username || '\u2014'}</span>
                </div>
                <div className="flex items-center gap-3 rounded-sm bg-white/5 px-4 py-3">
                  <span className="text-white/40">User ID</span>
                  <span className="font-mono text-xs text-white/80">{authUser?.id || '\u2014'}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
