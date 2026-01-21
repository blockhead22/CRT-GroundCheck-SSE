# Demo Mode Feature

**Added:** January 21, 2026  
**Version:** v0.9-beta  
**Purpose:** One-click contradiction demonstration for beta testers

---

## Quick Access

Click the **🎬 Demo** button in the top navigation bar (emerald green, next to X-Ray button).

---

## What It Does

Opens a lightbox with **5 pre-scripted turns** demonstrating CRT's contradiction handling:

1. **Turn 1:** Initial fact ("My name is Alex Chen and I work at DataCore")
2. **Turn 2:** Create contradiction ("Actually, I work at TechFlow, not DataCore")
3. **Turn 3:** Recall contradicted fact ("Where do I work?")
4. **Turn 4:** Confirm non-contradicted fact ("What's my name?")
5. **Turn 5:** Memory summary ("What do you know about me?")

---

## Usage

### Option 1: One-Click Send
Click the **▶ Send** button next to any turn → Message sent immediately, lightbox closes.

### Option 2: Copy-Paste
Click the **📋 Copy** button → Paste into chat input → Send manually.

### Sequential Flow
Run turns **in order** for proper contradiction demonstration:
- Turn 1 establishes facts
- Turn 2 creates the contradiction
- Turn 3 tests reintroduction disclosure (should show badge + caveat)

---

## Expected Results

### Turn 3 (Critical Test)
**Expected badge:**
```
⚠️ CONTRADICTED CLAIMS (2)
```

**Expected answer format:**
```
TechFlow (most recent update)
```
or similar caveat phrase.

**X-Ray mode (if enabled):**
Both memories flagged with `⚠️ CONTRADICTED` inline badge.

### Turn 4
Clean answer with no badges (name not contradicted).

### Turn 5
Summary listing both facts, with employer showing caveat/badge.

---

## Technical Details

**Files modified:**
- `frontend/src/components/DemoModeLightbox.tsx` (new component)
- `frontend/src/components/Topbar.tsx` (added Demo button)
- `frontend/src/App.tsx` (state + lightbox integration)

**No core logic changes:**
- Memory system unchanged
- Gates unchanged
- Contradiction detection unchanged
- Frontend-only feature

**Styling:**
- Emerald button (`border-emerald-500/30 bg-emerald-500/20`)
- Modal matches CRT dark theme (`slate-900/95`)
- Hover states on all interactive elements

---

## Screenshot Locations

After running demo, check for:
1. **Topbar:** Emerald "🎬 Demo" button visible
2. **Lightbox:** 5 turns with Copy/Send buttons
3. **Turn 3 response:** Amber badge visible in message
4. **X-Ray panel:** Contradicted memories flagged (if X-Ray enabled)

**To capture:**
1. Open demo lightbox: Screenshot topbar + modal
2. Send Turn 3: Screenshot message with badge
3. Enable X-Ray: Screenshot memory panel with flags

---

## Beta Testing Notes

**Success criteria:**
- ✅ Demo button appears in topbar
- ✅ Lightbox opens with 5 turns
- ✅ Send button works (closes lightbox, sends message)
- ✅ Copy button works (clipboard confirmation)
- ✅ Turn 3 shows badge + caveat
- ✅ X-Ray shows flagged memories

**Known limitations:**
- Requires API running on port 8123
- Requires Ollama for natural language caveats (optional)
- Thread state persists (demo turns become part of chat history)

---

## Customization

To modify demo script, edit [frontend/src/components/DemoModeLightbox.tsx](frontend/src/components/DemoModeLightbox.tsx):

```tsx
const DEMO_TURNS = [
  {
    id: 1,
    label: 'Turn 1: Your Label',
    message: 'Your message text',
    description: 'What this turn does'
  },
  // ... more turns
]
```

---

**Built for:** Quick beta demonstrations without manual typing  
**Philosophy:** Make contradiction testing accessible with one click
