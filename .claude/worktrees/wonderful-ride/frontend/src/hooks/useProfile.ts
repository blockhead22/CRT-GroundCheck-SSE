import { useState, useEffect, useCallback } from 'react'
import { getProfile, setProfileName } from '../lib/api'

type UseProfileOpts = {
  threadId: string | undefined
}

export function useProfile({ threadId }: UseProfileOpts) {
  const [userName, setUserName] = useState<string>('User')
  const [userEmail, setUserEmail] = useState<string>('')
  const [profileHasName, setProfileHasName] = useState<boolean>(false)
  const [setNameOpen, setSetNameOpen] = useState<boolean>(false)

  // Load profile on thread change
  useEffect(() => {
    if (!threadId) return
    let mounted = true

    async function load() {
      try {
        const p = await getProfile(threadId!)
        const raw = (p?.name || p?.slots?.name || '').trim()
        if (!mounted) return
        setProfileHasName(Boolean(raw))
        setUserName(raw || 'User')
      } catch (_e) {
        // Keep existing name on error.
      }
    }

    void load()
    return () => { mounted = false }
  }, [threadId])

  const handleSetName = useCallback(async (name: string, currentThreadId: string) => {
    try {
      await setProfileName({ threadId: currentThreadId, name })
      setUserName(name)
      setProfileHasName(true)
      setSetNameOpen(false)
      // Refresh profile to confirm
      const p = await getProfile(currentThreadId)
      const raw = (p?.name || p?.slots?.name || '').trim()
      if (raw) setUserName(raw)
    } catch (e) {
      console.error('Failed to set name:', e)
      alert(`Failed to set name: ${e instanceof Error ? e.message : String(e)}`)
    }
  }, [])

  return {
    userName,
    userEmail,
    profileHasName,
    setNameOpen,
    setSetNameOpen,
    handleSetName,
  }
}
