import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { getProfile, updateAuthProfile, setProfileFacts, setProfileName } from '../lib/api'
import type { AuthUser } from '../lib/api'

type Props = {
  isOpen: boolean
  onClose: () => void
  authUser: AuthUser | null
  threadId: string
  onDisplayNameChanged: (name: string) => void
  onProfileUpdated: () => void
}

export function SettingsModal({ isOpen, onClose, authUser, threadId, onDisplayNameChanged, onProfileUpdated }: Props) {
  const [displayName, setDisplayName] = useState('')
  const [nickname, setNickname] = useState('')
  const [slots, setSlots] = useState<Record<string, string>>({})
  const [newFactKey, setNewFactKey] = useState('')
  const [newFactValue, setNewFactValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // Load profile on open
  useEffect(() => {
    if (!isOpen) return
    setDisplayName(authUser?.display_name || '')
    setSaved(false)

    getProfile(threadId).then((p) => {
      setNickname(p.slots?.nickname || p.slots?.preferred_name || '')
      setSlots(p.slots || {})
    }).catch(() => {})
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

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.2 }}
            className="w-full max-w-[520px] max-h-[85vh] overflow-y-auto rounded-2xl glass-panel border border-white/10 shadow-2xl"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-white/10 bg-white/5 px-6 py-4">
              <h2 className="text-lg font-semibold text-white">Settings</h2>
              <button
                onClick={onClose}
                className="grid h-8 w-8 place-items-center rounded-lg text-white/60 hover:bg-white/10 hover:text-white transition-all"
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
                    className="w-full rounded-xl glass-field px-4 py-2.5 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-1 focus:ring-white/20"
                  />
                  <p className="mt-1 text-xs text-white/40">Shown in the topbar and profile</p>
                </div>

                <div>
                  <label className="mb-1.5 block text-sm text-white/70">Preferred Nickname</label>
                  <input
                    value={nickname}
                    onChange={(e) => setNickname(e.target.value)}
                    placeholder="What should Aether call you?"
                    className="w-full rounded-xl glass-field px-4 py-2.5 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-1 focus:ring-white/20"
                  />
                  <p className="mt-1 text-xs text-white/40">Aether will use this name when talking to you</p>
                </div>
              </div>

              <button
                onClick={handleSave}
                disabled={saving}
                className="mt-4 rounded-xl bg-white/10 px-5 py-2 text-sm font-medium text-white transition-all hover:bg-white/20 disabled:opacity-50"
              >
                {saving ? 'Saving...' : saved ? 'Saved' : 'Save Profile'}
              </button>
            </div>

            {/* Known Facts Section */}
            <div className="border-b border-white/10 px-6 py-5">
              <div className="mb-3 text-xs font-medium uppercase tracking-wide text-white/50">Known Facts</div>

              {Object.keys(slots).length > 0 ? (
                <div className="mb-4 space-y-1.5">
                  {Object.entries(slots).map(([key, val]) => (
                    <div key={key} className="flex items-center gap-2 rounded-lg bg-white/5 px-3 py-2 text-sm">
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
                    className="w-full rounded-xl glass-field px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none"
                  />
                </div>
                <div className="flex-1">
                  <input
                    value={newFactValue}
                    onChange={(e) => setNewFactValue(e.target.value)}
                    placeholder="Value (e.g. skateboarding)"
                    className="w-full rounded-xl glass-field px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none"
                    onKeyDown={(e) => { if (e.key === 'Enter') handleAddFact() }}
                  />
                </div>
                <button
                  onClick={handleAddFact}
                  disabled={saving || !newFactKey.trim() || !newFactValue.trim()}
                  className="rounded-xl bg-white/10 px-4 py-2 text-sm text-white hover:bg-white/20 disabled:opacity-30 transition-all"
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
