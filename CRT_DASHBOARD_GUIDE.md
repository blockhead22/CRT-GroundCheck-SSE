# CRT Dashboard - User Guide

**CRT System Visualization Dashboard v1.0**

## Quick Start

### Launch the Dashboard

```bash
streamlit run crt_dashboard.py
```

The dashboard will open at `http://localhost:8501`

### Populate with Demo Data

Before using the dashboard, populate it with sample data:

```bash
python populate_crt_demo_data.py
```

This creates:
- 10 sample interactions (queries with varying importance)
- 5 standalone memories
- Contradictions and trust evolution events
- Belief vs speech statistics

## Dashboard Pages

### 🏥 System Health (Landing Page)

**Overview of CRT system status**

**Metrics displayed:**
- **Total Memories**: Count of all stored memories
- **Open Contradictions**: Unresolved conflicts requiring reflection
- **Pending Reflections**: Queued reflection tasks
- **Average Trust**: Mean trust score across all memories

**Volatility Score:**
- Visual gauge showing system stability
- Green (<10%): Stable system
- Yellow (10-30%): Moderate volatility, adapting
- Red (>30%): High volatility, reflections needed

**Coherence Score:**
- Gauge showing average memory trust
- Higher = more coherent belief system

**Memory Sources:**
- Bar chart showing distribution of memory origins
- USER, SYSTEM, FALLBACK, REFLECTION

**Recent Activity:**
- Latest 5 memories with timestamps

---

### 📈 Trust Evolution

**Visualize how trust scores change over time**

**Features:**

1. **Current Trust Distribution**
   - Histogram of all memory trust scores
   - Shows concentration of high/low trust memories

2. **Trust Statistics**
   - Average trust
   - Median trust
   - Count of high trust (>0.7)
   - Count of low trust (<0.3)

3. **Trust Evolution Over Time**
   - Line chart tracking up to 10 recent memories
   - Shows trust trajectories as memories evolve
   - Hover for specific trust values and timestamps

**Interpretation:**
- Upward trends: Memory gaining trust through validation
- Downward trends: Memory degrading due to contradictions
- Flat lines: Stable, non-contradicted memories

---

### ⚠️ Contradiction Dashboard

**Track conflicts and drift in belief system**

**Metrics:**
- Total contradictions detected
- Open vs Resolved counts
- Average drift score

**Contradiction Timeline:**
- Scatter plot of contradictions over time
- Color-coded: Red (open), Green (resolved)
- Y-axis: Drift score (higher = more contradictory)
- Hover for memory IDs involved

**Contradiction List:**
- Expandable entries showing:
  - Old and new memory IDs
  - Detection timestamp
  - Resolution status and method
  - Notes and context

**Filters:**
- Toggle to show/hide resolved contradictions

**What to Watch:**
- High drift scores (>0.7): Significant contradictions
- Clusters of contradictions: Rapid belief changes
- Unresolved contradictions: Need reflection attention

---

### 💭 Belief vs Speech Monitor

**Understand when system speaks from belief vs fallback**

**Core Philosophy:**
- **Belief**: High-trust responses that pass reconstruction gates
- **Speech**: Fallback responses when gates fail

**Metrics:**
- Total queries processed
- Beliefs vs Speeches count
- Belief ratio (higher = more coherent system)

**Visualizations:**

1. **Pie Chart**
   - Green: Beliefs (passed gates)
   - Red: Speeches (failed gates)

2. **Gate Statistics**
   - Intent Gate Pass Rate: Query → Output alignment
   - Memory Gate Pass Rate: Output → Memory alignment
   - Average alignment scores

3. **Alignment Over Time**
   - Line chart showing:
     - Intent Alignment (blue): Query-output similarity
     - Memory Alignment (purple): Output-memory similarity
   - Threshold lines:
     - Intent: 0.6 (green dash)
     - Memory: 0.5 (orange dash)

**Interpretation:**
- High belief ratio: System speaking from validated memory
- Low belief ratio: Relying on fallback, needs more training
- Alignment trends: System getting better or worse at coherence

---

### 🔍 Memory Explorer

**Search, filter, and examine individual memories**

**Search & Filter:**

1. **Text Search**
   - Search memory content
   - Case-insensitive substring matching

2. **Source Filter**
   - Filter by: USER, SYSTEM, FALLBACK, REFLECTION
   - Multi-select supported

3. **Minimum Trust**
   - Slider to show only high-trust memories
   - Range: 0.0 to 1.0

**Sorting Options:**
- Timestamp (newest/oldest)
- Trust (high/low)
- Confidence

**Memory Cards:**

Each memory shows:
- **Trust**: Color-coded (green >0.7, yellow >0.4, red <0.4)
- **Confidence**: Initial certainty at creation
- **Source**: Origin of memory
- **SSE Mode**: Compression mode (L/C/H)
- **Created**: Timestamp
- **ID**: Short identifier
- **Full Text**: Complete memory content
- **Tags**: Associated tags (if any)

**Trust History:**
- Checkbox to expand trust evolution for each memory
- Shows all trust changes with timestamps and reasons

**Limits:**
- Displays up to 50 memories for performance
- Use filters to narrow down search

---

## Understanding CRT Metrics

### Trust Score (0.0 - 1.0)
- **What it is**: Evolves over time based on validation/contradictions
- **High (>0.7)**: Well-validated, stable belief
- **Medium (0.4-0.7)**: Moderately trusted
- **Low (<0.4)**: Contradicted or fallback source
- **Fallback cap**: Maxes at 0.3 for fallback sources

### Confidence Score (0.0 - 1.0)
- **What it is**: Fixed at creation, based on reasoning certainty
- **How it's set**: From LLM output or manual assignment
- **Unchanging**: Does not evolve over time

### Drift Score
- **What it is**: Semantic distance between two memories
- **Range**: 0.0 (identical) to 1.0 (opposite)
- **Threshold**: >0.4 considered contradiction

### Volatility
- **Formula**: Ratio of contradictions to total memories
- **Low (<0.1)**: Stable system
- **High (>0.3)**: Rapid changes, needs reflection

### Reconstruction Gates
- **Intent Gate**: `similarity(query, output) > 0.6`
- **Memory Gate**: `alignment(output, retrieved_memories) > 0.5`
- **Both must pass**: For response to be "belief"

---

## Typical Workflows

### 1. Morning Health Check

```
1. Open System Health page
2. Check volatility gauge
3. Review open contradictions count
4. Check pending reflections
5. If volatility >30%: Trigger reflections
```

### 2. Investigating Low Trust

```
1. Go to Trust Evolution
2. Check trust distribution histogram
3. Identify memories with low trust
4. Go to Memory Explorer
5. Sort by Trust (low)
6. Examine low-trust memories
7. Check their trust history
8. Look for contradiction patterns
```

### 3. Debugging Failed Queries

```
1. Go to Belief vs Speech Monitor
2. Check belief ratio (should be >50%)
3. If low, examine alignment over time
4. Look for patterns in gate failures
5. Go to Memory Explorer
6. Filter by source=FALLBACK
7. Review fallback responses
8. Identify missing memories to add
```

### 4. Analyzing Contradictions

```
1. Go to Contradiction Dashboard
2. Review timeline for clusters
3. Sort by drift score (high to low)
4. Expand high-drift contradictions
5. Note the memory IDs involved
6. Go to Memory Explorer
7. Search for those memory IDs
8. Understand the semantic drift
9. Decide if reflection needed
```

---

## Integration with CRT System

### The dashboard reads from:

- `personal_agent/crt_memory.db` - Memory storage
- `personal_agent/crt_ledger.db` - Contradiction ledger

### Tables accessed:

**crt_memory.db:**
- `memories` - All memory items
- `trust_log` - Trust evolution history
- `belief_speech` - Belief vs speech statistics
- `reflection_queue` - Pending reflections

**crt_ledger.db:**
- `contradictions` - Contradiction entries

### Real-time Updates

The dashboard uses Streamlit's caching:
- Refresh page (R) to see latest data
- Data loads from SQLite on each page view
- No WebSocket - manual refresh needed

---

## Performance Notes

### Large Memory Sets

- Memory Explorer limits to 50 displayed items
- Use filters to narrow down
- Trust Evolution shows max 10 memory trajectories

### Database Size

- SQLite scales well to 100k+ memories
- Slow queries on large datasets:
  - Trust history for specific memory: Fast (indexed)
  - All contradictions: Can be slow (add index if needed)

---

## Customization

### Adjusting Thresholds

Edit visualization thresholds in `crt_dashboard.py`:

```python
# Trust categories
TRUST_HIGH = 0.7
TRUST_MEDIUM = 0.4

# Volatility thresholds
VOLATILITY_LOW = 0.1
VOLATILITY_HIGH = 0.3

# Gate thresholds (match CRT config)
INTENT_THRESHOLD = 0.6
MEMORY_THRESHOLD = 0.5
```

### Color Schemes

Modify CSS in dashboard:

```python
st.markdown("""
<style>
    .trust-high { color: #2ecc71; }  /* Green */
    .trust-medium { color: #f39c12; } /* Orange */
    .trust-low { color: #e74c3c; }   /* Red */
</style>
""", unsafe_allow_html=True)
```

---

## Troubleshooting

### Dashboard won't start

```bash
# Check dependencies
pip install streamlit plotly pandas

# Verify databases exist
ls personal_agent/*.db

# Run with error output
streamlit run crt_dashboard.py 2>&1
```

### No data showing

```bash
# Populate demo data
python populate_crt_demo_data.py

# Check memory count
python -c "from personal_agent.crt_rag import CRTEnhancedRAG; \
           rag = CRTEnhancedRAG(); \
           print(len(rag.memory._load_all_memories()))"
```

### Slow performance

```bash
# Install watchdog for better file watching
pip install watchdog

# Run in minimal mode (disable file watcher)
streamlit run crt_dashboard.py --server.fileWatcherType none
```

### Database locked

```bash
# Close other connections
# Restart dashboard
# If persists, check for zombie processes:
ps aux | grep streamlit
kill <PID>
```

---

## Advanced Features

### Export Data

```python
# From any dashboard page, use sidebar
import pandas as pd
from personal_agent.crt_rag import CRTEnhancedRAG

rag = CRTEnhancedRAG()
memories = rag.memory._load_all_memories()

# Export to CSV
df = pd.DataFrame([{
    'text': m.text,
    'trust': m.trust,
    'confidence': m.confidence,
    'source': m.source.value,
    'timestamp': m.timestamp
} for m in memories])

df.to_csv('memories_export.csv', index=False)
```

### Live Monitoring

For continuous monitoring:

```bash
# Run dashboard
streamlit run crt_dashboard.py

# In another terminal, continuously add data
while true; do
    python -c "from personal_agent.crt_rag import CRTEnhancedRAG; \
               rag = CRTEnhancedRAG(); \
               rag.query('Test query', False)"
    sleep 5
done
```

Then refresh dashboard to see updates.

---

## Future Enhancements

**Planned for v2.0:**

- [ ] Auto-refresh every N seconds
- [ ] Interactive contradiction resolution
- [ ] Manual reflection triggering
- [ ] Memory editing/deletion
- [ ] Bulk import/export
- [ ] Dark mode
- [ ] Multi-session comparison
- [ ] Performance metrics dashboard
- [ ] Webhook notifications for high volatility

---

## Support & Documentation

**Related files:**
- `CRT_INTEGRATION.md` - Full CRT documentation
- `CRT_QUICK_REFERENCE.md` - Quick reference guide
- `crt_system_demo.py` - Code examples

**Architecture:**
- `personal_agent/crt_core.py` - Math equations
- `personal_agent/crt_memory.py` - Memory system
- `personal_agent/crt_ledger.py` - Contradiction tracking
- `personal_agent/crt_rag.py` - Integration layer

---

**Version**: 1.0  
**Last Updated**: January 9, 2026  
**Philosophy**: Memory first, honesty over performance
