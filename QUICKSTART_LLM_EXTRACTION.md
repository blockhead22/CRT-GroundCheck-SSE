# Quick Start: LLM-Based Fact Extraction

## Enable LLM Extraction

### 1. Set OpenAI API Key
```powershell
# PowerShell
$env:OPENAI_API_KEY = "sk-your-api-key-here"

# Or add to .env file
OPENAI_API_KEY=sk-your-api-key-here
```

### 2. Test It Works
```python
from personal_agent.user_profile import GlobalUserProfile

profile = GlobalUserProfile(use_llm_extraction=True)

# Test with complex fact
result = profile.update_from_text(
    "I have two pets: a healthy dog and a sick cat",
    thread_id="test"
)

print(result)
# Should extract 2 pet facts with health context
```

### 3. Run Test Suite
```bash
python test_llm_extraction.py
```

## Without API Key (Regex Fallback)

The system automatically falls back to regex patterns if:
- No OPENAI_API_KEY set
- API key invalid
- LLM request fails
- Dependencies missing

```python
profile = GlobalUserProfile(use_llm_extraction=True)  # Will auto-fallback
# OR explicitly disable:
profile = GlobalUserProfile(use_llm_extraction=False)  # Regex only
```

## What Gets Extracted

### Simple Cases (Regex Handles)
- "My name is John" → `name: John`
- "I work at Google" → `employer: Google`
- "I live in Seattle" → `location: Seattle`

### Complex Cases (Needs LLM)
- "My favorite colors are blue and green" → 2 favorite_color facts
- "I have a healthy dog and a sick cat" → 2 pet facts with health context
- "I work full-time at Google and part-time as a consultant" → 2 employer/occupation facts
- "I used to love woodworking but now prefer pottery" → deprecated + new hobby

## Integration with Existing Code

No changes needed! The system is backward compatible:

```python
# This already uses the new system:
user_profile.update_from_text(user_query, thread_id="current")

# Same retrieval:
facts = user_profile.get_all_facts_for_slot('pet')
```

## Monitoring

Check logs to see which extraction method was used:

```
[LLM_PROFILE_UPDATE] Extracted 2 tuples from 'I have two pets...'
[REGEX_PROFILE_UPDATE] Extracted 1 facts from 'My name is John'
```

## Cost Tracking

With `gpt-4o-mini`:
- ~$0.15 per 1M tokens
- Typical extraction: 50-500 tokens
- Cost per message: ~$0.000015 - $0.0001
- 10,000 messages = ~$1

Very affordable for personal use!

## Troubleshooting

### "LLM extraction unavailable"
- Check OPENAI_API_KEY is set
- Verify API key is valid
- Check internet connection
- System auto-falls back to regex

### "IntegrityError"
- Duplicate facts being inserted
- System auto-handles by deleting inactive duplicates
- Should self-resolve

### No facts extracted
- Check if temporal filter is blocking ("I'm working on X tonight")
- Try more explicit phrasing: "I like pottery" instead of "I'm into pottery"
- Check logs for extraction attempts

## Next Steps

1. Set API key
2. Run test_llm_extraction.py
3. Chat with system: "I have two pets: a dog and a cat"
4. New thread: "Tell me about my pets"
5. Should remember both pets!

## Disable LLM Extraction

If you want regex-only (no API calls):

```python
# In crt_rag.py or wherever GlobalUserProfile is initialized:
self.user_profile = GlobalUserProfile(use_llm_extraction=False)
```

Or set environment variable:
```powershell
$env:DISABLE_LLM_EXTRACTION = "1"
```

(Note: This env var would need to be added to the code)
