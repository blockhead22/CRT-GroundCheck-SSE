from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _norm_text(x: Any) -> str:
    return (str(x) if x is not None else "").strip().lower()


def _slot_key(s: Dict[str, Any]) -> str:
    return str(s.get("slot") or "").strip().lower()


def _contains_recommended_value(answer: str, recommended_value: Any) -> Optional[bool]:
    if recommended_value is None:
        return None
    a = _norm_text(answer)
    rv = _norm_text(recommended_value)
    if not rv:
        return None
    return rv in a


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

    # A/B scoring aggregates
    ab_compared = 0
    ab_agree_action = 0
    ab_agree_value = 0
    ab_disagree = 0
    learned_value_hits = 0
    learned_value_misses = 0
    heuristic_value_hits = 0
    heuristic_value_misses = 0

    with report_path.open("w", encoding="utf-8") as out:
        out.write(f"# CRT Stress Test Report ({run_id})\n\n")
        out.write(f"- Turns: {turns}\n")
        out.write(f"- Gates: pass={gates_pass} fail={gates_fail}\n")
        out.write(f"- Contradictions detected: {contra_yes}\n")
        if avg_conf is not None:
            out.write(f"- Avg confidence: {avg_conf:.3f}\n")
        out.write(f"- Source JSONL: {path.name}\n\n")

        # Compute A/B summary first so it appears near the top.
        for r in rows:
            answer = r.get("answer") or ""
            learned = r.get("learned_suggestions") or []
            heuristic = r.get("heuristic_suggestions") or []
            if not learned or not heuristic:
                continue

            lmap = {_slot_key(s): s for s in learned if _slot_key(s)}
            hmap = {_slot_key(s): s for s in heuristic if _slot_key(s)}
            for slot in sorted(set(lmap.keys()) & set(hmap.keys())):
                ls = lmap[slot]
                hs = hmap[slot]
                ab_compared += 1
                if _norm_text(ls.get("action")) == _norm_text(hs.get("action")):
                    ab_agree_action += 1
                else:
                    ab_disagree += 1
                if _norm_text(ls.get("recommended_value")) == _norm_text(hs.get("recommended_value")):
                    ab_agree_value += 1

                lv = _contains_recommended_value(answer, ls.get("recommended_value"))
                if lv is True:
                    learned_value_hits += 1
                elif lv is False:
                    learned_value_misses += 1

                hv = _contains_recommended_value(answer, hs.get("recommended_value"))
                if hv is True:
                    heuristic_value_hits += 1
                elif hv is False:
                    heuristic_value_misses += 1

        out.write("## A/B Scoring (Learned vs Heuristic)\n\n")
        out.write(
            "These metrics are metadata-only and do not change CRT behavior. "
            "Value-hit rates are a simple string containment check of the suggested recommended_value within the answer.\n\n"
        )
        out.write(f"- Compared slot-suggestions: {ab_compared}\n")
        if ab_compared:
            out.write(f"- Action agreement: {ab_agree_action}/{ab_compared} ({(ab_agree_action/ab_compared)*100:.1f}%)\n")
            out.write(f"- Value agreement: {ab_agree_value}/{ab_compared} ({(ab_agree_value/ab_compared)*100:.1f}%)\n")
            out.write(f"- Action disagreements: {ab_disagree}/{ab_compared} ({(ab_disagree/ab_compared)*100:.1f}%)\n")
        total_lv = learned_value_hits + learned_value_misses
        total_hv = heuristic_value_hits + heuristic_value_misses
        if total_lv:
            out.write(f"- Learned value-hit rate: {learned_value_hits}/{total_lv} ({(learned_value_hits/total_lv)*100:.1f}%)\n")
        if total_hv:
            out.write(f"- Heuristic value-hit rate: {heuristic_value_hits}/{total_hv} ({(heuristic_value_hits/total_hv)*100:.1f}%)\n")
        out.write("\n")

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
            heur = r.get("heuristic_suggestions") or []

            out.write(f"## Turn {t}: {name}\n\n")
            out.write(f"**Q:** {q}\n\n")
            out.write(f"**A:** {a}\n\n")
            out.write(
                f"**Meta:** mode={mode} confidence={conf} gates_passed={gates} contradiction_detected={contra}\n\n"
            )

            # Per-turn A/B delta (only if both exist)
            if sugg and heur:
                lmap = {_slot_key(s): s for s in sugg if _slot_key(s)}
                hmap = {_slot_key(s): s for s in heur if _slot_key(s)}
                shared = sorted(set(lmap.keys()) & set(hmap.keys()))
                deltas: List[str] = []
                for slot in shared:
                    ls = lmap[slot]
                    hs = hmap[slot]
                    la = _norm_text(ls.get("action"))
                    ha = _norm_text(hs.get("action"))
                    if la != ha:
                        deltas.append(f"- {slot}: learned={la} vs heuristic={ha}")
                if deltas:
                    out.write("**A/B delta (action):**\n")
                    out.write("\n".join(deltas) + "\n\n")
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

            if heur:
                out.write("**Heuristic baseline:**\n")
                for s in heur:
                    slot = s.get("slot")
                    action = s.get("action")
                    p = s.get("confidence")
                    rec = s.get("recommended_value")
                    rat = s.get("rationale")
                    out.write(f"- {slot}: {action} (p={p}) -> {rec} [{rat}]\n")
                out.write("\n")

    print(str(report_path))


if __name__ == "__main__":
    main()
