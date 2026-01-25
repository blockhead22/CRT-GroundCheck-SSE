# Dynamic Fact Storage & Resolution Pattern Guide

## Overview

This guide explains the new capabilities added to the CRT system for dynamic fact storage, expanded resolution patterns, and enhanced trace logging.

## Dynamic Fact Storage

### What Changed?

The system previously had a hardcoded limit of ~20 fact categories. Now it supports **unlimited fact categories** that can be created dynamically based on user input.

### Supported Dynamic Categories

#### 1. Structured Facts (FACT: syntax)

**Core Slots** (always supported):
- `name`, `employer`, `title`, `location`, `pronouns`, `communication_style`, `goals`, `favorite_color`

**Dynamic Patterns** (NEW - automatically supported):
- `favorite_*` - Any favorite category (e.g., `favorite_snack`, `favorite_movie`, `favorite_band`)
- `*_preference` - Any preference (e.g., `workspace_preference`, `music_preference`)
- `pref_*` - Preference prefix (e.g., `pref_communication`, `pref_workspace`)
- `my_*` - Personal attributes (e.g., `my_hometown`, `my_hobby`)
- `*_name` - Name attributes (e.g., `company_name`, `project_name`)
- `*_type` - Type attributes (e.g., `database_type`, `framework_type`)
- `*_status` - Status attributes (e.g., `project_status`, `task_status`)
- `*_count` - Count attributes (e.g., `vacation_count`, `project_count`)

#### 2. Natural Language Extraction

**Generic Favorite Pattern**:
```
"My favorite X is Y"
```

Examples:
- "My favorite snack is popcorn" → `favorite_snack = popcorn`
- "My favorite movie is The Matrix" → `favorite_movie = The Matrix`
- "My favourite book is 1984" → `favorite_book = 1984`

### Examples

#### Example 1: Favorite Snack (From Problem Statement)

**User:** "My favorite snack is popcorn"

**System:** Automatically creates `favorite_snack` category and stores "popcorn"

**User:** "I changed snack to pretzels"

**System:** Detects resolution pattern "changed to", resolves contradiction, updates to "pretzels"

#### Example 2: Multiple Dynamic Facts

```
User: "FACT: favorite_snack = popcorn"
System: ✓ Stored favorite_snack = popcorn

User: "FACT: favorite_drink = coffee"
System: ✓ Stored favorite_drink = coffee

User: "FACT: favorite_sport = basketball"
System: ✓ Stored favorite_sport = basketball

User: "My favorite movie is The Matrix"
System: ✓ Stored favorite_movie = The Matrix
```

#### Example 3: Custom Categories

```
User: "FACT: my_hometown = Seattle"
System: ✓ Stored my_hometown = Seattle

User: "FACT: workspace_preference = quiet"
System: ✓ Stored workspace_preference = quiet

User: "FACT: project_status = in progress"
System: ✓ Stored project_status = in progress
```

## Resolution Patterns

### What Changed?

The system now supports **24 resolution patterns** (13 new patterns added), making it easier for users to resolve contradictions naturally.

### Pattern Categories

#### 1. Explicit Correctness
- "X is correct"
- "X was right"
- "That is accurate"
- "The correct answer/value/status"

#### 2. Revision Markers
- "Actually, it's X"
- "I meant X"

#### 3. Job/Location Changes
- "I switched jobs"
- "I changed to X"
- "I moved to X"
- "Now working at X"

#### 4. Keep Old Value (NEW)
- "keep the old value"
- "keep old"
- "keep the original"
- "keep the first one"
- "stick with the old one"
- "stick with previous"

#### 5. Choose Value (NEW)
- "stick with X"
- "go with X"
- "prefer X"
- "choose X"
- "select X"
- "pick X"

#### 6. Update/Replace (NEW)
- "use X instead"
- "replace with X"
- "override with X"
- "update to X"

#### 7. Discard
- "ignore the old one"
- "ignore that"

### Examples

#### Example 1: Keep Old Value

```
User: "I work at Microsoft"
User: "I work at Google"
System: [Detects contradiction]

User: "keep the old value"
System: ✓ Resolved - keeping "Microsoft"
```

#### Example 2: Preference Choice

```
User: "My favorite color is blue"
User: "My favorite color is red"
System: [Detects contradiction]

User: "go with blue"
System: ✓ Resolved - chose "blue"
```

#### Example 3: Update/Override

```
User: "Project status is planning"
User: "Project status is active"
System: [Detects contradiction]

User: "update to active"
System: ✓ Resolved - updated to "active"
```

### Extending Patterns

You can add custom patterns at runtime:

```python
from personal_agent.resolution_patterns import add_custom_pattern

# Add a custom pattern
add_custom_pattern(r'\bswap\s+to\s+([A-Za-z0-9\s]+)')

# Now this works:
# User: "swap to Google"
# System: ✓ Resolution pattern matched
```

## Trace Logging

### What Changed?

Added detailed trace logging for contradiction resolution events, making it easier to debug and research contradiction handling.

### Log Format

Logs are written to `ai_logs/contradiction_trace.log` with the format:

```
YYYY-MM-DD HH:MM:SS | LEVEL | MESSAGE
```

### Logged Events

#### 1. Contradiction Detection
```
=== CONTRADICTION DETECTED ===
Ledger ID: led_abc123
Type: CONFLICT
Drift: 0.8500
Affected Slots: employer
Old Memory [mem_old]: I work at Microsoft
New Memory [mem_new]: I work at Google
```

#### 2. Resolution Attempt
```
=== RESOLUTION ATTEMPT ===
User Input: Google is correct
Open Contradictions: 3
Matched Patterns (2):
  1. Pattern: \b(is|was)\s+(correct|right)
     Match: 'is correct'
```

#### 3. Resolution Matched
```
=== RESOLUTION MATCHED ===
Ledger ID: led_abc123
Type: CONFLICT
Slot: employer
  Old Value: Microsoft
  New Value: Google
  Chosen: Google
Resolution Method: user_chose_new
```

#### 4. Ledger Update
```
=== LEDGER UPDATE ===
Ledger ID: led_abc123
Status: open -> resolved
Method: nl_resolution
Chosen Memory: mem_new
```

#### 5. Resolution Complete
```
=== RESOLUTION SUCCESS ===
Ledger ID: led_abc123
Details: Chose mem_new, deprecated mem_old
```

#### 6. Resolution Summary
```
=== RESOLUTION SUMMARY ===
Open Before: 3
Open After: 1
Resolved: 2
Time: 0.050s
```

### Configuring Trace Logging

```python
from personal_agent.contradiction_trace_logger import configure_trace_logging

# Enable with custom settings
configure_trace_logging(
    enabled=True,
    log_file="custom_path/trace.log",
    console_output=True,  # Also log to console
    log_level=logging.DEBUG  # More detailed logging
)

# Disable
configure_trace_logging(enabled=False)
```

## Testing

### Running Tests

```bash
# Test dynamic fact storage
pytest tests/test_dynamic_fact_storage.py -v

# Test resolution patterns
pytest tests/test_resolution_patterns.py -v

# Test trace logging
pytest tests/test_contradiction_trace_logger.py -v

# Run all new tests
pytest tests/test_dynamic_fact_storage.py tests/test_resolution_patterns.py tests/test_contradiction_trace_logger.py -v
```

### Test Coverage

- **Dynamic Facts**: 20+ test cases covering all dynamic patterns
- **Resolution Patterns**: 40+ test cases covering all 24 patterns
- **Trace Logging**: 20+ test cases covering all log events

## Migration Guide

### For Existing Users

No migration needed! All existing functionality works exactly as before. The new features are additive:

1. **Existing hardcoded slots still work** (name, employer, location, etc.)
2. **Existing resolution patterns still work** ("is correct", "actually", etc.)
3. **Logging is optional** and disabled by default

### To Start Using New Features

1. **Use dynamic facts**: Just use the `FACT:` syntax or natural language with new categories
2. **Use new resolution patterns**: They work automatically - just use natural language
3. **Enable trace logging**: Call `configure_trace_logging(enabled=True)` if you want detailed logs

## Best Practices

### Dynamic Facts

1. Use structured `FACT:` syntax for explicit category creation
2. Use natural language "My favorite X" for user-friendly input
3. Keep category names descriptive and consistent

### Resolution Patterns

1. Use natural, conversational language
2. Be specific when choosing between values
3. Patterns are case-insensitive - use whatever feels natural

### Trace Logging

1. Enable logging during development and debugging
2. Review logs to understand resolution behavior
3. Use logs for research and pattern analysis
4. Disable in production if not needed (to save disk space)

## API Reference

### fact_slots.py

```python
from personal_agent.fact_slots import extract_fact_slots

# Extract facts from text
facts = extract_fact_slots("FACT: favorite_snack = popcorn")
# Returns: {'favorite_snack': ExtractedFact(slot='favorite_snack', value='popcorn', normalized='popcorn')}
```

### resolution_patterns.py

```python
from personal_agent.resolution_patterns import (
    has_resolution_intent,
    get_matched_patterns,
    add_custom_pattern,
    get_all_patterns
)

# Check if text has resolution intent
has_intent = has_resolution_intent("Google is correct")  # True

# Get matched patterns with details
matches = get_matched_patterns("Google is correct")
# Returns: [{'pattern': '...', 'match': 'is correct', ...}]

# Add custom pattern
add_custom_pattern(r'\bswap\s+to\s+([A-Za-z0-9\s]+)')

# Get all patterns
all_patterns = get_all_patterns()  # Returns list of 24+ patterns
```

### contradiction_trace_logger.py

```python
from personal_agent.contradiction_trace_logger import get_trace_logger, configure_trace_logging

# Configure global logging
configure_trace_logging(
    enabled=True,
    log_file="ai_logs/contradiction_trace.log",
    console_output=False
)

# Get logger instance
logger = get_trace_logger()

# Log events (done automatically by CRT system)
logger.log_contradiction_detected(...)
logger.log_resolution_attempt(...)
logger.log_resolution_matched(...)
logger.log_ledger_update(...)
logger.log_resolution_complete(...)
logger.log_resolution_summary(...)
```

## Troubleshooting

### Dynamic Facts Not Working

**Issue**: Structured facts not being recognized

**Solution**: Check that your slot name matches one of the dynamic patterns:
- Starts with `favorite_`, `my_`, or `pref_`
- Ends with `_preference`, `_name`, `_type`, `_status`, or `_count`

### Resolution Patterns Not Matching

**Issue**: Natural language not resolving contradiction

**Solution**: 
1. Check that your phrase matches one of the 24 patterns
2. Use `get_matched_patterns()` to see what's matching
3. Add a custom pattern if needed

### Trace Logs Not Appearing

**Issue**: No log file created

**Solution**:
1. Ensure trace logging is enabled: `configure_trace_logging(enabled=True)`
2. Check log file path is writable
3. Verify log level is appropriate (INFO or DEBUG)

## Performance Considerations

- **Dynamic fact extraction**: Same performance as hardcoded slots (regex-based)
- **Resolution pattern matching**: O(n) where n = number of patterns (24)
- **Trace logging**: Minimal overhead when enabled, zero when disabled

## Security Considerations

- **Input validation**: All dynamic slot names are validated (alphanumeric + underscore only)
- **SQL injection**: Parameterized queries used throughout
- **Log injection**: User input is truncated in logs to prevent log injection

## Future Enhancements

Potential future improvements:
1. Machine learning-based pattern matching
2. User-defined pattern templates via config file
3. Pattern usage analytics and optimization
4. Multi-lingual pattern support
5. Interactive pattern testing tool
