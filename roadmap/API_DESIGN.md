# API Design Specification

**Version:** 1.0  
**Date:** 2026-01-21  
**Status:** Planning

---

## Overview

This document specifies the API changes required for both Enterprise Adoption and Active Learning tracks.

---

## Enterprise Track APIs

### Phase 1: Silent Detection

No API changes (detection happens in background)

---

### Phase 2: Soft Disclosure

#### Metadata Enhancement

**Endpoint:** `POST /api/chat/send` (existing, modified response)

**Enhanced Response Schema:**

```json
{
  "answer": "You work at Amazon.",
  "response_type": "BELIEF",
  "gates_passed": true,
  "metadata": {
    "reintroduced_claims_count": 2,
    "contradiction_flags": [
      {
        "contradiction_id": "contra_1234567890",
        "affected_memory_ids": ["mem_abc123", "mem_def456"],
        "contradiction_type": "value_conflict",
        "severity": "medium",
        "first_detected_at": 1737489600.0,
        "status": "open"
      }
    ],
    "uncertainty_level": "medium",  // NEW
    "confidence_score": 0.75        // NEW
  }
}
```

**New Fields:**
- `contradiction_flags` - Array of contradiction metadata
- `uncertainty_level` - "low" | "medium" | "high"
- `confidence_score` - 0.0 to 1.0

**Backward Compatibility:** Existing clients ignore new fields

---

### Phase 3: Full Ledger

#### List Contradictions

**Endpoint:** `GET /api/contradictions/list`

**Query Parameters:**
- `thread_id` (optional) - Filter by thread
- `status` (optional) - "open" | "resolved" | "dismissed"
- `severity` (optional) - "low" | "medium" | "high"
- `page` (optional, default: 1)
- `per_page` (optional, default: 50, max: 100)

**Response:**

```json
{
  "contradictions": [
    {
      "contradiction_id": "contra_1234567890",
      "created_at": 1737489600.0,
      "updated_at": 1737489700.0,
      "status": "open",
      "severity": "medium",
      "contradiction_type": "value_conflict",
      "involved_memories": [
        {
          "memory_id": "mem_abc123",
          "text": "I work at Microsoft",
          "timestamp": 1737400000.0,
          "trust": 0.8
        },
        {
          "memory_id": "mem_def456",
          "text": "I work at Amazon",
          "timestamp": 1737489600.0,
          "trust": 0.9
        }
      ],
      "suggested_resolution": null,  // Phase 4
      "resolution_history": []
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total_count": 127,
    "total_pages": 3
  }
}
```

---

#### Get Contradiction Details

**Endpoint:** `GET /api/contradictions/{contradiction_id}`

**Response:**

```json
{
  "contradiction_id": "contra_1234567890",
  "created_at": 1737489600.0,
  "updated_at": 1737489700.0,
  "status": "open",
  "severity": "medium",
  "contradiction_type": "value_conflict",
  "involved_memories": [...],
  "context": {
    "thread_id": "work_chat",
    "session_id": "sess_xyz789",
    "trigger_query": "Where do I work?",
    "trigger_timestamp": 1737489600.0
  },
  "provenance": {
    "detected_by": "system",
    "detection_method": "semantic_comparison",
    "confidence": 0.92
  },
  "resolution_suggestions": [],  // Phase 4
  "resolution_history": [],
  "metadata": {
    "affected_responses_count": 5,
    "user_acknowledged": false
  }
}
```

---

#### Export Contradictions

**Endpoint:** `GET /api/contradictions/export`

**Query Parameters:**
- `format` - "json" | "csv"
- `start_date` (optional) - ISO timestamp
- `end_date` (optional) - ISO timestamp
- `status` (optional) - Filter by status

**Response:**
- Content-Type: `application/json` or `text/csv`
- Content-Disposition: `attachment; filename="contradictions_{timestamp}.{format}"`

**CSV Columns:**
```
contradiction_id, created_at, status, severity, type, memory_ids, trigger_query, resolution_status
```

---

### Phase 4: AI-Assisted Resolution

#### Get Resolution Suggestions

**Endpoint:** `POST /api/contradictions/{contradiction_id}/suggest`

**Request:**

```json
{
  "user_context": {
    "recent_messages": ["...", "..."],
    "user_preference": "always_ask"  // or "auto_update", "keep_both"
  }
}
```

**Response:**

```json
{
  "suggestions": [
    {
      "suggestion_id": "sugg_abc123",
      "action": "update_to_newer",
      "confidence": 0.87,
      "reasoning": "User explicitly stated job change ('I work at Amazon now'), suggesting an intentional update rather than a conflict.",
      "preview": {
        "before": "You work at Microsoft.",
        "after": "You work at Amazon.",
        "side_effects": ["Updates 3 related memories about work location"]
      },
      "risk_level": "low",
      "requires_confirmation": false
    },
    {
      "suggestion_id": "sugg_def456",
      "action": "keep_both_with_context",
      "confidence": 0.65,
      "reasoning": "Could be multiple jobs (contractor + employee)",
      "preview": {
        "before": "You work at Microsoft.",
        "after": "You work at Amazon (current) and previously worked at Microsoft.",
        "side_effects": ["Adds temporal context to memories"]
      },
      "risk_level": "low",
      "requires_confirmation": true
    }
  ],
  "recommended": "sugg_abc123"
}
```

---

#### Apply Resolution

**Endpoint:** `POST /api/contradictions/{contradiction_id}/resolve`

**Request:**

```json
{
  "action": "update_to_newer",  // or "keep_both", "dismiss", "ask_user"
  "suggestion_id": "sugg_abc123",  // optional, if using suggestion
  "user_note": "Confirmed: Changed jobs in December"  // optional
}
```

**Response:**

```json
{
  "contradiction_id": "contra_1234567890",
  "status": "resolved",
  "applied_action": "update_to_newer",
  "timestamp": 1737489800.0,
  "affected_memories": ["mem_abc123", "mem_def456"],
  "rollback_id": "rollback_xyz789",  // Can undo within 24 hours
  "summary": "Updated employer from Microsoft to Amazon. Previous memory marked as historical."
}
```

---

#### Rollback Resolution

**Endpoint:** `POST /api/contradictions/{contradiction_id}/rollback`

**Request:**

```json
{
  "rollback_id": "rollback_xyz789",
  "reason": "Accidental resolution"
}
```

**Response:**

```json
{
  "contradiction_id": "contra_1234567890",
  "status": "open",
  "rollback_successful": true,
  "restored_state": "as_of_2026-01-21T12:00:00Z"
}
```

---

## Learning Track APIs

### Phase 1: Data Collection

#### Submit Feedback

**Endpoint:** `POST /api/feedback/thumbs`

**Request:**

```json
{
  "response_id": "resp_abc123",  // From chat response metadata
  "thread_id": "default",
  "vote": "up",  // or "down"
  "comment": "Perfect answer!"  // optional
}
```

**Response:**

```json
{
  "feedback_id": "fb_xyz789",
  "recorded_at": 1737489900.0,
  "thank_you": true
}
```

---

#### Submit Correction

**Endpoint:** `POST /api/feedback/correction`

**Request:**

```json
{
  "response_id": "resp_abc123",
  "thread_id": "default",
  "incorrect_field": "name",
  "incorrect_value": "Alison",
  "correct_value": "Alice",
  "explanation": "You misspelled my name"
}
```

**Response:**

```json
{
  "correction_id": "corr_abc123",
  "recorded_at": 1737490000.0,
  "will_retrain": true,
  "eta_improvement": "within 24 hours"
}
```

---

#### Report Issue

**Endpoint:** `POST /api/feedback/report`

**Request:**

```json
{
  "response_id": "resp_abc123",
  "thread_id": "default",
  "issue_type": "incorrect_information",  // or "inappropriate", "confusing", "other"
  "description": "Said I work at Microsoft, but I never mentioned that",
  "severity": "medium"
}
```

**Response:**

```json
{
  "report_id": "rpt_xyz789",
  "recorded_at": 1737490100.0,
  "escalated": false,
  "ticket_number": null
}
```

---

### Phase 2+: Learning Stats

#### Get Learning Statistics

**Endpoint:** `GET /api/learning/stats`

**Query Parameters:**
- `thread_id` (optional) - Get stats for specific thread
- `period` (optional) - "day" | "week" | "month" | "all"

**Response:**

```json
{
  "period": "week",
  "stats": {
    "total_interactions": 1523,
    "feedback_received": 342,
    "corrections_submitted": 47,
    "current_accuracy": {
      "slot_detection": 0.92,
      "fact_extraction": 0.95,
      "conflict_resolution": 0.87
    },
    "model_versions": {
      "slot_classifier": "v1.3",
      "extraction_model": "v2.1",
      "resolution_policy": "v1.0"
    },
    "last_training": {
      "slot_classifier": 1737400000.0,
      "extraction_model": 1737450000.0,
      "resolution_policy": null  // never trained yet
    },
    "improvement_over_baseline": {
      "user_satisfaction": "+12%",
      "correction_rate": "-8%",
      "response_time": "+5ms"
    }
  }
}
```

---

## Shared: Health & Monitoring

### Health Check

**Endpoint:** `GET /api/health`

**Response:**

```json
{
  "status": "healthy",
  "version": "v1.0.0",
  "components": {
    "database": "healthy",
    "cache": "healthy",
    "message_queue": "healthy",
    "ml_models": "healthy"
  },
  "metrics": {
    "uptime_seconds": 864000,
    "requests_per_second": 45.2,
    "avg_latency_ms": 87,
    "error_rate": 0.003
  }
}
```

---

### Metrics

**Endpoint:** `GET /api/metrics`

**Response:**

```json
{
  "timestamp": 1737490200.0,
  "api": {
    "requests_total": 1523421,
    "requests_per_second": 45.2,
    "latency_p50_ms": 62,
    "latency_p95_ms": 143,
    "latency_p99_ms": 287,
    "error_rate": 0.003
  },
  "memory": {
    "total_memories": 45231,
    "memories_per_user_avg": 23.4,
    "retrieval_latency_ms": 12
  },
  "contradictions": {
    "total_detected": 3421,
    "open": 234,
    "resolved": 3187,
    "false_positive_rate": 0.04
  },
  "learning": {
    "models_trained_today": 3,
    "training_jobs_queued": 0,
    "accuracy_improvements": "+5%"
  }
}
```

---

## Authentication & Authorization

### Current (v0.9-beta)

No authentication (dev/testing only)

### Phase 3+ (Enterprise)

**Authentication:** API keys or OAuth2  
**Authorization:** Role-based access control (RBAC)

**Roles:**
- `user` - Can interact with chat, view own data
- `admin` - Can view contradictions, export data
- `super_admin` - Can resolve contradictions, manage users

**Headers:**

```
Authorization: Bearer <api_key_or_token>
X-User-ID: user_abc123  // optional, for multi-user systems
```

---

## Rate Limiting

### Phase 1-2 (Development)

No rate limiting

### Phase 3+ (Production)

**Limits:**
- Free tier: 100 requests/minute
- Enterprise tier: 1000 requests/minute
- Burst: 2x limit for 10 seconds

**Response Headers:**

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1737490800
```

**Error Response (429 Too Many Requests):**

```json
{
  "error": "rate_limit_exceeded",
  "message": "You have exceeded your rate limit of 100 requests per minute",
  "retry_after_seconds": 42
}
```

---

## Versioning

**Strategy:** URL versioning (e.g., `/api/v1/chat/send`)

**Current:** All endpoints are v1 (implicit)

**Future:** When breaking changes needed, create v2 endpoints

**Deprecation:** v1 supported for 12 months after v2 release

---

## Error Handling

### Standard Error Format

```json
{
  "error": "contradiction_not_found",
  "message": "Contradiction with ID 'contra_invalid' does not exist",
  "error_code": 404001,
  "details": {
    "contradiction_id": "contra_invalid",
    "suggestion": "Check the contradiction ID and try again"
  },
  "request_id": "req_xyz789",
  "timestamp": 1737490300.0
}
```

### Error Codes

**400-series (Client Errors):**
- 400000: Bad request (generic)
- 400001: Invalid thread_id
- 400002: Missing required field
- 404001: Contradiction not found
- 404002: Memory not found
- 429000: Rate limit exceeded

**500-series (Server Errors):**
- 500000: Internal server error
- 500001: Database connection failed
- 500002: ML model unavailable
- 500003: Background job failed

---

## WebSocket Support (Future)

### Real-Time Updates

**Endpoint:** `ws://api.example.com/ws/contradictions`

**Messages:**

```json
{
  "type": "contradiction_detected",
  "data": {
    "contradiction_id": "contra_new123",
    "severity": "high",
    "summary": "New conflict detected in employer information"
  }
}
```

**Use Cases:**
- Live dashboard updates
- Real-time contradiction notifications
- Training job progress

---

## Changelog

**v1.0 (2026-01-21):**
- Initial API design
- Enterprise track endpoints (Phases 1-4)
- Learning track endpoints (Phases 1-6)
- Health & monitoring endpoints

---

**Status:** 📋 Draft  
**Next Review:** After roadmap approval  
**Maintainer:** CRT Team
