# Quick Start: Adding Heartbeat Feed to Your UI

## Option 1: Add to Existing Inspector Page

If you want to show heartbeat activity alongside reflection/personality loops:

**File: `frontend/src/pages/LoopsInspectorPage.tsx` (or similar)**

```tsx
import { HeartbeatFeed } from '../components/heartbeat/HeartbeatFeed';
import { BackgroundLoopInspector } from '../components/chat/BackgroundLoopInspector';

export function LoopsInspectorPage({ threadId }: { threadId: string }) {
  return (
    <div className="loops-page">
      <h1>Background Loops</h1>
      
      {/* Existing loop inspector */}
      <BackgroundLoopInspector threadId={threadId} />
      
      {/* NEW: Heartbeat activity feed */}
      <section className="heartbeat-section">
        <HeartbeatFeed threadId={threadId} limit={15} />
      </section>
    </div>
  );
}
```

## Option 2: Create Dedicated Heartbeat Page

**File: `frontend/src/pages/HeartbeatPage.tsx` (NEW)**

```tsx
import React from 'react';
import { useParams } from 'react-router-dom';
import { HeartbeatFeed } from '../components/heartbeat/HeartbeatFeed';

export function HeartbeatPage() {
  const { threadId } = useParams<{ threadId: string }>();

  return (
    <div className="heartbeat-page" style={{ padding: '2rem', maxWidth: '900px', margin: '0 auto' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>
          🦞 Heartbeat Activity
        </h1>
        <p style={{ color: '#6b7280' }}>
          See what the agent has been up to on Moltbook
        </p>
      </header>

      <HeartbeatFeed threadId={threadId} limit={20} showTitle={false} />
    </div>
  );
}
```

**Add to router:**

```tsx
// In your App.tsx or routes.tsx
import { HeartbeatPage } from './pages/HeartbeatPage';

<Route path="/threads/:threadId/heartbeat" element={<HeartbeatPage />} />
```

## Option 3: Sidebar Widget

**File: `frontend/src/components/Sidebar.tsx`**

```tsx
import { HeartbeatFeed } from './components/heartbeat/HeartbeatFeed';

export function Sidebar({ threadId }: { threadId: string }) {
  return (
    <aside className="sidebar">
      {/* ... existing sidebar content ... */}
      
      {/* Compact heartbeat feed */}
      <div className="sidebar-widget">
        <HeartbeatFeed 
          threadId={threadId} 
          limit={5} 
          showTitle={true}
        />
      </div>
    </aside>
  );
}
```

## Option 4: Dashboard Tile

**File: `frontend/src/pages/Dashboard.tsx`**

```tsx
import { HeartbeatFeed } from '../components/heartbeat/HeartbeatFeed';

export function Dashboard({ threadId }: { threadId: string }) {
  return (
    <div className="dashboard">
      <div className="grid grid-cols-2 gap-4">
        {/* Other dashboard tiles */}
        
        {/* Heartbeat tile */}
        <div className="dashboard-tile">
          <HeartbeatFeed 
            threadId={threadId}
            limit={10}
            showTitle={true}
          />
        </div>
      </div>
    </div>
  );
}
```

## Props Reference

```typescript
interface HeartbeatFeedProps {
  threadId?: string;      // Optional: omit for global feed
  limit?: number;         // Default: 10
  showTitle?: boolean;    // Default: true
}
```

## Styling Tips

The component uses CSS classes you can override:

```css
/* Custom theme */
.heartbeat-feed {
  --heartbeat-bg: #f9fafb;
  --heartbeat-border: #e5e7eb;
  --heartbeat-success: #10b981;
  --heartbeat-error: #ef4444;
}

/* Compact mode */
.heartbeat-feed.compact {
  padding: 0.5rem;
}

.heartbeat-feed.compact .activity-item {
  padding: 0.5rem;
  font-size: 0.875rem;
}

/* Dark mode */
.dark .heartbeat-feed {
  background: #1f2937;
  color: #f3f4f6;
}
```

## Testing

1. **Start backend:** `python crt_api.py`
2. **Enable heartbeat:**
   ```bash
   export CRT_HEARTBEAT_LOOP_ENABLED=true
   export CRT_HEARTBEAT_LOOP_SECONDS=60  # 1 minute for testing
   ```
3. **Trigger heartbeat:** POST `/api/threads/{threadId}/heartbeat/run-now`
4. **Check feed:** Component should show activity after 30s refresh

## Example: Full Implementation

**File: `frontend/src/App.tsx`**

```tsx
import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { HeartbeatFeed } from './components/heartbeat/HeartbeatFeed';

function App() {
  const [threadId] = useState('default');

  return (
    <BrowserRouter>
      <div className="app">
        <nav>
          <Link to="/">Chat</Link>
          <Link to="/heartbeat">Heartbeat</Link>
          <Link to="/moltbook">Moltbook</Link>
        </nav>

        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route 
            path="/heartbeat" 
            element={
              <div className="page">
                <h1>🦞 Agent Heartbeat</h1>
                <HeartbeatFeed threadId={threadId} limit={20} />
              </div>
            } 
          />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
```

## API Integration

The component automatically handles:
- ✅ Initial data fetch on mount
- ✅ Auto-refresh every 30 seconds
- ✅ Loading states
- ✅ Error handling
- ✅ Empty state messages

No additional setup required!

## Troubleshooting

**Q: Component shows "No heartbeat activity yet"**
- Check that `CRT_HEARTBEAT_LOOP_ENABLED=true`
- Manually trigger: POST `/api/threads/{threadId}/heartbeat/run-now`
- Check backend logs for heartbeat execution

**Q: Activities not refreshing**
- Verify API endpoint returns data: `GET /api/threads/{threadId}/heartbeat/history`
- Check browser console for CORS/network errors
- Ensure `threadId` prop is valid

**Q: Actions not displaying**
- Verify heartbeat executor is actually taking actions (not all "action": "none")
- Check `heartbeat_last_actions_json` in database
- Review HEARTBEAT.md instructions for action triggers

## Next Steps

1. Add navigation link to heartbeat page
2. Create HeartbeatSettings component for config
3. Add filters (by action type, date range)
4. Export activity log as JSON/CSV
5. Add charts/visualizations for trends

Enjoy your local OpenClaw experience! 🦞
