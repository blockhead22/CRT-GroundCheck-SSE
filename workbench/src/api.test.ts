import { api, streamChat } from './api'

beforeEach(() => {
  vi.restoreAllMocks()
})

test('imports support-pattern draft candidates through the proposed-review endpoint envelope', async () => {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify({
    imported_count: 1,
    candidates: [],
  }), { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)

  const candidate = {
    candidate_id: 'learn_consolidation_candidate_support',
    status: 'proposed_review',
    review_required: true,
    memory_write_allowed: false,
    confirmed_fact: false,
  }
  await api.importSupportPatterns([candidate])

  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining('/v1/support-patterns/import'),
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ candidates: [candidate] }),
    }),
  )
})

test('creates reflection draft payloads through the proposed reflection endpoint', async () => {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify({
    reflection_id: 'reflection-1',
    subject: 'agent',
    observation: 'A recent answer may reveal a behavior improvement.',
    interpretation: '',
    alternatives: [],
    confidence: 0.45,
    time_window: 'recent turns',
    suggested_experiment: '',
    status: 'proposed',
    created_at: 1,
    updated_at: 1,
    revision_hash: 'revision-1',
    evidence: [],
    reviews: [],
  }), { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)

  const reflection = {
    subject: 'agent',
    observation: 'A recent answer may reveal a behavior improvement.',
    confidence: 0.45,
    evidence: [{
      evidence_type: 'learner_risk_boundary',
      reference_id: 'consolidation_candidate_reflection',
      summary: 'Do not convert one thin answer into a permanent behavior rule.',
    }],
  }
  await api.createReflection(reflection)

  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining('/v1/reflections'),
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify(reflection),
    }),
  )
})

test('streamChat dispatches public governance steps before answer tokens', async () => {
  const encoder = new TextEncoder()
  const body = [
    'event: turn\ndata: {"turn_id":"turn-1","conversation_id":"conv-1"}\n\n',
    'event: trace\ndata: {"turn_id":"turn-1","public_governance_steps":[]}\n\n',
    'event: governance_step\ndata: {"schema":"aether.public_governance_step.v0","step_id":"gov-step-01-memory_check","index":1,"phase":"memory_check","status":"done","summary":"Checked governed memory","detail":"1 released packet.","public":true,"raw_chain_of_thought":false}\n\n',
    'event: token\ndata: {"text":"Hello"}\n\n',
    'event: done\ndata: {"answer":"Hello","needs_stronger_model":false}\n\n',
  ]
  const fetchMock = vi.fn(async () => new Response(new ReadableStream({
    start(controller) {
      for (const chunk of body) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  }), { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)

  const events: string[] = []
  await streamChat(
    { message: 'hi', model: 'qwen2.5:7b-instruct', voice_profile: 'alive' },
    {
      onTurn: () => events.push('turn'),
      onTrace: () => events.push('trace'),
      onGovernanceStep: (step) => {
        events.push(`governance:${step.phase}:${step.raw_chain_of_thought}`)
      },
      onToken: (text) => events.push(`token:${text}`),
      onDone: () => events.push('done'),
      onError: (message) => events.push(`error:${message}`),
    },
  )

  expect(events).toEqual([
    'turn',
    'trace',
    'governance:memory_check:false',
    'token:Hello',
    'done',
  ])
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining('/v1/chat/stream'),
    expect.objectContaining({
      body: JSON.stringify({
        message: 'hi',
        model: 'qwen2.5:7b-instruct',
        voice_profile: 'alive',
      }),
    }),
  )
})
