# AgentPanel Component - Testing Guide

## Overview
The AgentPanel component displays agent execution traces in a beautiful, interactive modal. It shows the complete thought → action → observation cycle for each step the agent takes.

## Files Created/Modified

### New Files
- `frontend/src/components/AgentPanel.tsx` - Main component (370 lines)

### Modified Files
- `frontend/src/types.ts` - Added AgentAction, AgentObservation, AgentStep, AgentTrace types
- `frontend/src/lib/api.ts` - Added agent_activated, agent_answer, agent_trace to ChatSendResponse
- `frontend/src/App.tsx` - Added AgentPanel integration with state management
- `frontend/src/components/chat/MessageBubble.tsx` - Added "AGENT TRACE" badge for messages with agent execution
- `frontend/src/components/chat/ChatThreadView.tsx` - Pass agent panel callback through component tree

## How to Test

### 1. Start the Backend
```bash
# Terminal 1
uvicorn crt_api:app --reload --port 8123
```

### 2. Start the Frontend
```bash
# Terminal 2
cd frontend
npm run dev
# Opens on http://localhost:5173
```

### 3. Trigger Agent Activation

The agent automatically activates when:
- **Low confidence** (< 0.5) - CRT doesn't have strong knowledge
- **Contradictions detected** - Conflicting statements found
- **Insufficient context** - Fallback response triggered
- **Memory gaps** - Very few relevant memories found

#### Test Scenarios

**Scenario A: Low Confidence Query**
```
User: "Tell me about quantum entanglement in the context of CRT"
→ Low confidence (not in memory)
→ Agent activates to research
→ Blue "🤖 AGENT TRACE" badge appears
→ Click badge to see execution steps
```

**Scenario B: Complex Research Query**
```
User: "What are the key features of CRT's contradiction resolution system?"
→ Agent searches memory + research
→ Synthesizes findings
→ Shows 4-6 steps in trace
```

**Scenario C: Manual Agent Run** (via API directly)
```bash
curl -X POST http://127.0.0.1:8123/api/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "test",
    "query": "Research CRT architecture",
    "max_steps": 8
  }'
```

### 4. Interact with AgentPanel

When you click the "🤖 AGENT TRACE" badge:

1. **Modal Opens** - Full-screen lightbox with agent execution
2. **Header Shows**:
   - Step count (e.g., "5 steps")
   - Success/failure status (✅/❌)
   - Execution duration (e.g., "2.5s")
3. **Steps Display**:
   - Each step is collapsible (click to expand/collapse)
   - Shows thought, action, observation
   - Color-coded results (green = success, red = fail)
4. **Controls Available**:
   - "Expand All" - Show all step details
   - "Collapse All" - Hide all step details
   - "X" or click outside - Close modal

### 5. What to Look For

#### Good Agent Execution ✅
```
Step 1: 💭 "I should search memory for CRT architecture"
        ⚡ search_memory({"query": "architecture", "top_k": 5})
        ✅ Found 3 memories

Step 2: 💭 "Need more detail from documentation"
        ⚡ search_research({"query": "CRT architecture"})
        ✅ Found 2 citations

Step 3: 💭 "I have enough information to answer"
        ⚡ synthesize([memory_results, research_results])
        ✅ Synthesis complete

Step 4: 💭 "Ready to finish"
        ⚡ finish({"answer": "CRT architecture consists of..."})
        ✅ Task complete
```

#### Failed Execution ❌
```
Step 1: 💭 "Search for file"
        ⚡ read_file({"path": "../nonexistent.md"})
        ❌ File not found

Step 2: 💭 "Try alternative path"
        ⚡ list_files({"path": "."})
        ✅ 50 files

... (continues until max steps or success)
```

### 6. UI Features

#### Step Card Components
- **Step Number Badge** - Blue circle with step number
- **Thought Section** - 💭 What the agent was thinking
- **Action Section** - ⚡ Tool used + arguments (JSON formatted)
- **Observation Section** - 👁️ Result with color coding
- **Timestamp** - When the step executed

#### Tool Icons
- 🧠 `search_memory` - Search CRT memory
- 🔍 `search_research` - Search documents
- 💾 `store_memory` - Save to memory
- ⚖️ `check_contradiction` - Validate statements
- 🧮 `calculate` - Math evaluation
- 📄 `read_file` - File reading
- 📁 `list_files` - Directory listing
- 🔗 `synthesize` - Combine sources
- 🤔 `reflect` - Self-critique
- 📋 `plan` - Create execution plan
- ✅ `finish` - Complete task

## Troubleshooting

### Agent Not Activating
**Problem:** No "AGENT TRACE" badge appears
**Solutions:**
1. Check API is running: `curl http://127.0.0.1:8123/api/agent/status`
2. Verify confidence is low enough (< 0.5 for suggestions, < 0.3 for auto-activation)
3. Check browser console for errors
4. Ensure Ollama is running if using LLM reasoning: `ollama serve`

### Empty Trace
**Problem:** Badge appears but clicking shows empty modal
**Solutions:**
1. Check `metadata.agent_trace` in API response (inspect network tab)
2. Verify agent execution completed (not timed out)
3. Check backend logs for agent errors

### LLM Not Available
**Problem:** Agent uses fallback heuristics instead of smart reasoning
**Expected Behavior:** This is normal! Agent works without LLM.
**To Enable LLM:**
```bash
# Terminal 3
ollama serve
# Keep running in background
```

### TypeScript Errors
**Problem:** Red squiggles in VS Code
**Solutions:**
1. Restart TypeScript server: `Ctrl+Shift+P` → "TypeScript: Restart TS Server"
2. Verify all types are updated (AgentTrace, AgentStep, etc.)
3. Check `frontend/src/types.ts` has all agent types

## API Endpoints Reference

### Check Agent Status
```bash
curl http://127.0.0.1:8123/api/agent/status

# Response:
# {
#   "available": true,
#   "llm_available": true,
#   "reasoning_available": true,
#   "tools_count": 10
# }
```

### Run Agent Manually
```bash
curl -X POST http://127.0.0.1:8123/api/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "test",
    "query": "Find all information about CRT",
    "max_steps": 10,
    "auto_mode": true
  }'
```

### Analyze Triggers
```bash
curl -X POST http://127.0.0.1:8123/api/agent/analyze-triggers \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "test",
    "response_data": {
      "confidence": 0.2,
      "response_type": "fallback",
      "query": "Test query"
    }
  }'

# Shows which triggers would activate and why
```

## Code Architecture

### Component Hierarchy
```
App.tsx
├── ChatThreadView
│   └── MessageBubble
│       └── [click "AGENT TRACE" badge]
└── AgentPanel (modal)
    └── StepCard (one per step)
        ├── Thought
        ├── Action (with args)
        └── Observation (with result)
```

### State Flow
```
1. User sends message
2. API returns response with metadata.agent_trace
3. App.tsx stores trace in message.crt.agent_trace
4. MessageBubble shows badge if agent_activated = true
5. User clicks badge
6. App.tsx sets agentPanelMessageId
7. AgentPanel renders with trace data
8. User explores steps, then closes
9. App.tsx clears agentPanelMessageId
```

## Next Steps

### Enhancements (Optional)
1. **Export Trace** - Download trace as JSON
2. **Step Timing** - Show individual step durations
3. **Tool Usage Stats** - Chart showing which tools used most
4. **Agent Toggle** - Disable auto-activation in UI settings
5. **Replay Mode** - Step-by-step replay of agent execution
6. **Compare Traces** - Side-by-side comparison of different runs

### Integration with M4/M5
- Background jobs can show agent traces in job details
- Learning system can analyze successful agent patterns
- Metrics dashboard can show agent performance over time

## Success Criteria

✅ Agent activates on low confidence queries  
✅ "AGENT TRACE" badge appears on messages  
✅ Clicking badge opens AgentPanel modal  
✅ All steps display with thought/action/observation  
✅ Tool icons and color coding work correctly  
✅ Expand/collapse controls function  
✅ Final answer shows at bottom  
✅ Modal closes without errors  
✅ Works with and without LLM available  

---

**Status:** ✅ Complete - Ready for testing
**Documentation:** See [CRT_AGENTIC_FEATURES.md](../CRT_AGENTIC_FEATURES.md) for full system documentation
