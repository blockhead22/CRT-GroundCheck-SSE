import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { getProfile, updateAuthProfile, setProfileFacts, setProfileName, getCloudSettings, updateCloudSettings, getCloudUsage } from '../lib/api'
import type { AuthUser, CloudSettings, CloudUsage } from '../lib/api'

type Props = {
  isOpen: boolean
  onClose: () => void
  authUser: AuthUser | null
  threadId: string
  onDisplayNameChanged: (name: string) => void
  onProfileUpdated: () => void
}

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
        className={`relative h-6 w-11 rounded-full transition-colors ${checked ? 'bg-blue-500/80' : 'bg-white/10'}`}
      >
        <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-5' : 'translate-x-0.5'}`} />
      </button>
    </div>
  )
}

export function SettingsModal({ isOpen, onClose, authUser, threadId, onDisplayNameChanged, onProfileUpdated }: Props) {
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

  // Load profile on open
  useEffect(() => {
    if (!isOpen) return
    setDisplayName(authUser?.display_name || '')
    setSaved(false)

    getProfile(threadId).then((p) => {
      setNickname(p.slots?.nickname || p.slots?.preferred_name || '')
      setSlots(p.slots || {})
      // Populate display name from profile if authUser is not available
      if (!authUser?.display_name) {
        const profileName = p.slots?.name || p.slots?.display_name || p.slots?.preferred_name || ''
        if (profileName) setDisplayName(profileName)
      }
    }).catch(() => {})

    // Load cloud settings
    getCloudSettings().then(setCloudSettingsState).catch(() => {})
    getCloudUsage().then(setCloudUsage).catch(() => {})
  }, [isOpen, threadId, authUser])

  async function handleSave() {
    setSaving(true)
    try {
      // Update display name if changed
      if (displayName.trim() && displayName.trim() !== authUser?.display_name) {
        const res = await updateAuthProfile({ display_name: displayName.trim() })
        if (res.ok) onDisplayNameChanged(displayName.trim())
      }

      // Update nickname and other facts
      const factsToSet: Record<string, string> = {}
      if (nickname.trim()) factsToSet.nickname = nickname.trim()

      // Also update name in CRT if display name changed
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
    const newVal = value ? 'on' : 'off'
    setCloudSettingsState({ ...cloudSettings, [key]: newVal })
    setCloudSaving(true)
    try {
      await updateCloudSettings({ [key]: newVal })
    } catch (e) {
      console.error('Cloud setting update failed:', e)
      // Revert
      setCloudSettingsState({ ...cloudSettings, [key]: value ? 'off' : 'on' })
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
    // Debounce: save on mouse up (handled by onMouseUp/onTouchEnd in the slider)
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

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60"
          onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.2 }}
            className="w-full max-w-[520px] max-h-[85vh] overflow-y-auto rounded glass-panel border border-white/10 shadow-lg"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-white/10 bg-white/5 px-6 py-4">
              <h2 className="text-lg font-semibold text-white">Settings</h2>
              <button
                onClick={onClose}
                className="grid h-8 w-8 place-items-center rounded text-white/60 hover:bg-white/10 hover:text-white transition-all"
              >
                &times;
              </button>
            </div>

            {/* Profile Section */}
            <div className="border-b border-white/10 px-6 py-5">
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

            {/* Cloud Features Section */}
            <div className="border-b border-white/10 px-6 py-5">
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

              {/* Usage Display */}
              {cloudUsage && (
                <div className="mt-4 rounded bg-white/5 px-4 py-3">
                  <div className="text-xs font-medium text-white/50 mb-2">Usage (this session)</div>
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
                    {cloudUsage.total_cost_est != null && (
                      <div className="flex justify-between pt-1 border-t border-white/10 font-medium">
                        <span>Estimated Cost</span>
                        <span>${cloudUsage.total_cost_est.toFixed(4)}</span>
                      </div>
                    )}
                    {cloudUsage.daily_limits && (
                      <div className="pt-1 border-t border-white/10">
                        <span className="text-white/50">Daily limits: </span>
                        {Object.entries(cloudUsage.daily_limits).map(([k, v]) => (
                          <span key={k} className="mr-3">{k.replace(/_/g, ' ')}: {v.used}/{v.limit}</span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Intent Routing Section (v2.9) */}
            <div className="border-b border-white/10 px-6 py-5">
              <div className="mb-3 text-xs font-medium uppercase tracking-wide text-white/50">Intent Routing</div>
              <p className="mb-4 text-xs text-white/40">
                Controls how user messages are classified and routed to tools.
                Regex patterns are always tried first (instant, free).
              </p>
              <div className="space-y-2">
                {[
                  { value: 'hybrid', label: 'Hybrid (Recommended)', desc: 'Regex → local LLM → cloud escalation. Best balance of speed, cost, and accuracy.' },
                  { value: 'local_only', label: 'Local Only', desc: 'Regex + local LLM. No cloud calls for routing. Free but less accurate on novel requests.' },
                  { value: 'cloud_only', label: 'Cloud Only', desc: 'Regex + cloud LLM. Most accurate, uses API tokens for classification.' },
                ].map((opt) => (
                  <label
                    key={opt.value}
                    className={`flex items-start gap-3 rounded-lg px-4 py-3 cursor-pointer transition-colors ${
                      (cloudSettings?.routing_mode || 'hybrid') === opt.value
                        ? 'bg-blue-500/15 ring-1 ring-blue-500/30'
                        : 'bg-white/5 hover:bg-white/8'
                    }`}
                  >
                    <input
                      type="radio"
                      name="routing_mode"
                      value={opt.value}
                      checked={(cloudSettings?.routing_mode || 'hybrid') === opt.value}
                      onChange={() => handleCloudSelect('routing_mode', opt.value)}
                      className="mt-0.5 accent-blue-500"
                    />
                    <div>
                      <div className="text-sm font-medium text-white/90">{opt.label}</div>
                      <div className="text-xs text-white/40 mt-0.5">{opt.desc}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* Known Facts Section */}
            <div className="border-b border-white/10 px-6 py-5">
              <div className="mb-3 text-xs font-medium uppercase tracking-wide text-white/50">Known Facts</div>

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

            {/* Account Info */}
            <div className="px-6 py-4">
              <div className="mb-2 text-xs font-medium uppercase tracking-wide text-white/50">Account</div>
              <div className="space-y-1 text-sm text-white/60">
                <div>Username: <span className="text-white/80">{authUser?.username || '—'}</span></div>
                <div>User ID: <span className="text-white/80">{authUser?.id || '—'}</span></div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
