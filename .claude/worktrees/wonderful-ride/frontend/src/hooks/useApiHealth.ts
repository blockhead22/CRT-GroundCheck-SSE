import { useState, useEffect } from 'react'
import { getEffectiveApiBaseUrl, getHealth, setEffectiveApiBaseUrl } from '../lib/api'

export function useApiHealth() {
  const [apiStatus, setApiStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking')
  const [apiBaseUrl, setApiBaseUrl] = useState<string>(getEffectiveApiBaseUrl())

  useEffect(() => {
    let mounted = true
    async function ping() {
      try {
        await getHealth()
        if (mounted) setApiStatus('connected')
      } catch (_e) {
        if (mounted) setApiStatus('disconnected')
      }
    }
    void ping()
    const id = window.setInterval(() => void ping(), 5000)
    return () => {
      mounted = false
      window.clearInterval(id)
    }
  }, [])

  useEffect(() => {
    setEffectiveApiBaseUrl(apiBaseUrl)
  }, [apiBaseUrl])

  return { apiStatus, apiBaseUrl, setApiBaseUrl }
}
