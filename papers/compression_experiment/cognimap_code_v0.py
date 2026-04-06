"""CogniMap Code Compression Experiment

Compress Python source code using semantic importance scoring.

Importance for code:
  - Function signatures, class definitions = HIGH (structural)
  - Core logic (conditionals, returns, assignments) = HIGH
  - Comments, docstrings = MEDIUM (readable but reconstructible)
  - Imports, boilerplate = LOW (predictable, highly compressible)
  - Whitespace, formatting = LOWEST (perfectly predictable)

The CogniMap records: which compression strategy was used per code block,
enabling lossless reconstruction of the exact original file.

Run: .venv/Scripts/python papers/compression_experiment/cognimap_code_v0.py
"""

import sys
import os
import zlib
import hashlib
import time
import struct
import json
from pathlib import Path
from io import BytesIO

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ── Code Line Classification ──────────────────────────────────────────

def classify_line(line: str, in_docstring: bool) -> tuple:
    """Classify a code line by semantic importance.

    Returns (category, importance, in_docstring_after).
    Categories: blank, comment, docstring, import, decorator,
                def, class, logic, assignment, boilerplate, string
    """
    stripped = line.strip()

    # Track docstring state
    if '"""' in stripped or "'''" in stripped:
        count = stripped.count('"""') + stripped.count("'''")
        if in_docstring:
            return ("docstring", 0.3, count % 2 == 1)  # closing
        else:
            if count >= 2:
                return ("docstring", 0.3, False)  # single-line docstring
            return ("docstring", 0.3, True)  # opening

    if in_docstring:
        return ("docstring", 0.3, True)

    if not stripped:
        return ("blank", 0.0, False)

    if stripped.startswith("#"):
        return ("comment", 0.3, False)

    if stripped.startswith("import ") or stripped.startswith("from "):
        return ("import", 0.2, False)

    if stripped.startswith("@"):
        return ("decorator", 0.5, False)

    if stripped.startswith("def "):
        return ("def", 0.9, False)

    if stripped.startswith("class "):
        return ("class", 0.9, False)

    if stripped.startswith("return "):
        return ("logic", 0.8, False)

    if stripped.startswith(("if ", "elif ", "else:", "for ", "while ", "try:", "except", "finally:", "with ")):
        return ("logic", 0.7, False)

    if stripped.startswith(("raise ", "yield ", "assert ")):
        return ("logic", 0.7, False)

    if "=" in stripped and not stripped.startswith(("==", "!=", "<=", ">=")):
        return ("assignment", 0.6, False)

    if stripped.startswith(("print(", "logger.", "logging.")):
        return ("boilerplate", 0.2, False)

    if stripped.startswith(("pass", "continue", "break")):
        return ("boilerplate", 0.1, False)

    return ("logic", 0.6, False)


def analyze_file(filepath: Path) -> dict:
    """Analyze a Python file and classify each line."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    lines = content.split("\n")
    classified = []
    in_docstring = False
    category_counts = {}

    for line in lines:
        cat, importance, in_docstring = classify_line(line, in_docstring)
        classified.append({
            "text": line,
            "category": cat,
            "importance": importance,
        })
        category_counts[cat] = category_counts.get(cat, 0) + 1

    return {
        "path": str(filepath.relative_to(REPO_ROOT)),
        "lines": classified,
        "total_lines": len(lines),
        "raw_bytes": len(content.encode("utf-8")),
        "categories": category_counts,
    }


# ── Importance-Weighted Code Compression ──────────────────────────────

def compress_code_uniform(content: bytes) -> bytes:
    """Standard zlib compression — uniform, no importance awareness."""
    return zlib.compress(content, 9)

def compress_code_cognimap(lines: list) -> tuple:
    """CogniMap code compression: group lines by importance tier,
    compress each tier with different strategies.

    High importance: stored with full context (low compression)
    Medium importance: compressed normally
    Low importance: aggressive compression, pattern dedup
    """
    # Group lines by importance tier
    high_lines = []   # importance >= 0.7
    med_lines = []    # importance 0.3-0.7
    low_lines = []    # importance < 0.3

    line_map = []  # Records which tier and index each line maps to

    for i, line_info in enumerate(lines):
        imp = line_info["importance"]
        text = line_info["text"]

        if imp >= 0.7:
            line_map.append(("H", len(high_lines)))
            high_lines.append(text)
        elif imp >= 0.3:
            line_map.append(("M", len(med_lines)))
            med_lines.append(text)
        else:
            line_map.append(("L", len(low_lines)))
            low_lines.append(text)

    # Compress each tier
    high_data = "\n".join(high_lines).encode("utf-8")
    med_data = "\n".join(med_lines).encode("utf-8")
    low_data = "\n".join(low_lines).encode("utf-8")

    # For low-importance: deduplicate identical lines first
    low_unique = list(set(low_lines))
    low_index = {line: idx for idx, line in enumerate(low_unique)}
    low_refs = [low_index[line] for line in low_lines]

    low_unique_data = "\n".join(low_unique).encode("utf-8")
    low_refs_data = struct.pack(f"{len(low_refs)}H", *low_refs) if low_refs else b""

    compressed_high = zlib.compress(high_data, 6)   # Less aggressive — preserve
    compressed_med = zlib.compress(med_data, 9)     # Standard
    compressed_low_unique = zlib.compress(low_unique_data, 9)  # Aggressive on unique set
    compressed_low_refs = zlib.compress(low_refs_data, 9)       # Index is very compressible

    # Line map: encode as simple byte arrays
    # tier as uint8 (0=H, 1=M, 2=L), index as uint16
    tier_bytes = bytes([{"H": 0, "M": 1, "L": 2}[t] for t, _ in line_map])
    idx_array = np.array([idx for _, idx in line_map], dtype=np.uint16)
    map_data = tier_bytes + idx_array.tobytes()
    compressed_map = zlib.compress(map_data, 9)

    # Pack everything
    header = struct.pack("IIIII",
        len(compressed_high), len(compressed_med),
        len(compressed_low_unique), len(compressed_low_refs),
        len(compressed_map))

    total = header + compressed_high + compressed_med + compressed_low_unique + compressed_low_refs + compressed_map

    stats = {
        "high_lines": len(high_lines),
        "med_lines": len(med_lines),
        "low_lines": len(low_lines),
        "low_unique": len(low_unique),
        "low_dedup_ratio": len(low_lines) / max(len(low_unique), 1),
        "sizes": {
            "high": len(compressed_high),
            "med": len(compressed_med),
            "low_unique": len(compressed_low_unique),
            "low_refs": len(compressed_low_refs),
            "map": len(compressed_map),
            "total": len(total),
        },
        "raw_sizes": {
            "high": len(high_data),
            "med": len(med_data),
            "low": len(low_data),
        }
    }

    return total, stats


def decompress_code_cognimap(compressed: bytes) -> str:
    """Decompress CogniMap code back to exact original."""
    offset = 0
    h_len, m_len, lu_len, lr_len, map_len = struct.unpack_from("IIIII", compressed, offset)
    offset += 20

    high_data = zlib.decompress(compressed[offset:offset+h_len]); offset += h_len
    med_data = zlib.decompress(compressed[offset:offset+m_len]); offset += m_len
    low_unique_data = zlib.decompress(compressed[offset:offset+lu_len]); offset += lu_len
    low_refs_data = zlib.decompress(compressed[offset:offset+lr_len]); offset += lr_len
    map_data = zlib.decompress(compressed[offset:offset+map_len])

    high_lines = high_data.decode("utf-8").split("\n") if high_data else []
    med_lines = med_data.decode("utf-8").split("\n") if med_data else []
    low_unique = low_unique_data.decode("utf-8").split("\n") if low_unique_data else []

    n_low_refs = len(low_refs_data) // 2
    low_refs = list(struct.unpack(f"{n_low_refs}H", low_refs_data)) if low_refs_data else []
    low_lines = [low_unique[ref] if ref < len(low_unique) else "" for ref in low_refs]

    # Reconstruct from map
    # First half is tier bytes, second half is uint16 indices
    # Total map_data = n_entries bytes (tiers) + n_entries * 2 bytes (indices)
    # So n_entries = len(map_data) / 3
    n_entries = len(map_data) // 3
    tier_bytes = map_data[:n_entries]
    idx_array = np.frombuffer(map_data[n_entries:n_entries + n_entries * 2], dtype=np.uint16)

    result_lines = []
    for i in range(n_entries):
        tier = tier_bytes[i]  # 0=H, 1=M, 2=L
        idx = int(idx_array[i])
        if tier == 0:
            result_lines.append(high_lines[idx] if idx < len(high_lines) else "")
        elif tier == 1:
            result_lines.append(med_lines[idx] if idx < len(med_lines) else "")
        else:
            result_lines.append(low_lines[idx] if idx < len(low_lines) else "")

    return "\n".join(result_lines)


# ── Main ───────────────────────────────────────────────────────────────

def run_experiment():
    print("=" * 70)
    print("CogniMap Code Compression Experiment")
    print("=" * 70)

    # Collect Python files from the codebase
    target_dirs = [
        REPO_ROOT / "personal_agent",
        REPO_ROOT / "routes",
    ]

    all_files = []
    for d in target_dirs:
        if d.exists():
            for f in sorted(d.glob("*.py")):
                if f.stat().st_size > 0:
                    all_files.append(f)

    print(f"\nFound {len(all_files)} Python files in personal_agent/ + routes/")

    total_raw = 0
    total_zlib = 0
    total_cogni = 0
    total_lines = 0
    global_categories = {}
    file_results = []

    for filepath in all_files:
        analysis = analyze_file(filepath)
        if not analysis:
            continue

        raw_bytes = analysis["raw_bytes"]
        content = filepath.read_bytes()

        # Uniform compression
        uniform = compress_code_uniform(content)

        # CogniMap compression
        cogni_compressed, cogni_stats = compress_code_cognimap(analysis["lines"])

        # Verify lossless
        reconstructed = decompress_code_cognimap(cogni_compressed)
        original_text = content.decode("utf-8", errors="replace")
        is_identical = reconstructed == original_text

        total_raw += raw_bytes
        total_zlib += len(uniform)
        total_cogni += len(cogni_compressed)
        total_lines += analysis["total_lines"]

        for cat, count in analysis["categories"].items():
            global_categories[cat] = global_categories.get(cat, 0) + count

        improvement = (1 - len(cogni_compressed) / len(uniform)) * 100

        file_results.append({
            "name": analysis["path"],
            "lines": analysis["total_lines"],
            "raw": raw_bytes,
            "zlib": len(uniform),
            "cogni": len(cogni_compressed),
            "improvement": improvement,
            "lossless": is_identical,
            "high": cogni_stats["high_lines"],
            "med": cogni_stats["med_lines"],
            "low": cogni_stats["low_lines"],
            "dedup": cogni_stats["low_dedup_ratio"],
        })

    # ── Per-file results ──────────────────────────────────────────────

    print(f"\n" + "-" * 70)
    print("PER-FILE RESULTS")
    print("-" * 70)
    print(f"  {'File':45s} {'Lines':>6s} {'Raw':>7s} {'zlib':>7s} {'Cogni':>7s} {'vs zlib':>8s} {'OK':>3s}")
    print(f"  {'-'*45} {'-'*6} {'-'*7} {'-'*7} {'-'*7} {'-'*8} {'-'*3}")

    for r in sorted(file_results, key=lambda x: -x["improvement"]):
        print(f"  {r['name']:45s} {r['lines']:6d} {r['raw']/1024:6.0f}K {r['zlib']/1024:6.0f}K "
              f"{r['cogni']/1024:6.0f}K {r['improvement']:+7.1f}% {'Y' if r['lossless'] else 'N'}")

    # ── Aggregate results ─────────────────────────────────────────────

    print(f"\n" + "-" * 70)
    print("AGGREGATE RESULTS")
    print("-" * 70)
    print(f"  Total files:  {len(file_results)}")
    print(f"  Total lines:  {total_lines}")
    print(f"  Raw size:     {total_raw/1024:.0f} KB")
    print(f"  zlib size:    {total_zlib/1024:.0f} KB ({total_raw/total_zlib:.1f}x)")
    print(f"  CogniMap:     {total_cogni/1024:.0f} KB ({total_raw/total_cogni:.1f}x)")

    overall_improvement = (1 - total_cogni / total_zlib) * 100
    print(f"  vs zlib:      {'BETTER' if overall_improvement > 0 else 'WORSE'} by {abs(overall_improvement):.1f}%")

    lossless_count = sum(1 for r in file_results if r["lossless"])
    print(f"  Lossless:     {lossless_count}/{len(file_results)} files")

    # ── Category distribution ─────────────────────────────────────────

    print(f"\n" + "-" * 70)
    print("CODE CATEGORY DISTRIBUTION")
    print("-" * 70)
    for cat, count in sorted(global_categories.items(), key=lambda x: -x[1]):
        pct = count / total_lines * 100
        imp = {"blank": 0.0, "comment": 0.3, "docstring": 0.3, "import": 0.2,
               "decorator": 0.5, "def": 0.9, "class": 0.9, "logic": 0.7,
               "assignment": 0.6, "boilerplate": 0.2, "string": 0.4}.get(cat, 0.5)
        print(f"  {cat:12s}: {count:6d} lines ({pct:5.1f}%) importance={imp}")

    # ── Deduplication analysis ────────────────────────────────────────

    print(f"\n" + "-" * 70)
    print("LOW-IMPORTANCE DEDUPLICATION")
    print("-" * 70)
    total_low = sum(r["low"] for r in file_results)
    avg_dedup = np.mean([r["dedup"] for r in file_results if r["low"] > 0]) if any(r["low"] > 0 for r in file_results) else 1.0
    print(f"  Total low-importance lines: {total_low}")
    print(f"  Average dedup ratio:        {avg_dedup:.1f}x")
    print(f"  (Higher = more duplicates found = better compression)")

    # ── Top improvers ─────────────────────────────────────────────────

    print(f"\n" + "-" * 70)
    print("TOP COMPRESSION WINS")
    print("-" * 70)
    top = sorted(file_results, key=lambda x: -x["improvement"])[:5]
    for r in top:
        print(f"  {r['improvement']:+.1f}% | {r['name']} ({r['lines']} lines, H:{r['high']} M:{r['med']} L:{r['low']})")

    print(f"\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  CogniMap code compression: {total_raw/1024:.0f} KB -> {total_cogni/1024:.0f} KB ({total_raw/total_cogni:.1f}x)")
    print(f"  vs standard zlib: {'BETTER' if overall_improvement > 0 else 'WORSE'} by {abs(overall_improvement):.1f}%")
    print(f"  Lossless: {lossless_count}/{len(file_results)} files reconstruct identically")
    print(f"  Key: low-importance lines (blanks, comments, imports, boilerplate)")
    print(f"  deduplicate heavily within each file, boosting compression")


if __name__ == "__main__":
    run_experiment()
