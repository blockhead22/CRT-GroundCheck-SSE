import { useState, useEffect, useCallback } from 'react'
import { authGetMe, authLogout, authLoadChats, getAuthToken, type AuthUser } from '../lib/api'
import type { ChatThread } from '../types'

type UseAuthOpts = {
  setThreads: React.Dispatch<React.SetStateAction<ChatThread[]>>
  setSelectedThreadId: React.Dispatch<React.SetStateAction<string>>
}

export function useAuth({ setThreads, setSelectedThreadId }: UseAuthOpts) {
  const [authUser, setAuthUser] = useState<AuthUser | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [showLogin, setShowLogin] = useState(false)

  // Load server threads helper
  const loadServerThreads = useCallback(async () => {
    const serverThreads = await authLoadChats()
    if (serverThreads.length > 0) {
      setThreads(serverThreads.map(t => ({
        id: t.id,
        title: t.title,
        messages: t.messages as any[],
        updatedAt: t.updatedAt
      })))
      if (serverThreads[0]) {
        setSelectedThreadId(serverThreads[0].id)
      }
    }
  }, [setThreads, setSelectedThreadId])

  // Check for existing auth session on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = getAuthToken()
      if (!token) {
        setAuthLoading(false)
        const hasSeenLogin = localStorage.getItem('crt-seen-login')
        if (!hasSeenLogin) {
          setShowLogin(true)
        }
        return
      }

      try {
        const result = await authGetMe()
        if (result.ok && result.user) {
          setAuthUser(result.user)
          await loadServerThreads()
        }
      } catch {
        // Session invalid
      } finally {
        setAuthLoading(false)
      }
    }

    checkAuth()
  }, [loadServerThreads])

  const handleLogin = useCallback(async (user: AuthUser) => {
    setAuthUser(user)
    setShowLogin(false)
    localStorage.setItem('crt-seen-login', 'true')
    try {
      await loadServerThreads()
    } catch {
      // Keep local threads
    }
  }, [loadServerThreads])

  const handleLogout = useCallback(async () => {
    await authLogout()
    setAuthUser(null)
  }, [])

  const handleSkipLogin = useCallback(() => {
    setShowLogin(false)
    localStorage.setItem('crt-seen-login', 'true')
  }, [])

  return {
    authUser,
    authLoading,
    showLogin,
    setShowLogin,
    handleLogin,
    handleLogout,
    handleSkipLogin,
  }
}
