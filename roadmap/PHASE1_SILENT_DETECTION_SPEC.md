# Phase 1: Silent Detection - Technical Specification

**Track:** Enterprise Adoption  
**Duration:** Weeks 1-3  
**Status:** Planning  
**Version:** 1.0

---

## Objective

Implement async contradiction detection without impacting user-facing API latency or behavior.

**Success Metric:** Detect 95% of contradictions within 5 seconds, with <10% false positive rate, while maintaining <100ms API latency.

---

## Architecture

### Current Flow (v0.9-beta)

```
User Request → FastAPI → CRTRag.chat()
                            ↓
                    Detect Contradictions (sync, ~50ms)
                            ↓
                    Generate Response
                            ↓
User Response ← Add Flags ← Return
```

**Problem:** Contradiction detection adds 50ms to every request

---

### Target Flow (Phase 1)

```
User Request → FastAPI → CRTRag.chat()
                            ↓
                    Generate Response (no detection)
                            ↓
User Response ← Return     ↓ (async, non-blocking)
                            ↓
                    Enqueue Detection Job
                            ↓
                    Message Queue (RabbitMQ)
                            ↓
                    Worker Process
                            ↓
                    Run Detection
                            ↓
                    Log to `contradiction_detection_log`
```

**Benefit:** API latency unchanged (~50ms), detection happens in background

---

## Components

### 1. Database Migration

#### Current: SQLite

**Files:**
- `personal_agent/crt_memory.db`
- `personal_agent/crt_ledger.db`

**Limitations:**
- Single-writer (no concurrent writes)
- Max ~100K records before slowdown
- No read replicas
- File locking issues

#### Target: PostgreSQL

**Schema:**

```sql
-- Memories table (migrated from SQLite)
CREATE TABLE memories (
    memory_id VARCHAR(64) PRIMARY KEY,
    text TEXT NOT NULL,
    embedding VECTOR(384),  -- pgvector extension
    timestamp DOUBLE PRECISION NOT NULL,
    confidence DOUBLE PRECISION,
    trust DOUBLE PRECISION,
    source VARCHAR(32),
    sse_mode VARCHAR(16),
    thread_id VARCHAR(64),
    session_id VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_memories_thread_id ON memories(thread_id);
CREATE INDEX idx_memories_timestamp ON memories(timestamp DESC);
CREATE INDEX idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops);

-- Ledger table (migrated from SQLite)
CREATE TABLE contradiction_ledger (
    ledger_id VARCHAR(64) PRIMARY KEY,
    timestamp DOUBLE PRECISION NOT NULL,
    status VARCHAR(16),
    contradiction_type VARCHAR(32),
    drift_mean DOUBLE PRECISION,
    drift_max DOUBLE PRECISION,
    memory_id_a VARCHAR(64) REFERENCES memories(memory_id),
    memory_id_b VARCHAR(64) REFERENCES memories(memory_id),
    thread_id VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ledger_status ON contradiction_ledger(status);
CREATE INDEX idx_ledger_thread_id ON contradiction_ledger(thread_id);

-- NEW: Detection log (for telemetry)
CREATE TABLE contradiction_detection_log (
    log_id SERIAL PRIMARY KEY,
    job_id VARCHAR(64) UNIQUE NOT NULL,
    memory_id_new VARCHAR(64) REFERENCES memories(memory_id),
    potential_conflicts JSONB,  -- Array of memory IDs checked
    contradictions_found JSONB,  -- Array of detected contradictions
    detection_latency_ms INTEGER,
    false_positive_score DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_detection_log_created_at ON contradiction_detection_log(created_at DESC);
CREATE INDEX idx_detection_log_job_id ON contradiction_detection_log(job_id);
```

**Migration Script:**

```python
# tools/migrate_sqlite_to_postgres.py

import sqlite3
import psycopg2
from psycopg2.extras import execute_batch
import json

def migrate_memories(sqlite_conn, pg_conn):
    """Migrate memories table from SQLite to Postgres."""
    sqlite_cur = sqlite_conn.cursor()
    pg_cur = pg_conn.cursor()
    
    # Read from SQLite
    sqlite_cur.execute("SELECT * FROM memories")
    rows = sqlite_cur.fetchall()
    columns = [desc[0] for desc in sqlite_cur.description]
    
    # Batch insert to Postgres
    insert_sql = f"""
        INSERT INTO memories ({','.join(columns)})
        VALUES ({','.join(['%s'] * len(columns))})
        ON CONFLICT (memory_id) DO NOTHING
    """
    
    execute_batch(pg_cur, insert_sql, rows, page_size=1000)
    pg_conn.commit()
    
    print(f"Migrated {len(rows)} memories")

def migrate_ledger(sqlite_conn, pg_conn):
    """Migrate contradiction ledger."""
    # Similar to above
    pass

def verify_migration(sqlite_conn, pg_conn):
    """Verify all data migrated correctly."""
    sqlite_count = sqlite_conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    pg_count = pg_conn.cursor().execute("SELECT COUNT(*) FROM memories")
    pg_count = pg_conn.cursor().fetchone()[0]
    
    assert sqlite_count == pg_count, f"Count mismatch: {sqlite_count} vs {pg_count}"
    print(f"✓ Verified: {pg_count} memories migrated")

if __name__ == "__main__":
    sqlite_conn = sqlite3.connect("personal_agent/crt_memory.db")
    pg_conn = psycopg2.connect("postgresql://user:pass@localhost/crt_db")
    
    try:
        migrate_memories(sqlite_conn, pg_conn)
        migrate_ledger(sqlite_conn, pg_conn)
        verify_migration(sqlite_conn, pg_conn)
        print("✓ Migration complete")
    except Exception as e:
        pg_conn.rollback()
        print(f"✗ Migration failed: {e}")
        raise
    finally:
        sqlite_conn.close()
        pg_conn.close()
```

**Rollback Plan:**

Keep SQLite files for 30 days post-migration. If issues arise:

```bash
# Restore from backup
cp personal_agent/crt_memory.db.backup personal_agent/crt_memory.db
cp personal_agent/crt_ledger.db.backup personal_agent/crt_ledger.db

# Revert code to use SQLite
git revert <migration_commit>

# Restart service
systemctl restart crt-api
```

---

### 2. Message Queue

**Technology:** RabbitMQ (simple, battle-tested)

**Alternative:** Redis Streams (if already using Redis)

**Queue:** `contradiction_detection_jobs`

**Message Format:**

```json
{
  "job_id": "detect_job_1234567890",
  "memory_id": "mem_abc123",
  "thread_id": "default",
  "priority": "normal",
  "created_at": 1737490400.0
}
```

**Producer:** FastAPI app (after storing new memory)

```python
# In crt_api.py after memory storage

import pika
import json
import uuid

def enqueue_detection_job(memory_id: str, thread_id: str):
    """Add contradiction detection job to queue."""
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='contradiction_detection_jobs', durable=True)
    
    job = {
        "job_id": f"detect_job_{uuid.uuid4().hex}",
        "memory_id": memory_id,
        "thread_id": thread_id,
        "priority": "normal",
        "created_at": time.time()
    }
    
    channel.basic_publish(
        exchange='',
        routing_key='contradiction_detection_jobs',
        body=json.dumps(job),
        properties=pika.BasicProperties(
            delivery_mode=2,  # persistent
        )
    )
    
    connection.close()
```

**Consumer:** Background worker (new service)

```python
# crt_detection_worker.py

import pika
import json
from personal_agent.crt_rag import detect_contradictions
from personal_agent.crt_memory import get_memory_by_id
import psycopg2

def callback(ch, method, properties, body):
    """Process detection job."""
    job = json.loads(body)
    job_id = job['job_id']
    memory_id = job['memory_id']
    
    start_time = time.time()
    
    try:
        # Run detection
        memory = get_memory_by_id(memory_id)
        contradictions = detect_contradictions(memory)
        
        # Log results
        latency_ms = int((time.time() - start_time) * 1000)
        log_detection_result(job_id, memory_id, contradictions, latency_ms)
        
        # Acknowledge job
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"✓ Job {job_id} completed in {latency_ms}ms")
        
    except Exception as e:
        print(f"✗ Job {job_id} failed: {e}")
        # Requeue with delay
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='contradiction_detection_jobs', durable=True)
    channel.basic_qos(prefetch_count=1)  # Process one at a time
    channel.basic_consume(queue='contradiction_detection_jobs', on_message_callback=callback)
    
    print("Worker started. Waiting for jobs...")
    channel.start_consuming()

if __name__ == "__main__":
    main()
```

---

### 3. Telemetry Dashboard

**Technology:** Grafana + Prometheus

**Metrics to Track:**

1. **Detection Performance**
   - Detection latency (p50, p95, p99)
   - Queue depth
   - Jobs processed per second
   - Error rate

2. **Detection Quality**
   - Contradictions detected per hour
   - False positive rate (estimated)
   - Detection coverage (% of memories checked)

3. **System Health**
   - API latency (should be unchanged)
   - Database connection pool usage
   - Worker CPU/memory usage

**Dashboard Panels:**

```yaml
# Grafana dashboard config (simplified)

dashboard:
  title: "CRT Phase 1: Silent Detection"
  panels:
    - title: "API Latency (Should Be Unchanged)"
      query: "histogram_quantile(0.95, rate(api_latency_seconds[5m]))"
      target: "<100ms"
      
    - title: "Detection Queue Depth"
      query: "rabbitmq_queue_messages{queue='contradiction_detection_jobs'}"
      alert: ">1000 (backlog)"
      
    - title: "Detection Latency"
      query: "histogram_quantile(0.95, rate(detection_latency_seconds[5m]))"
      target: "<5s"
      
    - title: "Contradictions Detected (24h)"
      query: "count_over_time(contradiction_detected[24h])"
      
    - title: "False Positive Rate (Estimated)"
      query: "rate(false_positives[1h]) / rate(detections[1h])"
      target: "<10%"
```

**Alerting Rules:**

```yaml
alerts:
  - name: "Detection Queue Backlog"
    condition: "queue_depth > 1000 for 5m"
    action: "Page on-call engineer"
    
  - name: "High False Positive Rate"
    condition: "false_positive_rate > 0.2 for 15m"
    action: "Slack notification"
    
  - name: "API Latency Regression"
    condition: "api_latency_p95 > 150ms for 10m"
    action: "Page on-call (critical)"
```

---

## Implementation Checklist

### Week 1: Setup & Migration

- [ ] Set up Postgres instance (dev environment)
- [ ] Install pgvector extension for embeddings
- [ ] Write migration scripts (SQLite → Postgres)
- [ ] Test migration on copy of production data
- [ ] Set up RabbitMQ locally
- [ ] Create message queue schema
- [ ] Write queue producer (enqueue jobs)
- [ ] Write queue consumer (process jobs)

### Week 2: Integration

- [ ] Modify `crt_api.py` to enqueue detection jobs
- [ ] Ensure API latency unchanged (benchmark before/after)
- [ ] Deploy worker service (systemd or Docker)
- [ ] Set up Prometheus metrics export
- [ ] Create Grafana dashboard
- [ ] Configure alerts

### Week 3: Testing & Tuning

- [ ] Load test: 1000 concurrent users
- [ ] Verify detection coverage (>95%)
- [ ] Measure false positive rate
- [ ] Tune queue concurrency (number of workers)
- [ ] Document operational procedures
- [ ] Create runbook for common issues

---

## Testing Strategy

### Unit Tests

```python
# tests/test_phase1_detection.py

def test_enqueue_detection_job():
    """Test job is enqueued correctly."""
    memory_id = "test_mem_123"
    thread_id = "test_thread"
    
    enqueue_detection_job(memory_id, thread_id)
    
    # Verify job in queue
    queue_depth = get_queue_depth("contradiction_detection_jobs")
    assert queue_depth == 1

def test_detection_worker_processes_job():
    """Test worker processes job and logs result."""
    job = {
        "job_id": "test_job_123",
        "memory_id": "mem_abc",
        "thread_id": "default"
    }
    
    process_detection_job(job)
    
    # Verify logged
    log = get_detection_log("test_job_123")
    assert log is not None
    assert log['job_id'] == "test_job_123"
```

### Integration Tests

```python
def test_end_to_end_async_detection():
    """Test full flow: API → Queue → Worker → Log."""
    # Send chat message
    response = client.post("/api/chat/send", json={
        "thread_id": "test",
        "message": "I work at Amazon"
    })
    
    assert response.status_code == 200
    
    # Wait for async detection (max 10s)
    for _ in range(20):
        logs = get_detection_logs_for_thread("test")
        if logs:
            break
        time.sleep(0.5)
    
    assert len(logs) > 0
    assert logs[0]['contradictions_found'] is not None
```

### Load Tests

```python
# tools/load_test_phase1.py

from locust import HttpUser, task, between

class CRTUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def send_message(self):
        self.client.post("/api/chat/send", json={
            "thread_id": "load_test",
            "message": "I like Python"
        })

# Run: locust -f tools/load_test_phase1.py --users 1000 --spawn-rate 100
```

**Success Criteria:**
- 1000 concurrent users sustained
- API latency <100ms p95
- Zero errors
- Detection queue processes at >100 jobs/second

---

## Deployment Plan

### Development Environment

```bash
# 1. Start Postgres
docker run -d --name crt-postgres \
  -e POSTGRES_PASSWORD=dev_password \
  -e POSTGRES_DB=crt_db \
  -p 5432:5432 \
  postgres:15

# 2. Install pgvector
docker exec crt-postgres psql -U postgres -d crt_db -c "CREATE EXTENSION vector"

# 3. Run migration
python tools/migrate_sqlite_to_postgres.py --config dev

# 4. Start RabbitMQ
docker run -d --name crt-rabbitmq \
  -p 5672:5672 \
  -p 15672:15672 \
  rabbitmq:3-management

# 5. Start worker
python crt_detection_worker.py &

# 6. Start API
uvicorn crt_api:app --reload
```

### Production Deployment (Blue-Green)

**Phase A: Blue (Current SQLite)**
- All traffic on blue
- Green environment with Postgres ready

**Phase B: Migration**
```bash
# 1. Enable read-only mode on blue
curl -X POST http://blue/api/admin/readonly

# 2. Run final migration (catch-up)
python tools/migrate_sqlite_to_postgres.py --production

# 3. Verify migration
python tools/verify_migration.py

# 4. Switch traffic to green (10% canary)
nginx config: 90% blue, 10% green

# 5. Monitor for 1 hour
# Check: API latency, error rate, user complaints

# 6. Full cutover to green
nginx config: 100% green

# 7. Keep blue running for 24 hours (rollback safety)
```

**Rollback Procedure:**
```bash
# If issues detected
nginx config: 100% blue  # Switch traffic back
systemctl stop crt-detection-worker
# Investigate, fix, retry
```

---

## Monitoring & Alerts

### Key Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| API Latency (p95) | <100ms | >150ms for 10min |
| Detection Latency (p95) | <5s | >10s for 5min |
| Queue Depth | <100 | >1000 for 5min |
| False Positive Rate | <10% | >20% for 15min |
| Worker Error Rate | <1% | >5% for 5min |
| Database CPU | <70% | >90% for 5min |

### On-Call Runbook

**Alert: "Detection Queue Backlog"**

1. Check worker status: `systemctl status crt-detection-worker`
2. If not running: `systemctl start crt-detection-worker`
3. If running but slow: Check database CPU, add more workers
4. If persistent: Increase worker concurrency or pause low-priority jobs

**Alert: "High False Positive Rate"**

1. Check recent code changes (was detection algorithm modified?)
2. Review false positive examples in logs
3. If widespread: Disable auto-flagging, manual review only
4. Schedule tuning session with team

---

## Success Criteria (Phase 1 Exit)

- [ ] Postgres migration complete (zero data loss)
- [ ] API latency unchanged (<100ms p95)
- [ ] Detection running async (95% detected within 5 seconds)
- [ ] False positive rate <10%
- [ ] Telemetry dashboard operational
- [ ] Load tested at 1000 concurrent users
- [ ] Runbook documented
- [ ] Team trained on new architecture

---

## Failure Checkpoints

### Checkpoint 1: Migration (End of Week 1)

**Criteria:**
- Migration completes without errors
- Data integrity verified (checksums match)
- Rollback tested and working

**If Failed:**
- Identify root cause (schema mismatch? data corruption?)
- Fix and retry
- If unfixable in 3 days: Abort phase, rethink approach

### Checkpoint 2: Integration (End of Week 2)

**Criteria:**
- Queue integration works
- Worker processes jobs correctly
- API latency unchanged

**If Failed:**
- If latency increased: Profile and optimize
- If queue buggy: Fix or switch to alternative (Redis)
- If unfixable in 3 days: Rollback to SQLite

### Checkpoint 3: Production Ready (End of Week 3)

**Criteria:**
- Load tests pass
- False positive rate acceptable
- Team confident in deployment

**If Failed:**
- Extend timeline by 1 week for tuning
- If still not ready: Deploy to subset of users (10%)
- If critical issues: Delay phase 1, address blockers

---

## Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Data loss during migration | Low | Critical | Extensive testing, backups, verification |
| Performance regression | Medium | High | Load testing, profiling, rollback plan |
| False positive spike | Medium | Medium | Tuning threshold, gradual rollout |
| Worker crashes | Low | Medium | Systemd auto-restart, monitoring |
| Queue backlog | Medium | Low | Auto-scaling workers, alerts |

---

## Estimated Effort

- **Engineering:** 60 hours (2 engineers × 30 hours each)
- **Testing:** 20 hours
- **Documentation:** 10 hours
- **Deployment:** 10 hours
- **Total:** 100 hours (~2.5 weeks)

---

**Status:** 📋 Planning  
**Next:** Awaiting approval to begin implementation  
**Version:** 1.0 (2026-01-21)
