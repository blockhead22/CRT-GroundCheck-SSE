from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def main() -> None:
    art = Path(__file__).resolve().parent
    files = sorted(
        art.glob("crt_stress_run.*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        raise SystemExit("No JSONL artifacts found under artifacts/")

    path = files[0]

    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    run_id = (rows[0].get("run_id") if rows else None) or "unknown"
    report_path = art / f"crt_stress_report.{run_id}.md"

    turns = len(rows)
    gates_pass = sum(1 for r in rows if r.get("gates_passed") is True)
    gates_fail = sum(1 for r in rows if r.get("gates_passed") is False)
    contra_yes = sum(1 for r in rows if r.get("contradiction_detected") is True)

    confs = [r.get("confidence") for r in rows if isinstance(r.get("confidence"), (int, float))]
    avg_conf = (sum(confs) / len(confs)) if confs else None

    with report_path.open("w", encoding="utf-8") as out:
        out.write(f"# CRT Stress Test Report ({run_id})\n\n")
        out.write(f"- Turns: {turns}\n")
        out.write(f"- Gates: pass={gates_pass} fail={gates_fail}\n")
        out.write(f"- Contradictions detected: {contra_yes}\n")
        if avg_conf is not None:
            out.write(f"- Avg confidence: {avg_conf:.3f}\n")
        out.write(f"- Source JSONL: {path.name}\n\n")

        for r in rows:
            t = r.get("turn")
            name = r.get("test_name") or ""
            q = r.get("question") or ""
            a = r.get("answer") or ""
            mode = r.get("mode")
            conf = r.get("confidence")
            gates = r.get("gates_passed")
            contra = r.get("contradiction_detected")
            sugg = r.get("learned_suggestions") or []

            out.write(f"## Turn {t}: {name}\n\n")
            out.write(f"**Q:** {q}\n\n")
            out.write(f"**A:** {a}\n\n")
            out.write(
                f"**Meta:** mode={mode} confidence={conf} gates_passed={gates} contradiction_detected={contra}\n\n"
            )
            if sugg:
                out.write("**Learned suggestions:**\n")
                for s in sugg:
                    slot = s.get("slot")
                    action = s.get("action")
                    p = s.get("confidence")
                    rec = s.get("recommended_value")
                    rat = s.get("rationale")
                    out.write(f"- {slot}: {action} (p={p}) -> {rec} [{rat}]\n")
                out.write("\n")
            else:
                out.write("**Learned suggestions:** (none)\n\n")

    print(str(report_path))


if __name__ == "__main__":
    main()
