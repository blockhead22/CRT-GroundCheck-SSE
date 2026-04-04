import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import type { AuthUser } from '../lib/api'
import { authGetMe, authLogout, getAuthToken, authSyncChats, authLoadChats } from '../lib/api'

type AuthContextType = {
  user: AuthUser | null
  loading: boolean
  isLoggedIn: boolean
  login: (user: AuthUser) => void
  logout: () => Promise<void>
  syncChats: (threads: Array<{ id: string; title: string; messages: unknown[]; updatedAt: number }>) => Promise<void>
  loadChats: () => Promise<Array<{ id: string; title: string; messages: unknown[]; updatedAt: number }>>
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider(props: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  // Check for existing session on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = getAuthToken()
      if (!token) {
        setLoading(false)
        return
      }

      try {
        const result = await authGetMe()
        if (result.ok && result.user) {
          setUser(result.user)
        }
      } catch {
        // Session invalid
      } finally {
        setLoading(false)
      }
    }

    checkAuth()
  }, [])

  const login = useCallback((newUser: AuthUser) => {
    setUser(newUser)
  }, [])

  const logout = useCallback(async () => {
    await authLogout()
    setUser(null)
  }, [])

  const syncChats = useCallback(async (threads: Array<{ id: string; title: string; messages: unknown[]; updatedAt: number }>) => {
    if (!user) return
    await authSyncChats(threads)
  }, [user])

  const loadChats = useCallback(async () => {
    if (!user) return []
    return await authLoadChats()
  }, [user])

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isLoggedIn: !!user,
        login,
        logout,
        syncChats,
        loadChats,
      }}
    >
      {props.children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
