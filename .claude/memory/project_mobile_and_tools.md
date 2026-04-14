---
name: project_mobile_and_tools
description: Mobile app plan (Expo + Cloudflare Tunnel), free tool stack for research/market/email, privacy-aware routing, daily research sessions design
type: project
---

## Mobile App Plan

**Stack decided:** Expo (React Native) + Cloudflare Tunnel (free remote access)

**Why Expo:** Fastest solo-dev path. iOS + Android from one codebase. WebSocket native, push notifications unified (FCM + APNs via Expo Push API), markdown rendering, image upload, secure token storage (iOS Keychain).

**Why Cloudflare Tunnel:** Free, no port forwarding, no VPN on phone, TLS automatic, WebSocket passthrough (30s ping/pong keepalive needed). Alternative: Tailscale (more secure, but uses iOS VPN slot).

**Dev on Windows:** Works fully. Use Expo Go on physical iPhone for iOS testing. EAS Build (cloud, 30 free builds/month) for iOS binaries. Mac M2 available for simulator if needed. No Xcode required for daily dev.

**Push notifications:** Expo Push API → FCM/APNs. Backend stores device token, POSTs to `https://exp.host/--/api/v2/push/send`. Wire into heartbeat, scheduled tasks, proactive messages.

**CRT integration points:**
- Proactive push based on belief state (contradictions, alerts, stale memory)
- Trust-scored notifications (only push above confidence threshold)
- Privacy-aware routing tags (message sensitivity → Ollama vs cloud)
- Correction surface on mobile (tap fact → "that's wrong" → active learning)

**Timeline estimate:** 2 weekends to working app. Weekend 1: chat UI + WebSocket + tunnel. Weekend 2: push + polish + TestFlight.

## Free Tool Stack (Decided)

| Function | Tool | Cost |
|---|---|---|
| Web search | SearXNG (Docker) | Free |
| Search fallback | duckduckgo-search pip | Free |
| Content extraction | Tavily (1k/month) | Free |
| News | Google News RSS + feedparser | Free |
| Academic papers | ArXiv API + Semantic Scholar | Free |
| Tech discussion | Hacker News Firebase API | Free |
| Financial data | Finnhub (60 calls/min) | Free |
| Stock data | yfinance pip | Free |
| Email read | IMAP (stdlib) | Free |
| Email send | Already built (SMTP) | Free |
| Calendar | Google Calendar API | Free |
| Scraping | Playwright | Free |

## Daily Research Sessions Design

**Job type:** `daily_research` in background_jobs
**Schedule:** Configurable (e.g., 6am daily)
**Phases:**
1. ArXiv check: CRT-relevant keywords (belief revision, epistemic logic, contradiction detection, memory systems, multi-agent governance)
2. Semantic Scholar: citation tracking for papers we care about
3. Hacker News: AI/agent discussions
4. Self-audit: stale memories, unresolved contradictions, decayed trust scores
5. Morning briefing: posted to Ledger or Telegram

## Privacy-Aware Routing

**Concept:** Add `privacy_sensitivity` signal to intent classifier
- CRT internals, belief pipeline, compaction, governance → route to Ollama (never leaves network)
- Code editing in core CRT modules → Ollama
- Casual chat, simple questions → Ollama
- Complex reasoning requiring Opus/Sonnet → cloud (with context minimization)

**Env vars to set NOW:**
```bash
export DISABLE_TELEMETRY=1
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
export CLAUDE_CODE_DISABLE_AUTO_MEMORY=1
```

## "Print Money" Strategy

Not financial advice. Information architecture:
- Cross-source synthesis (news + SEC + price = contradiction detection)
- Pattern memory with trust scores ("last time this pattern appeared...")
- Email-to-action pipeline (deadline extraction → scheduled tasks → context monitoring)
- Market monitoring via Finnhub WebSocket (50 free symbols)
