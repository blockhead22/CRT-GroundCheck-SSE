import { useState, useMemo, useEffect, useCallback } from 'react'
import type { ChatThread, NavId } from '../types'
import type { AuthUser } from '../lib/api'
import { authSyncChats } from '../lib/api'
import { newId } from '../lib/id'
import { loadChatStateFromStorage, saveChatStateToStorage } from '../lib/chatStorage'
import { seedThreads } from '../lib/seed'

type UseChatThreadsOpts = {
  setNavActive: (id: NavId) => void
}

export function useChatThreads({ setNavActive }: UseChatThreadsOpts) {
  // authUser is set reactively from App via setAuthUserForSync
  const [authUser, setAuthUserForSync] = useState<AuthUser | null>(null)
  const [threads, setThreads] = useState<ChatThread[]>(() => {
    const loaded = loadChatStateFromStorage()
    return loaded.threads.length ? loaded.threads : seedThreads()
  })
  const [selectedThreadId, setSelectedThreadId] = useState<string>(() => {
    const loaded = loadChatStateFromStorage()
    if (loaded.selectedThreadId) return loaded.selectedThreadId
    return loaded.threads[0]?.id ?? seedThreads()[0]?.id ?? 't1'
  })
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null)

  // Rename lightbox state
  const [renameOpen, setRenameOpen] = useState(false)
  const [renameThreadId, setRenameThreadId] = useState<string | null>(null)

  const selectedThread = useMemo(
    () => threads.find((t) => t.id === selectedThreadId) ?? threads[0],
    [threads, selectedThreadId],
  )

  const selectedMessage = useMemo(() => {
    if (!selectedThread || !selectedMessageId) return null
    return selectedThread.messages.find((m) => m.id === selectedMessageId) ?? null
  }, [selectedThread, selectedMessageId])

  const upsertThread = useCallback((updated: ChatThread) => {
    setThreads((prev) => {
      const exists = prev.some((t) => t.id === updated.id)
      const next = exists ? prev.map((t) => (t.id === updated.id ? updated : t)) : [updated, ...prev]
      next.sort((a, b) => b.updatedAt - a.updatedAt)
      return next
    })
  }, [])

  function openRename(id: string) {
    setRenameThreadId(id)
    setRenameOpen(true)
  }

  function renameThread(id: string, title: string) {
    const clean = title.trim()
    if (!clean) return
    const now = Date.now()
    setThreads((prev) => {
      const next = prev.map((t) => (t.id === id ? { ...t, title: clean, updatedAt: now } : t))
      next.sort((a, b) => b.updatedAt - a.updatedAt)
      return next
    })
  }

  const newThread = useCallback(() => {
    const now = Date.now()
    const t: ChatThread = { id: newId('t'), title: 'New chat', updatedAt: now, messages: [] }
    setThreads((prev) => [t, ...prev].sort((a, b) => b.updatedAt - a.updatedAt))
    setSelectedThreadId(t.id)
    setSelectedMessageId(null)
    setNavActive('chat')
  }, [setNavActive])

  const deleteThread = useCallback((id: string) => {
    setThreads((prev) => {
      const remaining = prev.filter((t) => t.id !== id)
      if (selectedThreadId === id) {
        const next = remaining[0]
        if (next) {
          setSelectedThreadId(next.id)
        } else {
          const now = Date.now()
          const t: ChatThread = { id: newId('t'), title: 'New chat', updatedAt: now, messages: [] }
          remaining.unshift(t)
          setSelectedThreadId(t.id)
        }
        setSelectedMessageId(null)
        setNavActive('chat')
      }
      return remaining
    })
  }, [selectedThreadId, setNavActive])

  // Persist threads + selection to localStorage
  useEffect(() => {
    const id = window.setTimeout(() => {
      saveChatStateToStorage({ threads, selectedThreadId: selectedThread?.id ?? selectedThreadId ?? null })
    }, 150)
    return () => window.clearTimeout(id)
  }, [threads, selectedThread?.id, selectedThreadId])

  // Sync threads to server when logged in
  useEffect(() => {
    if (!authUser) return

    const syncTimer = window.setTimeout(() => {
      authSyncChats(threads.map(t => ({
        id: t.id,
        title: t.title,
        messages: t.messages,
        updatedAt: t.updatedAt
      }))).catch(() => {})
    }, 2000)

    return () => window.clearTimeout(syncTimer)
  }, [authUser, threads])

  return {
    threads,
    setThreads,
    selectedThread,
    selectedThreadId,
    setSelectedThreadId,
    selectedMessage,
    selectedMessageId,
    setSelectedMessageId,
    upsertThread,
    newThread,
    deleteThread,
    openRename,
    renameThread,
    renameOpen,
    renameThreadId,
    setRenameOpen,
    setRenameThreadId,
    setAuthUserForSync,
  }
}
