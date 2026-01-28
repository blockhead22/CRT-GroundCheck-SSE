import type { ChatThread, QuickAction } from '../types'

export const quickActions: QuickAction[] = [
  {
    id: 'qa_job_contradiction',
    icon: '',
    title: 'Test job change contradiction',
    subtitle: 'See CRT catch contradictions about employment',
    seedPrompt: 'I work at Google as a software engineer.',
  },
  {
    id: 'qa_gaslighting',
    icon: '',
    title: 'Test gaslighting detection',
    subtitle: 'Watch CRT cite your own claims when you deny them',
    seedPrompt: 'I live in San Francisco.',
  },
  {
    id: 'qa_location',
    icon: '',
    title: 'Test location tracking',
    subtitle: 'See hybrid LLM+regex claim extraction in action',
    seedPrompt: 'I just moved to New York last week.',
  },
]

export function seedThreads(): ChatThread[] {
  const now = Date.now()
  return [
    { id: 't1', title: 'Job contradiction test', updatedAt: now - 86400_000 * 1, messages: [] },
    { id: 't2', title: 'Location tracking test', updatedAt: now - 86400_000 * 3, messages: [] },
    { id: 't3', title: 'Gaslighting detection demo', updatedAt: now - 86400_000 * 7, messages: [] },
  ]
}
