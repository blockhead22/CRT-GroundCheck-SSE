"""Fix encoding artifacts in crt_rag.py"""

target = "d:/AI_round2/personal_agent/crt_rag.py"

with open(target, "r", encoding="utf-8") as f:
    content = f.read()

before_len = len(content)

# Fix em-dash mojibake that was partially fixed by curly-quote replacement
# After the curly-quote pass, the right curly quote (U+201D) in the mojibake
# was replaced with a straight quote, turning the sequence into: â€"
content = content.replace('â€"', ' - ')   # em dash -> spaced hyphen
content = content.replace('â€™', "'")     # apostrophe
content = content.replace('â€œ', '"')     # left double quote
content = content.replace('â†\'', '->')   # right arrow (if still present)
content = content.replace('\u2014', ' - ')  # em dash (proper unicode)
content = content.replace('\u2192', '->')   # right arrow (proper unicode)
content = content.replace('\u2013', ' - ')  # en dash
content = content.replace('\u2018', "'")    # left single quote
content = content.replace('\u2019', "'")    # right single quote
content = content.replace('\u201c', '"')    # left double quote
content = content.replace('\u201d', '"')    # right double quote

# Check for remaining non-ASCII in string literals (rough check)
lines = content.split('\n')
issues = []
for i, line in enumerate(lines, 1):
    for ch in line:
        if ord(ch) > 127:
            issues.append((i, repr(ch), line[:80]))
            break

if issues:
    print(f"WARNING: {len(issues)} lines still have non-ASCII chars:")
    for lineno, ch, preview in issues[:10]:
        print(f"  Line {lineno}: {ch} in {preview!r}")
else:
    print("No non-ASCII chars remaining")

with open(target, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Done. {before_len} -> {len(content)} chars")
