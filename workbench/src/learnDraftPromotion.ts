import type { ReviewDraftHandoff } from './types'

export interface SupportDraftForm {
  category: string
  candidateKind: string
  summary: string
  suggestedResponseRule: string
  risk: string
}

export interface ReflectionDraftForm {
  subject: string
  observation: string
  interpretation: string
  alternatives: string
  confidence: string
  timeWindow: string
  suggestedExperiment: string
}

export function buildSupportDraftCandidate(draftHandoff: ReviewDraftHandoff, draft: SupportDraftForm) {
  const evidence = draftHandoff.evidence.length
    ? draftHandoff.evidence.map((item) => ({
      evidence_type: item.evidence_type || 'learner_candidate',
      conversation_id: item.reference_id || draftHandoff.source_candidate_id,
      title: item.summary || draftHandoff.summary,
    }))
    : [{
      evidence_type: 'learner_candidate',
      conversation_id: draftHandoff.source_candidate_id,
      title: draftHandoff.summary,
    }]

  return {
    candidate_id: `learn_${draftHandoff.source_candidate_id}`,
    candidate_type: 'archive_support_pattern',
    category: draft.category,
    candidate_kind: draft.candidateKind,
    summary: draft.summary,
    suggested_response_rule: draft.suggestedResponseRule,
    risk: draft.risk,
    source_signal: 'learner_consolidation_candidate',
    title_category_count: Math.max(1, evidence.length),
    evidence,
    status: 'proposed_review',
    review_required: true,
    memory_write_allowed: false,
    confirmed_fact: false,
  }
}

export function buildReflectionDraftPayload(draftHandoff: ReviewDraftHandoff, draft: ReflectionDraftForm) {
  const alternatives = draft.alternatives
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
  const evidence = draftHandoff.evidence.length
    ? draftHandoff.evidence.map((item) => ({
      evidence_type: item.evidence_type || 'learner_candidate',
      reference_id: item.reference_id || draftHandoff.source_candidate_id,
      summary: item.summary || draftHandoff.summary,
    }))
    : [{
      evidence_type: 'learner_candidate',
      reference_id: draftHandoff.source_candidate_id,
      summary: draftHandoff.summary,
    }]

  return {
    subject: draft.subject,
    observation: draft.observation,
    interpretation: draft.interpretation,
    alternatives,
    confidence: Number.parseFloat(draft.confidence) || 0.45,
    time_window: draft.timeWindow,
    suggested_experiment: draft.suggestedExperiment,
    evidence: [
      ...evidence,
      {
        evidence_type: 'learner_risk_boundary',
        reference_id: draftHandoff.source_candidate_id,
        summary: draftHandoff.risk || 'Learner draft required manual review before promotion.',
      },
    ],
  }
}
