import type { ChatThread, QuickAction } from '../types'

export const quickActions: QuickAction[] = [
  {
    id: 'qa_24h',
    icon: '⏱',
    title: "What’s happening in 24 hours?",
    subtitle: "See what’s been happening in the world over the last day",
    seedPrompt: "What's happened in the last 24 hours?",
  },
  {
    id: 'qa_market',
    icon: '📈',
    title: 'Stock market update',
    subtitle: "See what’s happening in the stock market in real time",
    seedPrompt: 'Give me a quick stock market update.',
  },
  {
    id: 'qa_econ',
    icon: '🧠',
    title: 'Deep economic research',
    subtitle: "See research from experts that we’ve simplified",
    seedPrompt: 'Summarize a recent economic topic in plain language.',
  },
]

export function seedThreads(): ChatThread[] {
  const now = Date.now()
  return [
    { id: 't1', title: 'Brainstorming small business ideas', updatedAt: now - 86400_000 * 1, messages: [] },
    { id: 't2', title: 'The history of roman empire', updatedAt: now - 86400_000 * 3, messages: [] },
    { id: 't3', title: 'Crypto investment suggestions', updatedAt: now - 86400_000 * 7, messages: [] },
  ]
}
