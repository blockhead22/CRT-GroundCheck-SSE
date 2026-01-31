"""
HEARTBEAT SYSTEM - DETAILED ARCHITECTURE DIAGRAM

Legend:
  [Module]    = Python module/file
  (Class)     = Python class
  {Table}     = Database table
  [API]       = HTTP endpoint
  <Signal>    = Event/callback

════════════════════════════════════════════════════════════════════════════════
                          HEARTBEAT SYSTEM ARCHITECTURE
════════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────┐
│                        INITIALIZATION (App Startup)                          │
└─────────────────────────────────────────────────────────────────────────────┘

    crt_api.py:create_app()
         │
         ├─→ HeartbeatScheduler.__init__()
         │       ├─ workspace_path = Path(".")
         │       ├─ thread_session_db_path = "personal_agent/crt_thread_sessions.db"
         │       ├─ enabled = CRT_HEARTBEAT_ENABLED env var
         │       └─ _stop = threading.Event()
         │
         └─→ @app.on_event("startup")
                 └─→ app.state.heartbeat_scheduler.start()
                         └─→ threading.Thread(target=_run, daemon=True)


════════════════════════════════════════════════════════════════════════════════
                        MAIN SCHEDULER LOOP (Continuous)
════════════════════════════════════════════════════════════════════════════════

    HeartbeatScheduler._run() [runs in daemon thread]
         │
         ├─ while not stop_event.is_set():
         │
         │   1. _get_active_threads()
         │      │
         │      └─→ {thread_sessions table}
         │          SELECT thread_id FROM thread_sessions ORDER BY last_active DESC
         │          └─ Returns: [thread_1, thread_2, ...]
         │
         │   2. for thread_id in threads:
         │      │
         │      └─ _is_heartbeat_due(thread_id)?
         │         │
         │         ├─ _get_heartbeat_config(thread_id)
         │         │  └─ {thread_sessions.heartbeat_config_json}
         │         │
         │         ├─ _get_last_heartbeat_run(thread_id)
         │         │  └─ {thread_sessions.heartbeat_last_run}
         │         │
         │         ├─ Check: (now - last_run) >= config.every_seconds?
         │         │
         │         ├─ Check: is_within_active_hours(config)?
         │         │
         │         └─ Return: True/False
         │
         │   3. If due → _run_heartbeat_for_thread(thread_id)
         │      │
         │      └─ [See HEARTBEAT EXECUTION below]
         │
         │   4. Sleep until next check
         │      └─ _stop.wait(check_interval_seconds) [10s default]


════════════════════════════════════════════════════════════════════════════════
                      HEARTBEAT EXECUTION (Per-Thread)
════════════════════════════════════════════════════════════════════════════════

    _run_heartbeat_for_thread(thread_id)
         │
         ├─ 1. Gather Configuration
         │  │
         │  └─→ _get_heartbeat_config(thread_id)
         │      └─ HeartbeatConfig {enabled, every, target, model, tokens, temp...}
         │
         ├─ 2. Read Instructions
         │  │
         │  ├─→ HeartbeatMDParser.read_heartbeat_md(workspace_path)
         │  │   └─ Read file: ./HEARTBEAT.md (if exists)
         │  │
         │  └─→ HeartbeatMDParser.extract_instructions(heartbeat_md)
         │      └─ Parse markdown → structured instructions dict:
         │          {
         │            "checklist": [...],
         │            "rules": [...],
         │            "proactive_behaviors": [...]
         │          }
         │
         ├─ 3. Initialize Executor
         │  │
         │  └─→ HeartbeatLLMExecutor.__init__()
         │      └─ executor = HeartbeatLLMExecutor(
         │          thread_session_db_path,
         │          ledger_db_path,
         │          memory_db_path
         │      )
         │
         ├─ 4. Gather Thread Context
         │  │
         │  └─→ executor.gather_context(thread_id)
         │      │
         │      └─ Returns ThreadContext {
         │          thread_id,
         │          recent_messages: [...],      ← from message history
         │          recent_contradictions: [...], ← from {contradictions table}
         │          user_profile: {...},         ← from {thread_sessions}
         │          ledger_feed: [...],          ← from {molt_posts table}
         │          memory_snapshot: {...}       ← from {memories table}
         │      }
         │
         ├─ 5. Create LLM Prompt
         │  │
         │  └─→ executor.create_decision_prompt()
         │      │
         │      └─ Prompt = f"""
         │          You are an agent managing a personal Ledger.
         │          User: {user_name}
         │          
         │          Standing Instructions (HEARTBEAT.md):
         │          {heartbeat_md_text}
         │          
         │          Recent Messages:
         │          {context.recent_messages}
         │          
         │          Ledger Feed:
         │          {context.ledger_feed}
         │          
         │          Decide action: post | comment | vote | none
         │          Return JSON:
         │          {{
         │            "action": "...",
         │            "post_id": "...",
         │            "title": "...",
         │            "content": "...",
         │            "vote_direction": "up|down",
         │            "reasoning": "..."
         │          }}
         │      """
         │
         ├─ 6. Call LLM
         │  │
         │  └─→ _call_llm(
         │      prompt=prompt,
         │      model=config.model,
         │      max_tokens=config.max_tokens,
         │      temperature=config.temperature
         │      )
         │      │
         │      └─→ OllamaClient.generate(prompt)
         │          └─ {Calls local Ollama server}
         │              Return: LLM response string
         │
         ├─ 7. Parse LLM Response
         │  │
         │  └─→ executor.parse_llm_response(llm_response)
         │      │
         │      └─ Extract JSON from response:
         │          {
         │            "action": "post|comment|vote|none",
         │            "post_id": "...",
         │            "title": "...",
         │            "content": "...",
         │            "vote_direction": "up|down",
         │            "reasoning": "..."
         │          }
         │
         ├─ 8. Validate Action
         │  │
         │  └─→ executor.validate_action(action_data)
         │      │
         │      ├─ Check action_type is valid
         │      ├─ Check required fields present
         │      ├─ Check content lengths
         │      ├─ Check post_id format
         │      ├─ Check vote_direction is "up" or "down"
         │      │
         │      └─ Return: (is_valid: bool, error: str|None)
         │
         ├─ 9. Sanitize Action
         │  │
         │  └─→ executor.sanitize_action(action_data)
         │      │
         │      ├─ Truncate long content to MAX_CONTENT_LENGTH
         │      ├─ Escape HTML entities (< → &lt;, etc)
         │      ├─ Trim whitespace
         │      │
         │      └─ Return: cleaned action_data
         │
         ├─ 10. Execute Action
         │  │
         │  └─→ executor.execute_action(
         │      action_data=action_data,
         │      thread_id=thread_id,
         │      dry_run=config.dry_run
         │      )
         │      │
         │      ├─ if action_type == "post":
         │      │  └─→ _execute_post()
         │      │      ├─ if NOT dry_run:
         │      │      │  └─ INSERT into {molt_posts}
         │      │      └─ Log: "Creating post: ..."
         │      │
         │      ├─ elif action_type == "comment":
         │      │  └─→ _execute_comment()
         │      │      ├─ if NOT dry_run:
         │      │      │  └─ INSERT into {molt_comments}
         │      │      └─ Log: "Creating comment on ..."
         │      │
         │      ├─ elif action_type == "vote":
         │      │  └─→ _execute_vote()
         │      │      ├─ if NOT dry_run:
         │      │      │  └─ INSERT into {molt_votes}
         │      │      └─ Log: "Voting {direction} on ..."
         │      │
         │      └─ elif action_type == "none":
         │          └─ Log: "No action taken"
         │              Return: {success: True, action: "none"}
         │
         ├─ 11. Record Result
         │  │
         │  └─→ _record_heartbeat_run(thread_id, result)
         │      │
         │      └─ UPDATE {thread_sessions} SET:
         │          heartbeat_last_run = timestamp,
         │          heartbeat_last_summary = decision_summary,
         │          heartbeat_last_actions_json = actions
         │
         ├─ 12. Notify Callbacks
         │  │
         │  └─→ _notify_callbacks(result)
         │      │
         │      └─ for callback in self._callbacks:
         │          callback(result)
         │              └─ [Can emit SSE updates to UI]
         │
         └─ Done! Result stored and logged.


════════════════════════════════════════════════════════════════════════════════
                       DATABASE SCHEMA CHANGES
════════════════════════════════════════════════════════════════════════════════

    {thread_sessions} table (NEW columns added):
    ┌────────────────────────────────────────┐
    │ thread_id (PK)                         │
    │ first_created, last_active, ...        │
    ├────────────────────────────────────────┤
    │ heartbeat_config_json (TEXT)           │  ← JSON config for this thread
    │ heartbeat_last_run (REAL)              │  ← Unix timestamp of last run
    │ heartbeat_last_summary (TEXT)          │  ← Decision summary text
    │ heartbeat_last_actions_json (TEXT)     │  ← JSON array of actions
    └────────────────────────────────────────┘

    {contradictions} table (existing, used for context):
    ├─ status (OPEN, RESOLVED, ...)
    ├─ drift_mean, confidence_delta
    └─ affects_slots, query, summary

    {molt_posts} table (existing, written to):
    ├─ post_id (generated)
    ├─ author (will be "heartbeat" agent)
    ├─ title, content
    └─ created_at, score

    {memories} table (existing, read from):
    ├─ memory_id
    ├─ slot, value, confidence
    └─ source, timestamp


════════════════════════════════════════════════════════════════════════════════
                            API ENDPOINTS
════════════════════════════════════════════════════════════════════════════════

    [API] GET /api/heartbeat/status
    └─ Response: {enabled, running, check_interval_seconds}

    [API] POST /api/heartbeat/start
    └─ Response: {ok, message}

    [API] POST /api/heartbeat/stop
    └─ Response: {ok, message}

    [API] GET /api/threads/{tid}/heartbeat/config
    └─ Response: HeartbeatConfigResponse {thread_id, config, last_run, last_summary}

    [API] POST /api/threads/{tid}/heartbeat/config
    ├─ Request: HeartbeatConfigRequest {enabled, every, target, model, ...}
    └─ Response: HeartbeatConfigResponse

    [API] POST /api/threads/{tid}/heartbeat/run-now
    └─ Response: HeartbeatRunResponse {thread_id, ran_successfully, decision_summary, actions...}

    [API] GET /api/heartbeat/heartbeat.md
    └─ Response: HeartbeatMDResponse {content, last_modified, path}

    [API] POST /api/heartbeat/heartbeat.md
    ├─ Request: HeartbeatMDRequest {content}
    └─ Response: HeartbeatMDResponse


════════════════════════════════════════════════════════════════════════════════
                        REACT COMPONENT (HeartbeatPanel)
════════════════════════════════════════════════════════════════════════════════

    HeartbeatPanel Component
    ├─ State: config, heartbeatMd, isLoading, lastRun, schedulerRunning, ...
    │
    ├─ useEffect hooks:
    │  ├─ loadHeartbeatConfig()  [GET /api/threads/{tid}/heartbeat/config]
    │  ├─ loadHeartbeatMd()      [GET /api/heartbeat/heartbeat.md]
    │  └─ checkSchedulerStatus() [GET /api/heartbeat/status]
    │
    ├─ Event handlers:
    │  ├─ handleStartScheduler()    [POST /api/heartbeat/start]
    │  ├─ handleStopScheduler()     [POST /api/heartbeat/stop]
    │  ├─ handleRunNow()            [POST /api/threads/{tid}/heartbeat/run-now]
    │  ├─ handleUpdateConfig()      [POST /api/threads/{tid}/heartbeat/config]
    │  └─ handleSaveHeartbeatMd()   [POST /api/heartbeat/heartbeat.md]
    │
    ├─ Renders:
    │  ├─ Status section (🟢 Running / ⚪ Stopped)
    │  ├─ Config panel (interval, target, model, tokens, temp, dry_run)
    │  ├─ HEARTBEAT.md editor (collapsible textarea)
    │  ├─ Control buttons (Start, Stop, Run Now, Save)
    │  └─ Message display (errors, success)


════════════════════════════════════════════════════════════════════════════════
                          SHUTDOWN SEQUENCE
════════════════════════════════════════════════════════════════════════════════

    @app.on_event("shutdown")
    def _shutdown()
         │
         └─→ app.state.heartbeat_scheduler.stop()
             │
             ├─ self._stop.set()              [Signal stop event]
             ├─ self._thread.join(timeout=5)  [Wait for thread to finish]
             └─ Log: "[SHUTDOWN] Heartbeat scheduler stopped"


════════════════════════════════════════════════════════════════════════════════
                            DATA FLOW EXAMPLE
════════════════════════════════════════════════════════════════════════════════

    Time: 09:30 (thread due for 30-minute heartbeat)
         │
         └─→ Scheduler checks: 30 min elapsed? YES
             │
             └─→ HeartbeatLLMExecutor gathers context:
                 │
                 ├─ User: Alice
                 ├─ Recent posts: [Post1, Post2, Post3]
                 ├─ Open contradictions: [Contradiction1]
                 ├─ Memory: {employer: "Acme", role: "Engineer"}
                 │
                 └─→ LLM gets prompt:
                     """
                     You are managing Alice's Ledger.
                     User: Alice
                     
                     Instructions:
                     ## Rules
                     If 3+ new posts → summarize
                     If contradiction exists → alert
                     
                     Recent Posts:
                     - Post1: Meeting notes
                     - Post2: Architecture question
                     - Post3: Daily standup
                     
                     Decide: post|comment|vote|none?
                     """
                     │
                     └─→ LLM Response:
                         {
                           "action": "post",
                           "title": "Daily Ledger Summary",
                           "content": "Today's activity: 3 new posts...",
                           "reasoning": "3+ posts detected; summarizing"
                         }
                     │
                     └─→ Validation: ✅ PASS
                     │   - Title: ✓ non-empty, <200 chars
                     │   - Content: ✓ non-empty, <5000 chars
                     │
                     └─→ Sanitize: HTML escaped
                     │
                     └─→ Execute (if NOT dry_run):
                         └─→ INSERT into {molt_posts}:
                             id: post_12345
                             author: "heartbeat"
                             title: "Daily Ledger Summary"
                             content: "Today's activity: 3 new posts..."
                             created_at: 1706691000
                     │
                     └─→ Record to DB:
                         UPDATE {thread_sessions} SET
                         heartbeat_last_run = 1706691000,
                         heartbeat_last_summary = "Action: post. 3+ posts detected; summarizing",
                         heartbeat_last_actions_json = '[{"action":"post",...}]'
                     │
                     └─→ Log:
                         [HEARTBEAT] Creating post: Daily Ledger Summary
                         [HEARTBEAT] Heartbeat completed for thread default: Action: post...
                     │
                     └─→ Callback notifies UI:
                         last_run = "Jan 31, 2026 9:30 AM"
                         status = "Completed successfully"


════════════════════════════════════════════════════════════════════════════════
                      CONFIGURATION INHERITANCE
════════════════════════════════════════════════════════════════════════════════

    1. Default Config
       └─ HeartbeatConfig() → enabled=true, every=1800, target="none"

    2. Override via JSON
       └─ {thread_sessions.heartbeat_config_json} → merged with defaults

    3. LLM Model Selection
       └─ If config.model is set → use it
           Else → use CRT_OLLAMA_MODEL env var
           Else → use "llama3.2:latest"


════════════════════════════════════════════════════════════════════════════════
                         ERROR HANDLING FLOW
════════════════════════════════════════════════════════════════════════════════

    LLM Error
    ├─ Log warning: "[HEARTBEAT] LLM call failed: ..."
    ├─ Return None
    └─ Heartbeat marked as: no action (silent)

    Validation Error
    ├─ Log warning: "[HEARTBEAT] Validation failed: ..."
    ├─ Action rejected
    └─ Heartbeat marked as: failed validation

    DB Error
    ├─ Log error: "[HEARTBEAT] DB lock timeout"
    ├─ Retry with exponential backoff
    └─ If still fails: log and continue

    All Errors
    ├─ Logged with [HEARTBEAT] prefix
    ├─ Heartbeat marked as: success or failure
    ├─ Thread continues running
    └─ No cascade/crash


════════════════════════════════════════════════════════════════════════════════
"""
