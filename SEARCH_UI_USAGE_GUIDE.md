# Search UI Usage Guide

**Component**: SearchResults.jsx  
**Location**: `sse-chat-ui/src/components/SearchResults.jsx`  
**Styling**: `sse-chat-ui/src/components/SearchResults.css`  
**Status**: Ready to integrate into React app

---

## Quick Start

### 1. Import the Component

```jsx
import SearchResults from './components/SearchResults';
```

### 2. Use in Your App

```jsx
function App() {
  const [searchResults, setSearchResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSearch = async (query) => {
    setLoading(true);
    try {
      const response = await fetch('/api/search', {
        method: 'POST',
        body: JSON.stringify({ query, highlight_contradictions: true })
      });
      const data = await response.json();
      setSearchResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <SearchInput onSearch={handleSearch} />
      <SearchResults 
        results={searchResults} 
        loading={loading} 
        error={error}
      />
    </div>
  );
}
```

---

## Props

### SearchResults Component

```jsx
<SearchResults 
  results={object}      // Required: EvidencePacket data
  graph={object}        // Optional: Contradiction graph data
  loading={boolean}     // Optional: Show loading state
  error={string|null}   // Optional: Show error message
/>
```

### Results Object Structure

From the RAG or Search adapter response:

```json
{
  "results": {
    "claims": [
      {
        "claim_id": "claim_001",
        "text": "The Earth orbits the Sun",
        "source": "NASA",
        "relevance": 0.95,
        "contradiction_count": 2,
        "cluster_id": "cluster_001",
        "highlighted": false
      }
    ],
    "contradictions": [
      {
        "claim_1": "claim_001",
        "claim_2": "claim_002",
        "strength": 0.85
      }
    ],
    "clusters": [
      {
        "cluster_id": "cluster_001",
        "claims": ["claim_001", "claim_003"],
        "description": "Claims about orbital mechanics"
      }
    ],
    "statistics": {
      "total_claims": 5,
      "total_contradictions": 2,
      "total_clusters": 2
    }
  },
  "graph": {
    "nodes": [
      {
        "id": "claim_001",
        "label": "The Earth orbits the Sun",
        "contradiction_count": 2,
        "cluster_id": "cluster_001",
        "highlighted": true
      }
    ],
    "edges": [
      {
        "source": "claim_001",
        "target": "claim_002",
        "strength": 0.85
      }
    ],
    "statistics": {
      "total_nodes": 5,
      "total_edges": 2
    }
  }
}
```

---

## Component Features

### View Modes

**List View** (default)
- Displays all claims as cards
- Shows relevance score (0-100%)
- Shows topology indicators (contradiction count, cluster membership)
- Sorted by relevance (highest first)
- "View Topology" button for each claim

**Graph View**
- SVG visualization of contradiction topology
- Nodes = Claims (circles)
- Edges = Contradictions (lines)
- Node highlighting = High structural complexity
- Interactive legend explaining the visualization

### Topology Indicators

The UI shows **only structural information**, never truth or credibility:

| Indicator | Meaning |
|-----------|---------|
| 🔀 Contradictions | How many other claims contradict this one |
| 🔗 Cluster | Which structural group this claim belongs to |
| 📍 Highlighted | High structural complexity (involved in many contradictions) |

### Colors & Styling

- **Blue boxes**: Regular claims
- **Yellow border**: Topology-highlighted claims (high complexity)
- **Gray badges**: Contradiction count and cluster membership
- **SVG circles**: Nodes in graph (size = contradiction count)
- **Dashed lines**: Contradiction edges

---

## Example: Connect to Search API

### Backend API Endpoint

```python
# From sse/platform_integration.py

@app.post("/api/search")
def search_endpoint(request):
    """
    Search endpoint with contradiction highlighting
    """
    query = request.json.get('query')
    packet = request.json.get('packet')
    highlight = request.json.get('highlight_contradictions', True)
    
    # Call platform integration boundary
    boundary = get_adapter_boundary()
    result = boundary.search_endpoint(
        packet_dict=packet,
        highlight_contradictions=highlight,
        adapter_request_id=str(uuid.uuid4())
    )
    
    return result
```

### Frontend Usage

```jsx
import SearchResults from './components/SearchResults';

function SearchPanel() {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSearch = async (query) => {
    setLoading(true);
    setError(null);
    
    try {
      // Step 1: Get search results from Search adapter
      const response = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          highlight_contradictions: true
        })
      });

      if (!response.ok) throw new Error('Search failed');
      
      const data = await response.json();
      
      // Step 2: Verify response has valid structure
      if (!data.valid) {
        throw new Error(data.error || 'Invalid search response');
      }
      
      // Step 3: Set results for display
      setResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="search-panel">
      <input 
        type="text" 
        placeholder="Ask a question..."
        onKeyPress={(e) => e.key === 'Enter' && handleSearch(e.target.value)}
      />
      <SearchResults 
        results={results}
        loading={loading}
        error={error}
      />
    </div>
  );
}

export default SearchPanel;
```

---

## Understanding the Display

### List View Example

```
📋 List View

Search Results
5 claims | 2 contradictions | 2 clusters

[claim_001] The Earth orbits the Sun
  Relevance: 95%
  Topology Indicators: 🔀 2 contradictions | 🔗 Cluster 1
  Source: NASA
  📍 Topology-highlighted (high structural complexity)
  [View Topology]

[claim_002] The Sun orbits the Earth
  Relevance: 45%
  Topology Indicators: 🔀 1 contradiction | 🔗 Cluster 2
  Source: Flat Earth Society
  [View Topology]
```

### Graph View Example

```
📊 Topology Graph

5 claims (nodes) | 2 contradictions (edges)

    ┌─────────────┐
    │  [CM1]      │ ← Node (claim)
    └──────┬──────┘
           │
           │ Dashed line = Contradiction
           │ (strength: 0.85)
           │
    ┌──────▼──────┐
    │  [CM2]      │
    └─────────────┘

Legend:
• Nodes = Claims
─ Edges = Contradictions
```

---

## What User Sees

### Explicitly Topology Language ✅

User sees:
- "contradiction count" ← **Structural**
- "cluster membership" ← **Structural**
- "topology-highlighted" ← **Structural**
- "contradiction strength: 0.85" ← **Structural**

### Never Credibility Language ✅

User NEVER sees:
- ❌ "credible" / "incredible"
- ❌ "confidence" / "confident"
- ❌ "true" / "false"
- ❌ "reliable" / "unreliable"
- ❌ "trustworthy" / "untrustworthy"
- ❌ "likely" / "probable"
- ❌ "ranking" / "score" (by truth)

---

## Wiring Checklist

- [ ] Import SearchResults component in your app
- [ ] Connect to backend `/api/search` endpoint
- [ ] Pass results object with correct structure
- [ ] Set loading state during request
- [ ] Set error state if request fails
- [ ] Test List view mode
- [ ] Test Graph view mode
- [ ] Verify topology language (not truth language)
- [ ] Check mobile responsiveness
- [ ] Monitor event logs in `adapter_logs/`

---

## Debugging

### Results not showing?

```js
// Check 1: Results object has correct structure
console.log('Results:', results);
// Should have: claims, contradictions, clusters, statistics

// Check 2: Claims have required fields
console.log('First claim:', results.results.claims[0]);
// Should have: claim_id, text, source, relevance, contradiction_count, cluster_id

// Check 3: Check backend response
// Look for valid: true in response
console.log('Valid:', results.valid);
```

### Graph not rendering?

```js
// Check: Graph object has correct structure
console.log('Graph:', results.graph);
// Should have: nodes, edges, statistics

// Check: At least one contradiction exists
console.log('Total edges:', results.graph.statistics.total_edges);
// Should be > 0 for graph to display
```

### Check API Endpoint

```bash
# Test search endpoint
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "highlight_contradictions": true}'
```

---

## Performance Tips

1. **Limit claims shown**: Very large evidence sets (1000+ claims) may slow rendering
   - Filter to top 20-50 claims by relevance
   
2. **Lazy load graph**: Only render graph when user switches to Graph view
   - Currently done in component (Graph View button)

3. **Monitor event logs**: Check `adapter_logs/adapter_events_YYYY-MM-DD.jsonl`
   - Look for latency spikes
   - Monitor validation failures

4. **Cache results**: Keep search results in state until new search
   - Avoid re-fetching same query

---

## Next Steps

1. **Integrate into React App**
   - Add SearchPanel component
   - Wire to backend API

2. **Test with Real Data**
   - Run integration tests
   - Check event logs

3. **Gather User Feedback**
   - Is topology language clear?
   - Is graph visualization helpful?
   - Any confusing claims or display?

4. **Monitor Production** (When Deployed)
   - Track event logs
   - Monitor latency
   - Gather user feedback for improvements

---

## Component API Reference

### SearchResults

```jsx
<SearchResults 
  results={{
    results: {...},
    contradictions: [...],
    clusters: [...],
    statistics: {...}
  }}
  graph={{
    nodes: [...],
    edges: [...],
    statistics: {...}
  }}
  loading={false}
  error={null}
/>
```

**Returns**: Rendered React component with List and Graph views

### SearchResultItem (Internal)

Used automatically by SearchResults, shows single claim.

### ContradictionGraph (Internal)

Used automatically by SearchResults, renders SVG graph.

---

## Key Design Principles

1. **Topology-Only**: Never judge truth, only show structure
2. **User Decides**: UI helps user understand contradictions, user resolves them
3. **Transparent**: All information visible (no hidden claims)
4. **Auditable**: Every interaction logged to event log
5. **Non-Judgmental**: Language is objectively structural

---

*This UI is intentionally constrained. It shows contradictions without trying to resolve them. Users make their own judgments.*
