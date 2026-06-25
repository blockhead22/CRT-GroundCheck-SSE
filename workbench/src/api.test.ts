import { api } from './api'

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
