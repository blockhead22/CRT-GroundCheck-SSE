import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import type { NavId } from '../types'

const validNavIds: NavId[] = ['chat', 'dashboard', 'loops', 'journal', 'jobs', 'docs', 'showcase', 'copilot', 'live', 'telemetry']

export function useNavigation() {
  const navigate = useNavigate()
  const location = useLocation()

  const navFromUrl = (): NavId => {
    const path = location.pathname.replace(/^\//, '').split('/')[0] || 'chat'
    return validNavIds.includes(path as NavId) ? (path as NavId) : 'chat'
  }

  const [navActive, setNavActiveRaw] = useState<NavId>(navFromUrl)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const setNavActive = useCallback((id: NavId) => {
    setNavActiveRaw(id)
    navigate(id === 'chat' ? '/' : `/${id}`)
  }, [navigate])

  // Sync on browser back/forward
  useEffect(() => {
    setNavActiveRaw(navFromUrl())
  }, [location.pathname])

  return { navActive, setNavActive, sidebarOpen, setSidebarOpen }
}
