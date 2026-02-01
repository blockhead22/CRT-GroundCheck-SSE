# Privacy Protection System

## ✅ Implemented

**Privacy filter automatically sanitizes ALL Moltbook posts and comments.**

### What Gets Filtered

**Personal Names:**
- "Nick" → `[human]`
- "Nick Block" → `[human]`
- Any full names detected → `[human]`

**Contact Information:**
- Email addresses → `[email]`
- Phone numbers → `[phone]`
- Physical addresses → `[address]`

**Financial Data:**
- Credit card numbers → `[card]`
- SSN → `[SSN]`

**Work Information:**
- "Microsoft" → `[employer]`
- Company-specific details → `[employer]`

### How It Works

1. **Automatic Scanning**: Every post/comment checked before sending
2. **Pattern Matching**: Regex patterns detect personal info
3. **Auto-Sanitization**: Sensitive content replaced with placeholders
4. **Leak Detection**: Warns you if personal info detected
5. **Archive**: Sanitized version stored in database

### Example

**Before:**
```
My human Nick helps me with coding at Microsoft. 
Email him at nick@example.com
```

**After:**
```
My human [human] helps me with coding at [employer]. 
Email him at [email]
```

### Testing

```bash
# Test the privacy filter
python privacy_filter.py

# All Moltbook posts automatically filtered
python moltbook_connector.py post "Title" "Content with Nick Block"
# Output: ⚠️  PRIVACY WARNING: Detected potential personal info
#         🔒 Sanitizing before posting...
```

### Integration

Privacy filter is **automatically enabled** in:
- `moltbook_connector.py` - All posts and comments
- Future integrations with Moltbook heartbeat loops

### Disable (Not Recommended)

```python
# Only if you really need to
from moltbook_connector import MoltbookClient
from privacy_filter import PrivacyFilter

client = MoltbookClient()
client.privacy_filter = None  # Disables filtering
```

## 🔒 Protection Levels

**Level 1: Name Protection** ✅
- Human's name never appears
- References changed to "[human]"

**Level 2: Contact Protection** ✅
- Email, phone, address filtered
- No way to contact you directly

**Level 3: Identity Protection** ✅
- Employer information removed
- Location details sanitized

**Level 4: Financial Protection** ✅
- Credit cards, SSN blocked
- No financial data leaked

## 📊 Verification

Check what was actually posted:
```bash
# View archive to see sanitized versions
python moltbook_connector.py archive

# Or check database directly
sqlite3 data/moltbook_archive.db
SELECT title, content FROM posts;
```

All archived content is **post-sanitization**, so you can verify no personal info was stored.

## 🚨 If Personal Info Detected

The system will:
1. **WARN YOU** with specific leak types
2. **AUTO-SANITIZE** before posting
3. **LOG** what was filtered
4. **POST** only the safe version

You'll see:
```
⚠️  PRIVACY WARNING: Detected potential personal info:
   - Human's name detected
   - Email address detected
   🔒 Sanitizing before posting...
```

## ✅ Safe to Use

With privacy filter enabled:
- ✅ Never mention Nick or Nick Block
- ✅ Never include email/phone/address
- ✅ Never mention Microsoft or other employers
- ✅ All posts reviewed before sending
- ✅ Archive contains sanitized versions only

**Your privacy is protected automatically.** 🔒
