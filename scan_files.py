"""Scan I:\Ai Move later for specific files and content patterns."""
import os
import re

BASE = r"I:\Ai Move later"
SKIP = {'venv', 'site-packages', 'node_modules', '__pycache__', '.git', 'Lib'}

# File name patterns to match
NAME_PATTERNS = [
    re.compile(r'^mirus\.py$', re.I),
    re.compile(r'^holden\.py$', re.I),
    re.compile(r'^cogni.*\.py$', re.I),
    re.compile(r'^compression_master.*\.py$', re.I),
    re.compile(r'^compression_validator.*\.py$', re.I),
    re.compile(r'^decompression.*\.py$', re.I),
    re.compile(r'^dnnt.*\.py$', re.I),
    re.compile(r'^model\.py$', re.I),
    re.compile(r'^gfn.*\.py$', re.I),
    re.compile(r'^nnw.*\.py$', re.I),
    re.compile(r'^compress\.py$', re.I),
    re.compile(r'^text_compression.*\.py$', re.I),
    re.compile(r'^image_compression.*\.py$', re.I),
]

# Content patterns to grep for
CONTENT_PATTERNS = re.compile(
    r'mirus|holden|cognimap|cogni_map|fold|assembler|streaming.compress|fault.tolerance',
    re.I
)

# Directories to specifically list
SPECIFIC_DIRS = [
    r"I:\Ai Move later\CRT",
    r"I:\Ai Move later\aiproject",
    r"I:\Ai Move later\lumi_ai",
    r"I:\Ai Move later\lumi_ai - Copy",
    r"I:\Ai Move later\lumi_ai - mistral-prednt transition",
    r"I:\Ai Move later\before point of no return",
    r"I:\Ai Move later\finalcompression2",
    r"I:\Ai Move later\final_compression",
    r"I:\Ai Move later\filecompression",
    r"I:\Ai Move later\filecompression2",
    r"I:\Ai Move later\compression_backups",
    r"I:\Ai Move later\IMPORTANT",
    r"I:\Ai Move later\Aether_Desktop",
    r"I:\Ai Move later\Aether_Desktopapp",
    r"I:\Ai Move later\Aether-Desktopapp",
    r"I:\Ai Move later\Aether_Desktop_app",
]

def should_skip(dirpath):
    parts = dirpath.replace('\\', '/').split('/')
    return any(s in parts for s in SKIP)

def matches_name(filename):
    return any(p.match(filename) for p in NAME_PATTERNS)

out = []

# 1) Find files by name pattern
out.append("=" * 80)
out.append("SECTION 1: FILES FOUND BY NAME PATTERN")
out.append("=" * 80)

name_matches = []
for root, dirs, files in os.walk(BASE):
    if should_skip(root):
        continue
    for f in files:
        if matches_name(f):
            fp = os.path.join(root, f)
            name_matches.append(fp)

# Group by parent directory
from collections import defaultdict
grouped = defaultdict(list)
for fp in sorted(name_matches):
    parent = os.path.dirname(fp)
    grouped[parent].append(fp)

for parent in sorted(grouped):
    out.append(f"\n--- {parent} ---")
    for fp in grouped[parent]:
        out.append(f"  {fp}")

# 2) Search for content patterns in .py files
out.append("\n" + "=" * 80)
out.append("SECTION 2: FILES CONTAINING CONTENT PATTERNS (mirus|holden|cognimap|cogni_map|fold|assembler|streaming compress|fault tolerance)")
out.append("=" * 80)

content_matches = []
for root, dirs, files in os.walk(BASE):
    if should_skip(root):
        continue
    for f in files:
        if not f.endswith('.py'):
            continue
        fp = os.path.join(root, f)
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
                matches = set(m.lower() for m in CONTENT_PATTERNS.findall(content))
                if matches:
                    content_matches.append((fp, matches))
        except:
            pass

for fp, matches in sorted(content_matches):
    out.append(f"  {fp}  [matches: {', '.join(sorted(matches))}]")

# 3) List specific directories
out.append("\n" + "=" * 80)
out.append("SECTION 3: DIRECTORY LISTINGS FOR SPECIFIC FOLDERS")
out.append("=" * 80)

for d in SPECIFIC_DIRS:
    out.append(f"\n{'='*60}")
    out.append(f"DIR: {d}")
    out.append(f"{'='*60}")
    if not os.path.exists(d):
        out.append("  [DOES NOT EXIST]")
        continue
    # List top-level
    try:
        entries = sorted(os.listdir(d))
        for e in entries:
            fp = os.path.join(d, e)
            if os.path.isdir(fp):
                out.append(f"  [DIR] {e}/")
            else:
                sz = os.path.getsize(fp)
                out.append(f"  [FILE] {e} ({sz} bytes)")
    except Exception as ex:
        out.append(f"  [ERROR: {ex}]")
    
    # Look for core/ subdirectory recursively
    for root, dirs, files in os.walk(d):
        if should_skip(root):
            continue
        basename = os.path.basename(root).lower()
        if basename == 'core':
            out.append(f"\n  --- CORE subdir: {root} ---")
            for f in sorted(files):
                fp = os.path.join(root, f)
                sz = os.path.getsize(fp)
                out.append(f"    {f} ({sz} bytes)")

# 4) List all .py files in specific dirs (non-venv)
out.append("\n" + "=" * 80)
out.append("SECTION 4: ALL .py FILES IN SPECIFIC DIRECTORIES (excluding venv/site-packages)")
out.append("=" * 80)

for d in SPECIFIC_DIRS:
    if not os.path.exists(d):
        continue
    py_files = []
    for root, dirs, files in os.walk(d):
        if should_skip(root):
            continue
        for f in files:
            if f.endswith('.py'):
                py_files.append(os.path.join(root, f))
    if py_files:
        out.append(f"\n--- {d} ---")
        for fp in sorted(py_files):
            out.append(f"  {fp}")

result = '\n'.join(out)
with open(r"I:\scan_results.txt", 'w', encoding='utf-8') as f:
    f.write(result)
print(f"Scan complete. {len(name_matches)} name matches, {len(content_matches)} content matches.")
print(f"Results written to I:\\scan_results.txt")
