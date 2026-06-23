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

beforeEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.endsWith('/health')) return new Response(JSON.stringify(health), { status: 200 })
    if (url.endsWith('/v1/models')) return new Response(JSON.stringify({ models: [{ name: health.model }] }), { status: 200 })
    if (url.endsWith('/v1/conversations')) return new Response(JSON.stringify({ conversations }), { status: 200 })
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
