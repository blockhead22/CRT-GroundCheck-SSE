# CRT Video Tutorial Script (2 Minutes)

**Target Length:** 2:00  
**Format:** Screen recording with voiceover  
**Audience:** Developers and AI product managers

---

## Scene 1: Hook (0:00-0:15)

**[SCREEN: Split screen showing two AI responses]**

**VOICEOVER:**
> "Traditional AI chatbots have a gaslighting problem. When facts change, they either overwrite history or randomly pick between conflicts, leaving users confused about what they actually said."

**[Visual: Show "Regular AI" response hiding contradiction vs "CRT AI" disclosing it]**

---

## Scene 2: Problem Statement (0:15-0:30)

**[SCREEN: Show examples of AI confusion]**

**VOICEOVER:**
> "Imagine telling your AI assistant you work at Microsoft, then later saying you work at Amazon. A normal chatbot will confidently tell you Amazon without acknowledging the change—or worse, randomly flip between the two. This is gaslighting."

**[Visual: Show chat bubbles with contradictory statements]**

---

## Scene 3: Solution Introduction (0:30-0:45)

**[SCREEN: Show CRT logo/interface]**

**VOICEOVER:**
> "CRT—Contradiction Resolution & Trust—solves this by tracking contradictions in a permanent ledger and enforcing mandatory disclosure when conflicts are detected."

**[Visual: Zoom into contradiction ledger showing tracked changes]**

---

## Scene 4: Live Demo - Part 1 (0:45-1:00)

**[SCREEN: Terminal/UI showing commands]**

**VOICEOVER:**
> "Let's see it in action. First, I'll tell CRT I work at Microsoft."

**[Type: "I work at Microsoft"]**

**[Show response: "Got it! I'll remember you work at Microsoft."]**

**VOICEOVER:**
> "Now I'll update that fact."

**[Type: "I work at Amazon now"]**

**[Show response with warning icon: "⚠️ Contradiction detected! I'll update to Amazon and preserve the history."]**

---

## Scene 5: Live Demo - Part 2 (1:00-1:15)

**[SCREEN: Show query and response]**

**VOICEOVER:**
> "Now when I ask where I work, CRT doesn't hide the contradiction—it discloses it transparently."

**[Type: "Where do I work?"]**

**[Show response: "You work at Amazon (changed from Microsoft)."]**

**[Visual: Highlight the disclosure in the response]**

---

## Scene 6: Ledger View (1:15-1:30)

**[SCREEN: Navigate to contradiction ledger]**

**VOICEOVER:**
> "Every contradiction is preserved in an audit trail. You can see exactly when the change happened, the old and new values, trust scores, and whether the disclosure was made."

**[Visual: Scroll through ledger showing:
- Contradiction ID
- Slot: employer
- Old value: Microsoft (trust: 0.9)
- New value: Amazon (trust: 0.9)
- Status: DISCLOSED ✓]**

---

## Scene 7: Two-Lane Architecture (1:30-1:45)

**[SCREEN: Show memory lane visualizer]**

**VOICEOVER:**
> "CRT uses a two-lane memory architecture. Facts with high trust go into the stable lane and are used in responses. Unconfirmed facts stay in the candidate lane until they're verified."

**[Visual: Show stable lane with high-trust facts, candidate lane with pending facts]**

---

## Scene 8: Integration & Call to Action (1:45-2:00)

**[SCREEN: Show code snippet]**

**VOICEOVER:**
> "Integrating CRT into your chatbot takes just a few lines of code. It works with LangChain, LlamaIndex, or any custom RAG pipeline. Plus, it's deterministic—no LLM calls, under 10 milliseconds per check, and zero API costs."

**[Visual: Show Python code example]**

```python
from groundcheck import GroundCheck

verifier = GroundCheck()
result = verifier.verify(statement, memories)

if result.requires_disclosure:
    print(result.expected_disclosure)
```

**VOICEOVER:**
> "Try CRT today and stop your AI from gaslighting users. Link in the description."

**[SCREEN: Show GitHub link and CTA]**

**[TEXT OVERLAY: github.com/blockhead22/AI_round2]**

---

## Visual Elements Checklist

### Required Screen Recordings

1. ✅ Split-screen comparison (Regular AI vs CRT AI)
2. ✅ Chat interface showing contradiction creation
3. ✅ Contradiction detection warning
4. ✅ Disclosure in response
5. ✅ Contradiction ledger panel
6. ✅ Memory lane visualizer
7. ✅ Code snippet with syntax highlighting

### Text Overlays

- [ ] "Traditional AI" vs "CRT AI" labels
- [ ] ⚠️ Warning icons for contradictions
- [ ] ✅ Success icons for disclosures
- [ ] "Contradiction Ledger" title
- [ ] "Stable Lane" and "Candidate Lane" labels
- [ ] GitHub URL
- [ ] Call to action

### Audio Notes

- Use clear, energetic voiceover
- Background music (subtle, modern)
- Sound effects:
  - Ding for contradiction detected
  - Swoosh for ledger entry
  - Success chime for disclosure

---

## B-Roll Suggestions

### Use Cases to Illustrate (5-10 seconds each)

1. **Healthcare:** Diagnosis change (positive → negative test)
2. **Customer Service:** Shipping address update
3. **Personal Assistant:** Job change tracking
4. **Legal:** Contradictory testimony

---

## Technical Setup

### Tools

- **Screen Recording:** OBS Studio or QuickTime
- **Video Editing:** DaVinci Resolve or Final Cut Pro
- **Voiceover:** Audacity or GarageBand
- **Graphics:** Figma for overlays

### Settings

- **Resolution:** 1920x1080 (1080p)
- **Frame Rate:** 30fps or 60fps
- **Format:** MP4 (H.264)
- **Aspect Ratio:** 16:9
- **Audio:** 44.1kHz, stereo

---

## Script Variations

### 30-Second Version (Social Media)

> "AI chatbots gaslight users by hiding contradictions. CRT fixes this. Tell it 'I work at Microsoft,' then 'I work at Amazon'—it'll disclose the change instead of hiding it. Every contradiction tracked forever. Link in bio."

### 60-Second Version (Quick Demo)

Combine Scenes 1, 4, 5, 6, and 8. Skip architecture explanation.

---

## Post-Production Checklist

- [ ] Color grade for consistency
- [ ] Add lower thirds with key terms
- [ ] Include captions/subtitles
- [ ] Add end screen with GitHub link
- [ ] Export in multiple formats (YouTube, Twitter, LinkedIn)
- [ ] Create thumbnail (1280x720)
- [ ] Write video description with links

---

## YouTube Metadata

**Title:**
"Stop AI Gaslighting: CRT Tracks Contradictions & Enforces Disclosure"

**Description:**
```
CRT (Contradiction Resolution & Trust) prevents AI chatbots from gaslighting users by tracking contradictions and enforcing mandatory disclosure.

🔍 Key Features:
✅ Contradiction detection & tracking
✅ Mandatory disclosure when conflicts detected
✅ Permanent audit trail (ledger)
✅ Two-lane memory architecture
✅ Deterministic (no LLM calls, <10ms)
✅ Works with LangChain, LlamaIndex, and custom RAG

📦 GitHub: https://github.com/blockhead22/AI_round2
📚 Docs: [link]
💬 Discord: [link]

Timestamps:
0:00 - The Problem
0:15 - How CRT Solves It
0:45 - Live Demo
1:30 - Architecture
1:45 - Integration

#AI #ChatGPT #LLM #MachineLearning #RAG #MemoryManagement
```

**Tags:**
AI, chatbot, LLM, RAG, contradiction tracking, disclosure, memory management, LangChain, LlamaIndex, gaslighting, AI safety, AI transparency

---

## Distribution Channels

1. **YouTube** (main platform)
2. **Twitter/X** (30-second cut)
3. **LinkedIn** (60-second cut, professional angle)
4. **Reddit** (r/MachineLearning, r/LocalLLaMA)
5. **Dev.to** (article with embedded video)
6. **GitHub README** (embedded at top)

---

**Script Version:** 1.0  
**Last Updated:** January 22, 2026
