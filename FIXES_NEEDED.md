# CRT-GroundCheck-SSE: Actionable Fixes List

**Note:** This document lists WHERE to apply fixes. No patches have been applied yet per your request.

---

## 🔴 CRITICAL - Fix Immediately

### 1. Shell Injection Vulnerabilities

**Files to Fix:**
- `personal_agent/rag.py` line 201
- `personal_agent/core.py` line 104
- `personal_agent/researcher.py` line 150

**Current Code:**
```python
os.system(f'python -m sse.cli compress --input "{doc_path}" --out "{sse_output_dir}"')
```

**Replace With:**
```python
import subprocess
subprocess.run([
    'python', '-m', 'sse.cli', 'compress',
    '--input', doc_path,
    '--out', sse_output_dir
], check=True, capture_output=True, text=True)
```

---

### 2. SQLite Concurrency Issues

**Files to Fix:**
- `personal_agent/crt_memory.py` - All database connections
- `personal_agent/crt_ledger.py` - All database connections

**Changes Needed:**
1. Enable WAL mode for all SQLite connections
2. Add busy timeout handling
3. Add retry logic for SQLITE_BUSY errors

**Add to Connection Initialization:**
```python
conn = sqlite3.connect('database.db')
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('PRAGMA busy_timeout=5000')
conn.execute('PRAGMA synchronous=NORMAL')
```

---

## 🟠 HIGH - Fix Before Production

### 3. Transaction Safety

**Files to Fix:**
- `personal_agent/crt_ledger.py` - `record_contradiction()` method
- `personal_agent/crt_memory.py` - `store_memory()` and similar multi-step methods

**Pattern to Apply:**
```python
def record_contradiction(self, ...):
    conn = self.get_connection()
    try:
        conn.execute('BEGIN TRANSACTION')
        # ... multiple write operations ...
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise
```

---

### 4. API Error Handling

**File to Fix:** `crt_api.py`

**Lines to Update:**
- Line 476, 481, 486, 493, 498, 503 - Bare exception handlers
- Line 711-712, 720-721, 740-741, 762-763, 790-791 - Error detail exposure

**Pattern to Apply:**
```python
except ValueError as e:
    logger.error(f"Validation error in endpoint", exc_info=True)
    raise HTTPException(status_code=400, detail="Invalid request")
except Exception as e:
    logger.error(f"Unexpected error in endpoint", exc_info=True)
    raise HTTPException(status_code=500, detail="Internal server error")
```

---

### 5. Security Audit for SQL Injection

**Files to Audit:**
- `personal_agent/crt_memory.py` - All SQL queries
- `personal_agent/crt_ledger.py` - All SQL queries
- `personal_agent/jobs_db.py` - All SQL queries

**Check Pattern:**
```python
# BAD - SQL injection risk
cursor.execute(f"SELECT * FROM memories WHERE id = {user_id}")

# GOOD - Parameterized query
cursor.execute("SELECT * FROM memories WHERE id = ?", (user_id,))
```

---

## 🟡 MEDIUM - Fix for Quality

### 6. Invalid Regex Escape Sequence

**File to Fix:** `personal_agent/resolution_patterns.py`

**Line:** 106 (and any other regex patterns)

**Fix:**
```python
# Change all regex strings to raw strings
pattern = r"\s+"  # Instead of "\s+"
```

---

### 7. Trust Score Documentation

**File to Document:** `personal_agent/crt_memory.py`

**Add:**
- Docstring explaining trust score algorithm
- Mathematical formula for trust decay
- Examples of trust score evolution
- Unit tests for trust score edge cases

---

### 8. SSE Boundary Enforcement

**Files to Refactor:**
- `sse/client.py` - Add stricter boundary checks
- `personal_agent/crt_rag.py` - Move `heuristic_contradiction()` out of SSE calls

**Goal:** Ensure SSE layer only does retrieval, not decision-making

---

### 9. Job Queue Retry Logic

**Files to Fix:**
- `personal_agent/jobs_worker.py` - Add retry mechanism
- `crt_background_worker.py` - Add error handling
- `artifacts/crt_jobs.db` schema - Add retry_count column

**Add:**
```python
def run_job_with_retry(job_id, max_retries=3):
    for attempt in range(max_retries):
        try:
            return run_job(job_id)
        except TransientError:
            if attempt == max_retries - 1:
                move_to_dead_letter_queue(job_id)
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
```

---

## 🟢 LOW - Nice to Have

### 10. Debug Logging Cleanup

**File to Clean:** `personal_agent/crt_rag.py`

**Lines with `[PROFILE_DEBUG]`:**
- Line 2283, 2301, 2345, 2353, 2358, 2360, 2362, 2559, 2568, 2989, 2991, 3589, 4343, 4347, 4363, 4367

**Replace With:**
```python
if logger.isEnabledFor(logging.DEBUG):
    logger.debug(f"Profile debug: {info}")
```

---

### 11. Specific Exception Handling

**File to Fix:** `crt_api.py`

**Lines:** 476, 481, 486, 493, 498, 503

**Pattern:**
```python
# Instead of:
except Exception:
    pass

# Use:
except (KeyError, ValueError) as e:
    logger.warning(f"Expected error: {e}")
except Exception as e:
    logger.error(f"Unexpected error", exc_info=True)
    raise
```

---

### 12. Database Cleanup

**Files to Add:**
- `scripts/vacuum_databases.py` - Regular VACUUM operations
- `scripts/cleanup_test_dbs.py` - Remove old test databases

**Update .gitignore:**
```
# Test databases
personal_agent/*_validation.db
personal_agent/*_test*.db
personal_agent/crt_ledger_phase*.db
personal_agent/crt_memory_phase*.db
personal_agent/crt_ledger_quick*.db
personal_agent/crt_memory_quick*.db
```

---

### 13. Structured Error Codes

**File to Create:** `personal_agent/error_codes.py`

**Example:**
```python
class ErrorCode:
    MEMORY_CONFLICT = 4001
    INVALID_THREAD = 4002
    JOB_FAILED = 5001
    # ... etc
```

**Update:** `crt_api.py` to use error codes in responses

---

### 14. Mock Ollama for Tests

**File to Create:** `tests/conftest.py`

**Add:**
```python
@pytest.fixture
def mock_ollama(monkeypatch):
    def fake_generate(prompt, **kwargs):
        return {"response": "Mocked response"}
    
    monkeypatch.setattr('ollama.generate', fake_generate)
    yield
```

**Update:** All tests to use `@pytest.mark.usefixtures("mock_ollama")`

---

### 15. LLM-Based Fact Extraction

**File to Enhance:** `personal_agent/two_tier_facts.py`

**Add:**
- Option to use LLM for fact extraction instead of regex
- Temporal relationship parsing
- Context-aware entity resolution

---

## Testing Recommendations

### Add Test Categories

**File to Update:** `pytest.ini`

**Add:**
```ini
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    requires_ollama: marks tests requiring Ollama server
    unit: fast unit tests
```

---

## Production Deployment Checklist

**Before deploying to production, add:**

1. Database migrations (Alembic)
2. Monitoring (Prometheus/Grafana)
3. Rate limiting (slowapi)
4. Authentication (OAuth2/JWT)
5. HTTPS/TLS (nginx/caddy)
6. Secrets management (Vault/AWS Secrets Manager)
7. Backup procedures
8. Health checks (`/health`, `/ready`)
9. Graceful shutdown
10. Container configs (Dockerfile, docker-compose.yml)

---

## Summary

**Total Issues Identified:** 15 major items
- **CRITICAL:** 2 (shell injection, SQLite concurrency)
- **HIGH:** 3 (transactions, error handling, SQL audit)
- **MEDIUM:** 4 (regex, trust docs, SSE boundaries, retry logic)
- **LOW:** 6 (logging, exceptions, cleanup, error codes, mocking, fact extraction)

**Estimated Effort:**
- Critical fixes: 2-4 hours
- High priority: 4-8 hours
- Medium priority: 8-12 hours
- Low priority: 4-6 hours

**Total:** Approximately 18-30 hours to address all identified issues.

---

**Note:** This is a comprehensive list. For research use, fixing CRITICAL items (shell injection, basic SQLite improvements) is sufficient. For production, all HIGH and MEDIUM items should be addressed.
