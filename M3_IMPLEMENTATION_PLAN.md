# M3 Implementation Plan - Evidence Packets

**Goal:** Web/tool research that doesn't become lying.

**Timeline:** 3-5 days

---

## What M3 Delivers

**User Experience:**
```
User: "What's the latest on Anthropic's Claude?"
System: [Searches web]
System: "According to TechCrunch (Dec 2025), Claude 3.5 Sonnet was released..."
         ↳ Shows citation: [1] "Anthropic releases Claude 3.5..." techcrunch.com
User: "Show me the source"
System: [Opens citation panel with original quote + link]
```

**Key Innovation:** Every research fact has a traceable source. If sources conflict, system records contradiction instead of merging into false consensus.

---

## Architecture

### Data Flow
```
Query → Search → Fetch → Extract Quotes → Summarize with Citations → TOOL Memory
                                                                          ↓
                                                            [quarantined, never auto-promoted]
                                                                          ↓
                                                            User sees citations in UI
                                                                          ↓
                                                            User can promote to belief lane
```

### Memory Lanes (Already Exists)
- **Belief Lane:** User-confirmed facts (trust 0.7-1.0)
- **Notes Lane:** Research notes, unconfirmed (trust 0.3-0.5) ← M3 writes here

---

## Implementation Tasks

### Phase 1: Backend Core (2 days)

**1.1 Evidence Packet Schema** (2 hours)
```python
# personal_agent/evidence_packet.py

@dataclass
class Citation:
    quote_text: str
    source_url: str
    char_offset: Tuple[int, int]  # In original document
    fetched_at: datetime
    
@dataclass
class EvidencePacket:
    packet_id: str
    query: str
    summary: str
    citations: List[Citation]
    created_at: datetime
    trust: float = 0.4  # TOOL sources start at 0.4
    lane: str = "notes"  # Always quarantined
```

**Files:** Create `personal_agent/evidence_packet.py`

**1.2 Search Integration** (3 hours)

**Option A: Local Index (Quick)**
- Use existing SSE compression for local documents
- Search personal files, not web
- Faster, no dependencies

**Option B: Web Search (Full M3)**
- Use DuckDuckGo (no API key needed)
- Fetch page content with `requests` + `BeautifulSoup`
- Extract quotes with char offsets

**Decision:** Start with Option A (local), add Option B in M3.5

```python
# personal_agent/research_engine.py

class ResearchEngine:
    def search(self, query: str) -> List[str]:
        """Search for relevant sources"""
        
    def fetch(self, url: str) -> str:
        """Fetch document content"""
        
    def extract_quotes(self, text: str, query: str) -> List[Citation]:
        """Extract relevant quotes with offsets"""
```

**Files:** Create `personal_agent/research_engine.py`

**1.3 TOOL Memory Integration** (2 hours)

Update `personal_agent/crt_memory.py`:
```python
def store_research_result(
    self,
    query: str,
    evidence_packet: EvidencePacket
) -> str:
    """Store research in notes lane with provenance"""
    return self.store(
        kind="research_note",
        lane="notes",  # Quarantined
        key=f"research:{query_hash}",
        value_text=evidence_packet.summary,
        source=MemorySource.EXTERNAL,
        trust=0.4,
        provenance_json={
            "citations": [c.to_dict() for c in evidence_packet.citations],
            "query": query,
            "fetched_at": evidence_packet.created_at.isoformat()
        }
    )
```

**Files:** Update `personal_agent/crt_memory.py`

### Phase 2: API Endpoints (1 day)

**2.1 Research Endpoint** (3 hours)
```python
# crt_api.py

@app.post("/api/research/search")
async def research_search(
    query: str,
    thread_id: str,
    max_sources: int = 3
):
    """Execute research query, return evidence packet"""
    engine = ResearchEngine()
    packet = engine.research(query, max_sources)
    
    # Store in TOOL memory
    rag = get_rag(thread_id)
    memory_id = rag.memory.store_research_result(query, packet)
    
    return {
        "packet_id": packet.packet_id,
        "summary": packet.summary,
        "citations": [c.to_dict() for c in packet.citations],
        "memory_id": memory_id
    }

@app.get("/api/research/citations/{memory_id}")
async def get_citations(memory_id: str, thread_id: str):
    """Get citations for a research memory"""
    rag = get_rag(thread_id)
    memory = rag.memory.retrieve_by_id(memory_id)
    return memory.provenance_json.get("citations", [])
```

**Files:** Update `crt_api.py`

**2.2 Promotion Endpoint** (2 hours)
```python
@app.post("/api/research/promote")
async def promote_research(
    memory_id: str,
    thread_id: str,
    user_confirmed: bool
):
    """Promote research note to belief lane"""
    if not user_confirmed:
        return {"error": "User confirmation required"}
    
    rag = get_rag(thread_id)
    rag.memory.promote_to_belief(memory_id)
    
    return {"promoted": True, "memory_id": memory_id}
```

**Files:** Update `crt_api.py`

### Phase 3: Frontend UI (2 days)

**3.1 Citation Viewer Component** (4 hours)
```typescript
// frontend/src/components/CitationViewer.tsx

export function CitationViewer({ citations }: { citations: Citation[] }) {
  return (
    <div className="citations">
      {citations.map((cite, idx) => (
        <div key={idx} className="citation-card">
          <div className="quote">"{cite.quote_text}"</div>
          <a href={cite.source_url} target="_blank">
            {cite.source_url}
          </a>
          <div className="metadata">
            Fetched: {new Date(cite.fetched_at).toLocaleString()}
          </div>
        </div>
      ))}
    </div>
  );
}
```

**Files:** Create `frontend/src/components/CitationViewer.tsx`

**3.2 Research Integration in Chat** (4 hours)

Update `frontend/src/App.tsx` chat component:
```typescript
// Show citations inline with answers
{message.citations && (
  <CitationViewer citations={message.citations} />
)}

// Add "Research" button
<button onClick={() => handleResearch(query)}>
  Research This 🔍
</button>
```

**Files:** Update `frontend/src/App.tsx`

**3.3 Source Inspector Modal** (3 hours)
```typescript
// frontend/src/components/SourceInspector.tsx

export function SourceInspector({ memoryId }: { memoryId: string }) {
  const [citations, setCitations] = useState([]);
  
  useEffect(() => {
    api.getCitations(memoryId).then(setCitations);
  }, [memoryId]);
  
  return (
    <dialog>
      <h2>Source Evidence</h2>
      {citations.map(cite => (
        <div>
          <blockquote>{cite.quote_text}</blockquote>
          <a href={cite.source_url}>View Original</a>
        </div>
      ))}
      <button onClick={handlePromote}>
        Promote to Beliefs ✓
      </button>
    </dialog>
  );
}
```

**Files:** Create `frontend/src/components/SourceInspector.tsx`

### Phase 4: Testing & Validation (1 day)

**4.1 Unit Tests** (3 hours)
```python
# tests/test_evidence_packets.py

def test_research_creates_quarantined_memory():
    """Research results go to notes lane, not belief lane"""
    
def test_citation_char_offsets_accurate():
    """Quote offsets point to correct text"""
    
def test_promotion_requires_user_confirmation():
    """Can't auto-promote TOOL memories"""
    
def test_conflicting_sources_create_contradiction():
    """If sources conflict, record contradiction"""
```

**Files:** Create `tests/test_evidence_packets.py`

**4.2 Integration Test** (2 hours)
```python
# tests/test_m3_research_flow.py

def test_full_research_flow():
    """End-to-end: query → search → fetch → cite → store"""
    
def test_research_with_contradictions():
    """Multiple sources with conflicting info"""
```

**Files:** Create `tests/test_m3_research_flow.py`

**4.3 Manual Smoke Test** (1 hour)
1. Start API + frontend
2. Ask: "Research the history of Python programming language"
3. Verify citations appear
4. Click citation → verify source inspector opens
5. Promote to beliefs → verify moves to belief lane
6. Ask contradictory research query → verify contradiction recorded

---

## Acceptance Criteria

✅ Every research answer has 1+ citations  
✅ Citations show source URL + quote text + timestamp  
✅ Research results stored in notes lane (quarantined)  
✅ User can view original sources  
✅ User can promote research to belief lane  
✅ Conflicting sources trigger contradiction  
✅ UI shows citation count per answer  
✅ Citation viewer modal working  

---

## Dependencies & Risks

**External Dependencies:**
- `requests` - HTTP fetch (already in requirements.txt)
- `beautifulsoup4` - HTML parsing (need to add)
- `duckduckgo-search` - Search (optional, add if doing web)

**Risks:**
1. **Web scraping reliability** - Sites might block/change structure
   - Mitigation: Start with local docs, add web later
2. **Quote extraction accuracy** - Char offsets might drift
   - Mitigation: Store both offset + exact text for validation
3. **Citation UI complexity** - Lots of new React components
   - Mitigation: Use existing Tailwind components, keep simple

---

## Week 2 Schedule

**Monday:**
- Morning: Evidence packet schema + research engine stub
- Afternoon: Local document search integration

**Tuesday:**
- Morning: TOOL memory integration + provenance storage
- Afternoon: API endpoints (search + citations)

**Wednesday:**
- Morning: CitationViewer component
- Afternoon: Chat integration (show citations inline)

**Thursday:**
- Morning: SourceInspector modal + promotion flow
- Afternoon: UI polish + styling

**Friday:**
- Morning: Unit tests + integration tests
- Afternoon: Manual testing + bug fixes

**Result:** Working M3 by end of week

---

## Success Metrics

**Before M3:**
- Research queries: System makes stuff up or says "I don't know"
- Citations: None
- Provenance: None
- Trust: User must verify everything

**After M3:**
- Research queries: System searches, shows sources
- Citations: Every research fact has 1+ citations
- Provenance: Full trail from query → source → quote
- Trust: User can verify via citations

**Measurement:** Run 20 research queries, verify 100% have citations

---

## Next Steps

**Immediate (Today):**
1. ✅ M2 wrapped up
2. ✅ Backend services confirmed running
3. → Create `personal_agent/evidence_packet.py`
4. → Create `personal_agent/research_engine.py`
5. → Add `beautifulsoup4` to requirements.txt

**Tomorrow:**
- Implement search + fetch logic
- Test with local documents first
- Add provenance to memory storage

**This Week:**
- Complete backend (Phase 1-2)
- Start frontend (Phase 3)
- M3 shipped by Friday

---

## Files to Create/Update

**New Files:**
- `personal_agent/evidence_packet.py`
- `personal_agent/research_engine.py`
- `frontend/src/components/CitationViewer.tsx`
- `frontend/src/components/SourceInspector.tsx`
- `tests/test_evidence_packets.py`
- `tests/test_m3_research_flow.py`

**Update Files:**
- `personal_agent/crt_memory.py` - Add research storage
- `crt_api.py` - Add research endpoints
- `frontend/src/App.tsx` - Integrate citations
- `frontend/src/lib/api.ts` - Add research API calls
- `frontend/src/types.ts` - Add Citation/EvidencePacket types
- `requirements.txt` - Add beautifulsoup4

**Total:** 6 new files, 6 updates

---

## Ready to Start?

**Backend is running:** ✅  
**M2 complete:** ✅  
**M3 plan ready:** ✅  

**Next command:** `code personal_agent/evidence_packet.py`

Let's build M3! 🚀
