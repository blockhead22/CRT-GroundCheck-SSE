import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from './App'

const health = {
  ok: true,
  aether: 'ready',
  ollama: 'ready',
  model: 'qwen2.5:7b-instruct',
  codex_available: false,
  substrate: { path: 'test', slots: 2, states: 3, revision_hash: 'rev' },
}

const conversations = [
  {
    conversation_id: 'conv-1',
    title: 'Existing chat',
    created_at: 1,
    updated_at: 2,
  },
]

const trace = {
  query: 'old question',
  status: 'needs_clarification',
  turn_id: 'turn-old',
  conversation_id: 'conv-1',
  model: 'qwen2.5:7b-instruct',
  generation_model: 'deterministic',
  completion: {
    source: 'aether_meta',
    needs_stronger_model: false,
    generation_model: 'deterministic',
  },
  plan: {
    status: 'unknown',
    coverage: 0,
    unresolved_clauses: [],
    clauses: [
      {
        clause_id: 'c1',
        text: 'old question',
        status: 'unresolved',
        candidate_slots: [],
        reason_code: 'no_candidate_above_threshold',
      },
    ],
  },
  packets: [],
}

const turns = [
  {
    turn_id: 'turn-old',
    user_message: 'old question',
    local_answer: 'old answer',
    model: 'qwen2.5:7b-instruct',
    needs_stronger_model: false,
    created_at: 1,
  },
]

beforeEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.endsWith('/health')) return new Response(JSON.stringify(health), { status: 200 })
    if (url.endsWith('/v1/models')) return new Response(JSON.stringify({ models: [{ name: health.model }] }), { status: 200 })
    if (url.endsWith('/v1/conversations')) return new Response(JSON.stringify({ conversations }), { status: 200 })
    if (url.endsWith('/v1/conversations/conv-1/turns')) return new Response(JSON.stringify({ turns }), { status: 200 })
    if (url.endsWith('/v1/traces/turn-old')) return new Response(JSON.stringify({ trace }), { status: 200 })
    if (url.includes('/v1/slots')) return new Response(JSON.stringify({ revision_hash: 'rev', slots: [] }), { status: 200 })
    return new Response(JSON.stringify({ turns: [] }), { status: 200 })
  }))
})

test('opens the trace drawer and expands the desktop window', async () => {
  render(<App />)
  await screen.findByText('Local')
  fireEvent.click(screen.getByRole('button', { name: 'Trace' }))
  expect(screen.getByLabelText('trace drawer')).toBeInTheDocument()
  expect(window.aetherDesktop?.setExpanded).toHaveBeenCalledWith(true)
})

test('shows Codex availability in settings', async () => {
  render(<App />)
  await screen.findByText('Local')
  fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
  await waitFor(() => expect(screen.getByText('unavailable')).toBeInTheDocument())
})

test('opens the reflect drawer from bottom navigation', async () => {
  render(<App />)
  await screen.findByText('Local')
  fireEvent.click(screen.getByRole('button', { name: 'Reflect' }))
  expect(screen.getByLabelText('reflect drawer')).toBeInTheDocument()
  expect(screen.getByText('Reflection review')).toBeInTheDocument()
  expect(window.aetherDesktop?.setExpanded).toHaveBeenCalledWith(true)
})

test('starts a new chat without deleting durable knowledge', async () => {
  localStorage.setItem('aether.currentConversation', 'conv-1')
  render(<App />)
  await screen.findByDisplayValue('Existing chat')
  fireEvent.click(screen.getByRole('button', { name: 'New chat' }))
  expect(screen.getByRole('combobox', { name: 'Conversation' })).toHaveValue('')
  expect(localStorage.getItem('aether.currentConversation')).toBeNull()
})

test('deletes only the current chat after explicit confirmation', async () => {
  localStorage.setItem('aether.currentConversation', 'conv-1')
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const fetchMock = vi.mocked(fetch)
  render(<App />)
  await screen.findByDisplayValue('Existing chat')
  fireEvent.click(screen.getByRole('button', { name: 'Delete current chat' }))

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining('/v1/conversations/conv-1'),
    expect.objectContaining({ method: 'DELETE' }),
  ))
  expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('Governed memory'))
})

test('opens a historical turn trace from the assistant answer', async () => {
  localStorage.setItem('aether.currentConversation', 'conv-1')
  const fetchMock = vi.mocked(fetch)
  render(<App />)
  await screen.findByText('old answer')

  fireEvent.click(screen.getByRole('button', { name: 'Open trace for turn turn-old' }))

  await screen.findByLabelText('trace drawer')
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining('/v1/traces/turn-old'),
    expect.anything(),
  ))
  const route = screen.getByLabelText('Response route')
  expect(route).toHaveTextContent('aether meta')
  expect(route).toHaveTextContent('deterministic')
})
