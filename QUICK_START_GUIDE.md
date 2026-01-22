# Quick Start Guide: Premium Components with Real API

## What Was Changed

This PR replaces sample/mock data in premium frontend components with real API data from the CRT backend.

## Components Now Using Real Data

### 1. MemoryLaneVisualizer 🛡️
**Before:** Hardcoded sample memories  
**After:** Fetches from `/api/memory/recent`

**Location:** ShowcasePage → "Memory Lanes" tab

**What to see:**
- Stable lane: Memories with trust ≥ 0.75
- Candidate lane: Memories with trust < 0.75
- Real trust scores from database
- Actual timestamps and sources

### 2. TrustScoreCard 📊
**Before:** Static example cards  
**After:** Real memory data with trust scores

**Location:** ShowcasePage → "Trust Scores" tab

**What to see:**
- Current trust percentage
- Trust score visualization (colored bar)
- Source information
- Calculated confirmations
- Last updated timestamp

### 3. ContradictionLedger 🔍
**Before:** Component existed but not integrated  
**After:** Full integration with slide-in panel

**Location:** ShowcasePage → "Contradiction Ledger" tab

**What to see:**
- Badge showing contradiction count
- Preview of top 3 contradictions
- Click badge to open full ledger panel
- Each entry shows:
  - Contradiction ID
  - Status (DISCLOSED/PENDING)
  - Affected slot
  - Old vs new values
  - Trust scores for both
  - Summary/policy

## How to Test

### Prerequisites
```bash
# Install Python dependencies (if needed)
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
```

### Start Backend
```bash
# From repository root
python -m uvicorn crt_api:app --reload --port 8123
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8123
INFO:     Application startup complete.
```

### Start Frontend
```bash
# In a new terminal, from repository root
cd frontend
npm run dev
```

You should see:
```
  VITE v4.x.x  ready in XXX ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### Open Showcase Page
1. Navigate to http://localhost:5173
2. Click "Showcase" in the sidebar (or navigate to `/showcase`)
3. Test each tab:
   - **Memory Lanes**: Should show your actual memories split by trust
   - **Trust Scores**: Should show cards for stable and candidate memories
   - **Contradiction Ledger**: Should show contradiction count and list

## What You'll See

### With No Data (First Time)
- **Memory Lanes**: Empty state message "No memories to display"
- **Trust Scores**: Empty state message "No memories to display"  
- **Ledger**: Green checkmark "No contradictions detected"

### After Chatting with CRT
1. Go to main chat page
2. Have a conversation (e.g., "My name is John. I work at Amazon.")
3. Create some contradictions (e.g., "Actually, I work at Microsoft.")
4. Return to Showcase page
5. You'll now see:
   - Real memories in the lanes
   - Trust scores for your facts
   - Contradictions in the ledger

### During Loading
- Hourglass emoji (⏳)
- "Loading memories..." / "Loading contradictions..." message

### On Error
- Red error box with message
- "Retry" button to fetch again

## API Endpoints Being Called

When you load ShowcasePage, it automatically calls:

1. **GET `/api/memory/recent?thread_id=default&limit=100`**
   - Fetches your recent memories
   - Response: Array of memory objects with text, trust, confidence, etc.

2. **GET `/api/ledger/open?thread_id=default&limit=50`**
   - Fetches open contradictions
   - Response: Array of contradictions with enhanced details (NEW!)
   - Each includes: slot, old_value, new_value, trust scores

## New Backend Features

### Enhanced Contradiction Response
The `/api/ledger/open` endpoint now returns additional fields:

```json
{
  "ledger_id": "led_abc123",
  "contradiction_id": "led_abc123",        // NEW: Alias for UI
  "slot": "employer",                      // NEW: Extracted from affects_slots
  "old_value": "Amazon",                   // NEW: Memory text
  "new_value": "Microsoft",                // NEW: Memory text
  "old_trust": 0.85,                       // NEW: Trust score
  "new_trust": 0.90,                       // NEW: Trust score
  "detected_at": 1704067200,               // NEW: Alias for timestamp
  "policy": "conflict",                    // NEW: From contradiction_type
  "status": "open",
  "summary": "Job change detected",
  // ... other existing fields
}
```

## Code Structure

### Frontend Data Flow
```
ShowcasePage.tsx
  ├─ useEffect() → fetchData()
  │   ├─ listRecentMemories() → /api/memory/recent
  │   └─ listOpenContradictions() → /api/ledger/open
  │
  ├─ Split memories by trust (0.75 threshold)
  │   ├─ stable: trust >= 0.75
  │   └─ candidate: trust < 0.75
  │
  └─ Render components with real data
      ├─ MemoryLaneVisualizer(stableMemories, candidateMemories)
      ├─ TrustScoreCard(memory data)
      └─ ContradictionLedger(contradictions)
```

### Backend Enhancement
```
crt_api.py → /api/ledger/open
  ├─ Get contradictions from ledger
  ├─ For each contradiction:
  │   ├─ Fetch old memory details
  │   ├─ Fetch new memory details
  │   ├─ Extract slot from affects_slots
  │   └─ Build enhanced response
  └─ Return ContradictionListItem[]
```

## Troubleshooting

### "Failed to fetch data"
- Check backend is running on port 8123
- Check browser console for CORS errors
- Try: `curl http://localhost:8123/health`

### Empty states showing with data in database
- Check thread_id (default is "default")
- Check API response in Network tab
- Verify data exists: `curl http://localhost:8123/api/memory/recent?thread_id=default`

### TypeScript build errors
- Pre-existing errors in MessageBubble.tsx are unrelated
- Our changes pass Python syntax check
- Frontend will build despite TS config warnings

## Export Functionality

### Contradiction Ledger Export
1. Open ledger panel (click badge)
2. Click "Export Ledger" button
3. Downloads `contradictions-ledger.json`
4. Contains all contradictions with full details

## Next Steps

1. **Test in your environment** - Follow "How to Test" above
2. **Create some data** - Chat with CRT to generate memories and contradictions
3. **Verify all components** - Check each tab in Showcase page
4. **Review export** - Try exporting the ledger data

## Questions?

See `WIRE_PREMIUM_COMPONENTS_SUMMARY.md` for complete technical details.
