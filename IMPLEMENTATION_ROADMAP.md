# CRT Implementation Roadmap

**Comprehensive planning document for enterprise adoption and active learning tracks**

**Version:** 1.0  
**Created:** 2026-01-21  
**Status:** Planning Phase - Awaiting Review & Approval

---

## Executive Summary

This roadmap details the implementation plan for two parallel tracks:

1. **Enterprise Adoption Track** - Scale CRT for production use (millions of users)
2. **Active Learning Track** - Build self-improving ML systems

**Approach:** Hybrid implementation allowing both tracks to scale independently while sharing infrastructure.

**Timeline:** 12-week initial phase, 24-week full deployment  
**Resource Requirements:** 2-3 engineers, 1 ML specialist, infrastructure budget  
**Risk Level:** Medium (well-defined scope, incremental rollout, failure checkpoints)

---

## Table of Contents

1. [Strategic Goals](#strategic-goals)
2. [Architecture Overview](#architecture-overview)
3. [Track 1: Enterprise Adoption (4 Phases)](#track-1-enterprise-adoption)
4. [Track 2: Active Learning (6 Phases)](#track-2-active-learning)
5. [Hybrid Integration Plan](#hybrid-integration-plan)
6. [Milestones & Deliverables](#milestones--deliverables)
7. [Success Criteria](#success-criteria)
8. [Failure Checkpoints](#failure-checkpoints)
9. [Resource Requirements](#resource-requirements)
10. [Risk Assessment](#risk-assessment)

---

## Strategic Goals

### Primary Objectives

1. **Scale CRT to enterprise-level usage** (10K+ users, 1M+ memories)
2. **Build self-improving systems** that learn from user corrections
3. **Maintain backward compatibility** with v0.9-beta
4. **Preserve zero-violation invariant** throughout scaling
5. **Create reusable infrastructure** for both tracks

### Non-Goals (Scope Limitations)

- ❌ Multi-tenant isolation (post-v1.0)
- ❌ Real-time collaborative memory (future)
- ❌ Complete rewrite of core systems
- ❌ Support for non-English languages (initial release)

---

## Architecture Overview

### Current State (v0.9-beta)

```
┌─────────────────┐
│   FastAPI       │  Single-process, SQLite-backed
│   crt_api.py    │  
└────────┬────────┘
         │
    ┌────▼────────────────────┐
    │ CRT Core (crt_rag.py)   │
    │ - Contradiction detect  │
    │ - Trust scoring         │
    │ - Memory retrieval      │
    └────┬────────────────────┘
         │
    ┌────┴──────┬──────────┐
    │           │          │
┌───▼────┐ ┌───▼─────┐ ┌──▼──────┐
│Memory  │ │ Ledger  │ │ Active  │
│SQLite  │ │ SQLite  │ │Learning │
└────────┘ └─────────┘ └─────────┘
```

**Limitations:**
- Single process (no horizontal scaling)
- SQLite (max ~100K users before performance degrades)
- Synchronous contradiction detection (adds latency)
- No distributed caching
- Manual model updates (no hot-reloading)

### Target State (v1.0 Enterprise)

```
┌────────────────────────────────────────────────────┐
│          Load Balancer (nginx/HAProxy)             │
└─────────┬──────────────────────────────────────────┘
          │
    ┌─────┴────────┬────────────┬───────────────┐
    │              │            │               │
┌───▼────────┐ ┌──▼─────────┐ ┌▼──────────┐ ┌─▼────────┐
│ API Node 1 │ │ API Node 2 │ │ API Node 3│ │ API Node N│
│ (FastAPI)  │ │ (FastAPI)  │ │ (FastAPI) │ │ (FastAPI) │
└─────┬──────┘ └──────┬─────┘ └─────┬─────┘ └─────┬────┘
      │               │              │             │
      └───────────────┴──────────────┴─────────────┘
                      │
    ┌─────────────────▼──────────────────────┐
    │  Shared Services Layer                 │
    │  ┌──────────────┐  ┌─────────────────┐ │
    │  │ Redis Cache  │  │ Message Queue   │ │
    │  │ (hot memory) │  │ (RabbitMQ/Kafka)│ │
    │  └──────────────┘  └─────────────────┘ │
    └────────────────────────────────────────┘
                      │
    ┌─────────────────▼──────────────────────┐
    │  Data Layer (Postgres Cluster)         │
    │  ┌──────────┐  ┌──────────┐  ┌───────┐│
    │  │ Memories │  │  Ledger  │  │ Learn │││
    │  │  (hot)   │  │  (append)│  │ Stats │││
    │  └──────────┘  └──────────┘  └───────┘│
    └────────────────────────────────────────┘
                      │
    ┌─────────────────▼──────────────────────┐
    │  Background Workers (Async)            │
    │  ┌───────────────┐  ┌────────────────┐ │
    │  │ Contradiction │  │ ML Training    │ │
    │  │ Detection     │  │ Pipeline       │ │
    │  └───────────────┘  └────────────────┘ │
    └────────────────────────────────────────┘
```

**Improvements:**
- Horizontal scaling (N API nodes behind load balancer)
- Postgres (millions of users, ACID guarantees)
- Async contradiction detection (non-blocking)
- Redis caching (hot memories, <10ms retrieval)
- Message queue (decouple API from background work)
- Background workers (training, detection, analytics)

---

## Track 1: Enterprise Adoption

**Goal:** Scale CRT to handle millions of users with <100ms latency

### Phase 1: Silent Detection (Weeks 1-3)

**Objective:** Add contradiction detection without changing user-facing behavior

**Implementation:**

1. **Database Migration**
   - Migrate SQLite → Postgres
   - Preserve schema compatibility
   - Add indexes for performance
   - Create read replicas for scaling

2. **Async Detection Pipeline**
   - Message queue for detection jobs
   - Background workers process contradictions
   - Log results to new `contradiction_detection_log` table
   - No user-facing changes yet

3. **Telemetry System**
   - Log every contradiction detected
   - Track false positive rate
   - Measure detection latency
   - Dashboard for ops team

**Deliverables:**
- ✅ Postgres migration script
- ✅ Message queue integration
- ✅ Background worker service
- ✅ Detection telemetry dashboard
- ✅ Performance benchmarks (target: <50ms p95 latency)

**Success Criteria:**
- Zero data loss during migration
- Detection runs async (API latency unchanged)
- False positive rate measured and <10%
- 95% of contradictions detected within 5 seconds

**Failure Checkpoint:**
- If false positive rate >20%, pause and retune detection algorithm
- If migration causes data corruption, rollback to SQLite
- If performance degrades >2x, abort and redesign

**Technical Specs:** See [PHASE1_SILENT_DETECTION_SPEC.md](./roadmap/PHASE1_SILENT_DETECTION_SPEC.md)

---

### Phase 2: Soft Disclosure (Weeks 4-6)

**Objective:** Surface contradictions in metadata without interrupting flow

**Implementation:**

1. **Metadata Enrichment**
   - Add `contradiction_flags` to response metadata
   - Include contradiction IDs for debugging
   - No changes to answer text yet

2. **UI Indicators (Optional)**
   - Badge/icon showing "conflicting info"
   - Click to see contradiction details
   - Non-blocking UX

3. **User Feedback Collection**
   - Track if users click contradiction badges
   - Measure engagement with disclosure
   - A/B test: With vs without indicators

**Deliverables:**
- ✅ Metadata enrichment in API responses
- ✅ Optional UI component for badges
- ✅ Feedback collection endpoint
- ✅ A/B test framework
- ✅ User engagement analytics

**Success Criteria:**
- >5% of users click on contradiction badges
- <1% increase in support tickets about "confusing warnings"
- User trust metrics stable or improved

**Failure Checkpoint:**
- If users complain about "too many warnings", dial back threshold
- If engagement <1%, disclosure may not be valuable to users
- If trust metrics drop >10%, rollback feature

**Technical Specs:** See [PHASE2_SOFT_DISCLOSURE_SPEC.md](./roadmap/PHASE2_SOFT_DISCLOSURE_SPEC.md)

---

### Phase 3: Full Ledger (Weeks 7-10)

**Objective:** Implement complete audit trail for enterprise customers

**Implementation:**

1. **Enhanced Ledger Schema**
   - Add provenance tracking (who, when, why)
   - Capture full context for each contradiction
   - Immutable append-only log

2. **API Endpoints for Ledger Access**
   - `/api/contradictions/list` - List all contradictions
   - `/api/contradictions/{id}` - Get detailed view
   - `/api/contradictions/export` - CSV/JSON export for compliance

3. **Admin Dashboard**
   - Visual timeline of contradictions
   - Search/filter by user, date, type
   - Resolution tracking

**Deliverables:**
- ✅ Enhanced ledger schema migration
- ✅ Ledger API endpoints (RESTful)
- ✅ Admin dashboard (React component)
- ✅ Export functionality for compliance
- ✅ Documentation for enterprise admins

**Success Criteria:**
- 100% of contradictions logged with provenance
- Ledger API responds in <200ms p95
- Exports work for 10K+ entries
- Dashboard usable by non-technical admins

**Failure Checkpoint:**
- If ledger storage grows >10GB/month, implement archiving
- If API latency >500ms, add caching layer
- If dashboard is unusable, simplify UI

**Technical Specs:** See [PHASE3_FULL_LEDGER_SPEC.md](./roadmap/PHASE3_FULL_LEDGER_SPEC.md)

---

### Phase 4: AI-Assisted Resolution (Weeks 11-14)

**Objective:** Use LLM to suggest contradiction resolutions

**Implementation:**

1. **Resolution Suggestion Engine**
   - Analyze contradiction context with LLM
   - Suggest: "Update to new value", "Keep both", "Ask user"
   - Confidence scoring for suggestions

2. **One-Click Resolution**
   - User approves/rejects suggestion
   - System applies resolution automatically
   - Log user decision for learning

3. **Auto-Resolution (Conservative)**
   - For high-confidence, low-risk contradictions
   - e.g., "I moved to Denver" → auto-update location
   - Always log for audit

**Deliverables:**
- ✅ LLM-based resolution suggester
- ✅ UI for one-click resolution
- ✅ Auto-resolution policy engine
- ✅ Safety guardrails (rollback mechanism)
- ✅ User satisfaction survey

**Success Criteria:**
- >70% of suggestions accepted by users
- Auto-resolution accuracy >90%
- Average resolution time reduced by 50%
- Zero accidental data loss from auto-resolution

**Failure Checkpoint:**
- If suggestion acceptance <50%, improve LLM prompts
- If auto-resolution causes errors, disable and manual-only
- If users report confusion, simplify resolution flow

**Technical Specs:** See [PHASE4_AI_RESOLUTION_SPEC.md](./roadmap/PHASE4_AI_RESOLUTION_SPEC.md)

---

## Track 2: Active Learning

**Goal:** Build ML systems that improve from user corrections

### Phase 1: Data Collection Infrastructure (Weeks 1-2)

**Objective:** Capture all interactions for ML training

**Implementation:**

1. **Interaction Logging**
   - Log every query, response, user reaction
   - Schema: `{query, slots_inferred, facts_injected, response, user_feedback}`
   - Privacy-preserving (anonymize PII)

2. **Feedback API**
   - `/api/feedback/thumbs` - Up/down voting
   - `/api/feedback/correction` - "Actually, my name is X"
   - `/api/feedback/report` - Report incorrect behavior

3. **Training Data Storage**
   - Separate DB: `active_learning.db`
   - Tables: `interaction_logs`, `corrections`, `conflict_resolutions`
   - Daily backup and archival

**Deliverables:**
- ✅ Logging middleware for all API calls
- ✅ Feedback API endpoints
- ✅ Training data DB schema
- ✅ Data export pipeline for ML
- ✅ Privacy audit (ensure PII anonymization)

**Success Criteria:**
- 100% of interactions logged (no silent failures)
- Feedback API responds in <50ms
- Storage cost <$100/month for 10K users
- Privacy audit passes (no PII leaks)

**Failure Checkpoint:**
- If logging adds >10ms latency, make fully async
- If storage grows >1GB/day, implement sampling
- If privacy violations found, pause and fix

**Technical Specs:** See [PHASE1_DATA_COLLECTION_SPEC.md](./roadmap/PHASE1_DATA_COLLECTION_SPEC.md)

---

### Phase 2: Query→Slot Learning (Weeks 3-4)

**Objective:** Learn which slots to extract from which queries

**Implementation:**

1. **Baseline Dataset**
   - Analyze logged interactions
   - Label: Which slots were actually used in responses
   - Training set: 1000+ query-slot pairs

2. **Lightweight Classifier**
   - Input: Query embedding (384d via sentence-transformers)
   - Output: Slot probabilities (15 slots, 0-1 score each)
   - Model: Logistic regression or small NN
   - Training time: <5 minutes on laptop

3. **A/B Testing**
   - 10% traffic to learned model
   - 90% traffic to rule-based (control)
   - Compare: Accuracy, latency, user satisfaction

**Deliverables:**
- ✅ Dataset generation script
- ✅ Model training pipeline
- ✅ A/B test framework
- ✅ Accuracy comparison report
- ✅ Model versioning system

**Success Criteria:**
- Learned model accuracy >90% vs rule-based
- Inference latency <10ms
- No regressions in user satisfaction
- Model size <10MB (fast loading)

**Failure Checkpoint:**
- If accuracy <80%, need more training data
- If latency >50ms, use smaller model
- If user satisfaction drops, rollback to rules

**Technical Specs:** See [PHASE2_SLOT_LEARNING_SPEC.md](./roadmap/PHASE2_SLOT_LEARNING_SPEC.md)

---

### Phase 3: Fact Extraction Fine-Tuning (Weeks 5-6)

**Objective:** Improve confidence in fact extraction

**Implementation:**

1. **Correction Dataset**
   - Collect user corrections: "No, my name is Alice, not Alison"
   - Label: Correct vs incorrect extractions
   - Training set: 500+ correction examples

2. **Confidence Predictor**
   - Input: Text + candidate slot value
   - Output: Extraction confidence (0-1)
   - Model: Fine-tuned BERT or RoBERTa (small)

3. **Probabilistic Extraction**
   - Replace binary regex with confidence-based
   - Threshold: Only extract if confidence >0.7
   - Low-confidence → ask for confirmation

**Deliverables:**
- ✅ Correction dataset builder
- ✅ Fine-tuned extraction model
- ✅ Confidence-based extraction pipeline
- ✅ Confirmation prompt generator
- ✅ Accuracy benchmarks

**Success Criteria:**
- User correction rate drops from ~15% to <5%
- False positive rate <3%
- Confirmation prompts accepted >80%
- Model inference <20ms

**Failure Checkpoint:**
- If correction rate doesn't improve, retune model
- If too many confirmation prompts, raise threshold
- If model too large (>100MB), use distillation

**Technical Specs:** See [PHASE3_EXTRACTION_TUNING_SPEC.md](./roadmap/PHASE3_EXTRACTION_TUNING_SPEC.md)

---

### Phase 4: Conflict Resolution Learning (Weeks 7-8)

**Objective:** Learn user preferences for contradiction handling

**Implementation:**

1. **User Interaction Dataset**
   - Log responses to contradiction prompts
   - Label: Accept new, keep old, ask later
   - User history features: Past resolutions, context

2. **Resolution Policy**
   - Input: (old_fact, new_fact, context, user_history)
   - Output: Action (auto-update, prompt, ignore)
   - Model: Decision tree or random forest

3. **Personalized Resolution**
   - Learn per-user preferences
   - Some users: "Always ask"
   - Some users: "Auto-update volatile facts"

**Deliverables:**
- ✅ Resolution interaction logs
- ✅ Policy learning pipeline
- ✅ Per-user preference profiles
- ✅ Adaptive resolution engine
- ✅ User satisfaction metrics

**Success Criteria:**
- Auto-resolution accuracy >85%
- Prompts reduced by 30% (less user friction)
- User satisfaction stable or improved
- Policy learns in <10 interactions per user

**Failure Checkpoint:**
- If accuracy <70%, fall back to always-prompt
- If users report unexpected updates, disable auto
- If learning requires >50 interactions, simplify

**Technical Specs:** See [PHASE4_CONFLICT_RESOLUTION_SPEC.md](./roadmap/PHASE4_CONFLICT_RESOLUTION_SPEC.md)

---

### Phase 5: Cross-Thread Relevance (Weeks 9-10)

**Objective:** Learn which facts to inject into which contexts

**Implementation:**

1. **Fact Usage Tracking**
   - Monitor: Which injected facts influenced response
   - Use LLM attention weights or explicit tagging
   - Dataset: (thread_context, fact, was_used)

2. **Relevance Scorer**
   - Input: (current_thread_context, historical_fact)
   - Output: Relevance score (0-1)
   - Model: Neural net or gradient boosting

3. **Context-Aware Retrieval**
   - Work thread → boost job-related facts
   - Personal thread → boost hobby/preference facts
   - Filter facts by relevance >0.5 before injection

**Deliverables:**
- ✅ Fact usage tracking system
- ✅ Relevance scoring model
- ✅ Context-aware retrieval pipeline
- ✅ A/B test: With vs without filtering
- ✅ Precision/recall metrics

**Success Criteria:**
- Precision: >80% of injected facts used
- Recall: >90% of relevant facts retrieved
- Response quality improved (user ratings)
- Latency unchanged (<10ms overhead)

**Failure Checkpoint:**
- If precision <60%, need better features
- If recall <70%, lower relevance threshold
- If latency increases >20ms, optimize model

**Technical Specs:** See [PHASE5_RELEVANCE_SCORING_SPEC.md](./roadmap/PHASE5_RELEVANCE_SCORING_SPEC.md)

---

### Phase 6: Fact Staleness Prediction (Weeks 11-12)

**Objective:** Auto-detect when facts need revalidation

**Implementation:**

1. **Temporal Training Data**
   - Collect: Facts that were corrected after T days
   - Label: Time-to-correction for each fact type
   - Dataset: (fact_type, age_days, update_freq) → staleness

2. **Decay Model**
   - Predict: Probability fact is stale (0-1)
   - Volatile facts (favorite_color): High decay
   - Stable facts (name): Low decay

3. **Proactive Revalidation**
   - When staleness >0.8, prompt: "Is X still true?"
   - Refresh confidence on user confirmation
   - Log revalidation attempts for metrics

**Deliverables:**
- ✅ Temporal dataset generation
- ✅ Staleness prediction model
- ✅ Proactive revalidation prompts
- ✅ Confidence decay system
- ✅ Revalidation effectiveness metrics

**Success Criteria:**
- Staleness prediction accuracy >75%
- Revalidation prompts confirmed >60%
- Reduced incorrect responses by 20%
- Proactive prompts <5% of interactions

**Failure Checkpoint:**
- If accuracy <60%, need more temporal features
- If prompts annoying (acceptance <40%), reduce frequency
- If no improvement in response quality, deprioritize

**Technical Specs:** See [PHASE6_STALENESS_PREDICTION_SPEC.md](./roadmap/PHASE6_STALENESS_PREDICTION_SPEC.md)

---

## Hybrid Integration Plan

### Shared Infrastructure

Both tracks leverage:

1. **Common Data Layer**
   - Postgres cluster (enterprise track)
   - Shared by training pipeline (learning track)

2. **Message Queue**
   - Enterprise: Contradiction detection jobs
   - Learning: Training trigger events

3. **Background Workers**
   - Enterprise: Async detection, export
   - Learning: ML training, model evaluation

4. **Monitoring Stack**
   - Prometheus + Grafana
   - Shared dashboards for both tracks
   - Alert on anomalies

### Integration Points

**Week 4:** Learning track starts using enterprise Postgres  
**Week 7:** Enterprise track uses learned models from learning track  
**Week 10:** Full integration - learned models in production for enterprise

### Dependency Management

```
Enterprise Track          Learning Track
    Phase 1    ──────┐        Phase 1
    Phase 2          │        Phase 2
    Phase 3          └──►     Phase 3 (uses enterprise data)
    Phase 4    ◄──┬──────     Phase 4 (provides learned models)
                   └──────     Phase 5
                   └──────     Phase 6
```

**Key:** Enterprise provides data, Learning provides intelligence

---

## Milestones & Deliverables

### Month 1 (Weeks 1-4)

**Enterprise Track:**
- ✅ Postgres migration complete
- ✅ Async detection pipeline live
- ✅ Telemetry dashboard deployed
- ✅ Soft disclosure A/B test running

**Learning Track:**
- ✅ Data collection infrastructure live
- ✅ Feedback API deployed
- ✅ Query→Slot classifier trained
- ✅ A/B test: Learned vs rule-based

**Milestone:** Data flowing, initial ML model in testing

---

### Month 2 (Weeks 5-8)

**Enterprise Track:**
- ✅ Full ledger deployed for enterprise tier
- ✅ Ledger API endpoints live
- ✅ Admin dashboard usable
- ✅ AI-assisted resolution in beta

**Learning Track:**
- ✅ Fact extraction fine-tuning complete
- ✅ Confidence-based extraction live
- ✅ Conflict resolution policy learned
- ✅ Adaptive resolution in testing

**Milestone:** Enterprise features ready, ML showing improvements

---

### Month 3 (Weeks 9-12)

**Enterprise Track:**
- ✅ AI-assisted resolution in production
- ✅ Auto-resolution for low-risk cases
- ✅ Full enterprise tier launched

**Learning Track:**
- ✅ Cross-thread relevance deployed
- ✅ Staleness prediction live
- ✅ Full active learning loop closed

**Milestone:** Both tracks in production, self-improving system live

---

## Success Criteria

### Enterprise Track Success

**Performance:**
- ✅ API latency <100ms p95 (vs 50ms today)
- ✅ Support 10K concurrent users
- ✅ Contradiction detection within 5 seconds
- ✅ Zero data loss during migration

**Quality:**
- ✅ Zero-violation invariant maintained
- ✅ False positive rate <5%
- ✅ User trust metrics stable or improved
- ✅ Enterprise customers adopt full ledger

**Business:**
- ✅ 5+ enterprise customers paying for ledger tier
- ✅ <2% churn rate post-migration
- ✅ Positive ROI on infrastructure investment

### Learning Track Success

**Accuracy:**
- ✅ Query→Slot: >90% accuracy
- ✅ Fact extraction: <5% user correction rate
- ✅ Conflict resolution: >85% auto-accuracy
- ✅ Relevance scoring: >80% precision

**User Experience:**
- ✅ Response quality improved (ratings +10%)
- ✅ User friction reduced (prompts -30%)
- ✅ Trust metrics stable or improved

**Technical:**
- ✅ Models train in <10 minutes
- ✅ Inference adds <20ms latency
- ✅ Hot-reload works without restart
- ✅ Training pipeline runs automatically

---

## Failure Checkpoints

### Critical Failures (Abort Immediately)

1. **Data Corruption**
   - If migration causes data loss >0.1%
   - Action: Rollback to SQLite, investigate root cause

2. **Invariant Violations**
   - If reintroduction invariant violated in production
   - Action: Emergency rollback, fix before retry

3. **Severe Performance Degradation**
   - If API latency increases >5x
   - Action: Abort phase, optimize before continuing

4. **User Revolt**
   - If trust metrics drop >30%
   - Action: Pause all changes, gather feedback

### Warning Thresholds (Pause & Fix)

1. **High Error Rate**
   - If error rate >5% in any phase
   - Action: Pause rollout, debug, resume

2. **Poor ML Accuracy**
   - If any model <70% accuracy
   - Action: Retrain with more data or better features

3. **Cost Overrun**
   - If infrastructure cost >3x projection
   - Action: Optimize or reduce scope

### Regular Reviews

**Weekly:** Team standup, metrics review  
**Bi-weekly:** Stakeholder update, go/no-go decision  
**Monthly:** Retrospective, adjust roadmap

---

## Resource Requirements

### Engineering Team

**Minimum:**
- 1x Backend Engineer (enterprise track)
- 1x ML Engineer (learning track)
- 0.5x DevOps (infrastructure)

**Optimal:**
- 2x Backend Engineers (parallel development)
- 1x ML Engineer + 0.5x ML Researcher
- 1x DevOps Engineer
- 0.5x Product Manager (prioritization)

### Infrastructure

**Month 1-2 (Testing):**
- Postgres instance: $50/month (dev tier)
- Redis cache: $20/month
- Message queue: $30/month
- Total: ~$100/month

**Month 3+ (Production):**
- Postgres cluster: $500/month (multi-AZ)
- Redis cluster: $200/month
- Message queue: $100/month
- Load balancer: $50/month
- Monitoring: $100/month
- Total: ~$950/month

**Scaling (10K users):**
- Estimated: $2000-3000/month
- Break-even: 100 enterprise customers @ $30/month

### Time Investment

**Total:** ~480 engineer-hours (3 engineers × 4 hours/day × 12 weeks)

**Breakdown:**
- Enterprise Track: 200 hours
- Learning Track: 200 hours
- Integration & Testing: 80 hours

---

## Risk Assessment

### High Risk

**1. Postgres Migration**
- **Risk:** Data loss or corruption
- **Mitigation:** Extensive testing, backup/restore procedures, gradual rollout
- **Contingency:** Keep SQLite fallback for 30 days post-migration

**2. Performance Regression**
- **Risk:** Latency increases unacceptably
- **Mitigation:** Load testing, profiling, caching strategy
- **Contingency:** Feature flags to disable expensive features

### Medium Risk

**3. ML Model Accuracy**
- **Risk:** Models don't improve over baseline
- **Mitigation:** Start with simple models, collect more data, iterate
- **Contingency:** Keep rule-based systems as fallback

**4. User Confusion**
- **Risk:** New features confuse or annoy users
- **Mitigation:** A/B testing, user research, gradual rollout
- **Contingency:** Feature flags to disable per-user

### Low Risk

**5. Infrastructure Cost**
- **Risk:** Costs exceed budget
- **Mitigation:** Monitor usage, optimize queries, use reserved instances
- **Contingency:** Scale down features or tier pricing

**6. Team Velocity**
- **Risk:** Development takes longer than planned
- **Mitigation:** Buffer time in estimates, prioritize ruthlessly
- **Contingency:** Cut lower-priority features

---

## Next Steps

### Immediate (This Week)

1. **Review & Approve** this roadmap
2. **Create GitHub project** with milestones
3. **Assign technical leads** for each track
4. **Set up infrastructure** (Postgres instance, message queue)

### Week 1 Tasks

1. **Enterprise Track:** Start Postgres migration script
2. **Learning Track:** Implement data collection logger
3. **DevOps:** Set up CI/CD for roadmap phases
4. **Documentation:** Create detailed phase specs (see references below)

### Review Cadence

- **Weekly:** Team standup (progress, blockers)
- **Bi-weekly:** Stakeholder demo (show working features)
- **Monthly:** Roadmap review (adjust based on learnings)

---

## Related Documents

**Phase Specifications:**
- [PHASE1_SILENT_DETECTION_SPEC.md](./roadmap/PHASE1_SILENT_DETECTION_SPEC.md) - Enterprise Phase 1
- [PHASE2_SOFT_DISCLOSURE_SPEC.md](./roadmap/PHASE2_SOFT_DISCLOSURE_SPEC.md) - Enterprise Phase 2
- [PHASE3_FULL_LEDGER_SPEC.md](./roadmap/PHASE3_FULL_LEDGER_SPEC.md) - Enterprise Phase 3
- [PHASE4_AI_RESOLUTION_SPEC.md](./roadmap/PHASE4_AI_RESOLUTION_SPEC.md) - Enterprise Phase 4
- [PHASE1_DATA_COLLECTION_SPEC.md](./roadmap/PHASE1_DATA_COLLECTION_SPEC.md) - Learning Phase 1
- [PHASE2_SLOT_LEARNING_SPEC.md](./roadmap/PHASE2_SLOT_LEARNING_SPEC.md) - Learning Phase 2
- [PHASE3_EXTRACTION_TUNING_SPEC.md](./roadmap/PHASE3_EXTRACTION_TUNING_SPEC.md) - Learning Phase 3
- [PHASE4_CONFLICT_RESOLUTION_SPEC.md](./roadmap/PHASE4_CONFLICT_RESOLUTION_SPEC.md) - Learning Phase 4
- [PHASE5_RELEVANCE_SCORING_SPEC.md](./roadmap/PHASE5_RELEVANCE_SCORING_SPEC.md) - Learning Phase 5
- [PHASE6_STALENESS_PREDICTION_SPEC.md](./roadmap/PHASE6_STALENESS_PREDICTION_SPEC.md) - Learning Phase 6

**Technical Designs:**
- [API_DESIGN.md](./roadmap/API_DESIGN.md) - API endpoints and schemas
- [DATABASE_SCHEMA.md](./roadmap/DATABASE_SCHEMA.md) - Postgres schema design
- [ARCHITECTURE.md](./roadmap/ARCHITECTURE.md) - System architecture diagrams
- [DEPLOYMENT.md](./roadmap/DEPLOYMENT.md) - Deployment and ops guide

---

**Status:** 📋 Planning Phase - Awaiting Approval  
**Next Review:** After stakeholder feedback  
**Version:** 1.0 (2026-01-21)

*This roadmap is a living document. It will be updated based on learnings, feedback, and changing priorities.*
