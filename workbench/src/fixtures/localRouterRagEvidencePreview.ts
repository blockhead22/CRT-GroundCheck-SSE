import { localRouterRagEvidenceReview } from './localRouterRagEvidenceReview'
import type { ConsolidationPreview } from '../types'

export const localRouterRagEvidencePreview = {
  mode: 'preview_only',
  writes_performed: false,
  memory_ingestion_performed: false,
  support_pattern_import_performed: false,
  reflection_create_performed: false,
  inspected_turn_count: localRouterRagEvidenceReview.case_count,
  candidates: [{
    candidate_id: 'local_router_rag_evidence_adversarial_v2',
    candidate_type: 'background_consolidation_candidate',
    category: 'local_router_rag_evidence',
    candidate_kind: 'baseline_evidence_review',
    summary: 'Adversarial v2: governed passed 6/6 with trace 6/6; scaffolded RAG passed 5/6.',
    proposed_action: 'Review as evidence for governed cognition, but do not tune against this pack again.',
    risk: 'Small holdout and perfect governed score require caution; this is evidence for review, not a product or grant claim by itself.',
    review_required: true,
    memory_write_allowed: false,
    confirmed_fact: false,
    review_route: {
      surface: 'reflections',
      action: 'review_rag_evidence',
      endpoint: '/v1/reflections',
      requires_adapter: true,
      draft: {
        subject: 'agent',
        observation: 'In adversarial v2, governed Aether passed 6/6 with trace 6/6 while scaffolded RAG passed 5/6.',
        interpretation: 'Governance appears to add reviewable value over scaffolded RAG on receipt-boundary and wrong-memory holdout cases, but the pack is small and should not be treated as final proof.',
        alternatives: [
          'The result may partially reflect pack design or evaluator fit.',
          'A larger blind/adversarial mix may reveal additional governed failure modes.',
        ],
        confidence: 0.62,
        time_window: 'local-router RAG adversarial v2 holdout',
        suggested_experiment: 'Review the evidence in Workbench, then test a larger blind/adversarial mix only if a specific evidence question remains.',
      },
    },
    evidence: [{
      evidence_type: 'rag_suite_result',
      reference_id: localRouterRagEvidenceReview.result_path,
      summary: 'governed 6/6 trace 6/6 vs scaffolded_rag 5/6; delta +1 pass, +0.022 avg',
    }, {
      evidence_type: 'safety_contract',
      reference_id: 'local_router_rag_evidence_review',
      summary: 'review_only; memory writes blocked; raw hidden CoT not stored; silent policy mutation blocked',
    }],
  }],
} as const satisfies ConsolidationPreview
