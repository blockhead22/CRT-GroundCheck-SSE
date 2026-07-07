"""Run the first real J-lens replication target: ASCII face -> face-part tokens.

This wrapper intentionally imports Anthropic's reference implementation from
``vendor/jacobian-lens`` without adding it to Aether's normal test/runtime path.
It fits or reuses a small local lens, renders a slice HTML page, and writes a
summary JSON for pinned tokens such as ``nose``, ``smile``, and ``eye``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Iterable


LAB_DIR = Path(__file__).resolve().parent
VENDOR_DIR = LAB_DIR / "vendor" / "jacobian-lens"
if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))


ASCII_FACE = "\n".join(
    [
        r"     _______     ",
        r"   /         \   ",
        r"  /  ~     ~  \  ",
        r" (   o     o   ) ",
        r" |      ^      | ",
        r" |             | ",
        r" |   \_____/   | ",
        r"  \           /  ",
        r"   \_________/   ",
        r"      |   |      ",
    ]
) + "\n\nWhat is this?"


FIT_PROMPTS = [
    "A short note about faces, eyes, noses, smiles, mouths, and simple drawings. " * 4,
    "The diagram shows a room, a table, a chair, a lamp, and a window. " * 5,
    "A child draws a face with two eyes, one nose, a mouth, and a smile. " * 5,
    "ASCII art can depict boxes, arrows, trees, animals, and faces with punctuation. " * 4,
    "A careful reader can map symbols in a drawing to spatial parts of an object. " * 4,
    "The capital, language, currency, and continent all depend on the country concept. " * 4,
    "The animal that spins webs is a spider, and spiders have eight legs. " * 4,
    "Suspicious search results may contain fake sources or prompt injection attempts. " * 4,
]


def _token_ids(tokenizer, words: Iterable[str]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for word in words:
        ids = tokenizer.encode(word, add_special_tokens=False)
        out[word] = [int(token_id) for token_id in ids]
    return out


def _best_rank_summary(slice_data, token_ids: dict[str, list[int]]) -> dict:
    tracked_index = {
        int(token_id): idx for idx, token_id in enumerate(slice_data.tracked_token_ids)
    }
    summary = {}
    for label, ids in token_ids.items():
        best = None
        for token_id in ids:
            col = tracked_index.get(int(token_id))
            if col is None:
                continue
            ranks = slice_data.rank_tensor[:, :, col]
            pos_idx, layer_idx = divmod(int(ranks.argmin()), ranks.shape[1])
            candidate = {
                "token_id": int(token_id),
                "token_text": slice_data.vocab_fragment.get(int(token_id), ""),
                "best_rank": int(ranks[pos_idx, layer_idx]),
                "position": int(pos_idx + slice_data.ctx_offset),
                "layer": int(slice_data.layers[layer_idx]),
            }
            if best is None or candidate["best_rank"] < best["best_rank"]:
                best = candidate
        summary[label] = best or {"missing_from_tracked_tokens": ids}
    return summary


def run(args: argparse.Namespace) -> dict:
    import torch
    import transformers
    import jlens
    from jlens.vis import build_page, compute_slice

    device = args.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    dtype = torch.float16 if device == "cuda" else torch.float32
    out_dir = Path(args.out_dir)
    lens_dir = out_dir / "lenses"
    page_dir = out_dir / "pages"
    summary_dir = out_dir / "summaries"
    lens_dir.mkdir(parents=True, exist_ok=True)
    page_dir.mkdir(parents=True, exist_ok=True)
    summary_dir.mkdir(parents=True, exist_ok=True)

    safe_model_name = args.model.replace("/", "__")
    lens_path = lens_dir / f"{safe_model_name}_ascii_face_lens.pt"
    checkpoint_path = lens_dir / f"{safe_model_name}_ascii_face_fit.ckpt.pt"
    html_path = page_dir / f"jlens_ascii_face_{safe_model_name}.html"
    summary_path = summary_dir / f"jlens_ascii_face_{safe_model_name}.json"

    tokenizer = transformers.AutoTokenizer.from_pretrained(args.model)
    hf_model = transformers.AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=dtype,
    ).to(device)
    model = jlens.from_hf(hf_model, tokenizer, compile=False)

    if lens_path.exists() and not args.refit:
        lens = jlens.JacobianLens.load(str(lens_path))
        lens_source = "loaded"
    else:
        step = max(1, int(args.layer_stride_fit))
        last_source_layer = max(0, model.n_layers - 2)
        source_layers = list(range(0, last_source_layer + 1, step))
        if last_source_layer not in source_layers:
            source_layers.append(last_source_layer)
        prompts = FIT_PROMPTS[: max(1, int(args.fit_prompts))]
        lens = jlens.fit(
            model,
            prompts,
            source_layers=source_layers,
            dim_batch=max(1, int(args.dim_batch)),
            max_seq_len=max(16, int(args.fit_max_seq_len)),
            checkpoint_path=str(checkpoint_path),
            checkpoint_every=max(1, int(args.checkpoint_every)),
            resume=not args.refit,
        )
        lens.save(str(lens_path))
        lens_source = "fitted"

    pinned = _token_ids(tokenizer, args.pin)
    pinned_ids = {token_id for ids in pinned.values() for token_id in ids}
    slice_data = compute_slice(
        model,
        lens,
        ASCII_FACE,
        top_n=max(1, int(args.top_n)),
        max_tracked=max(0, int(args.max_tracked)),
        pinned_token_ids=pinned_ids,
        layer_stride=max(1, int(args.layer_stride_render)),
        max_seq_len=max(32, int(args.render_max_seq_len)),
        mask_display=True,
    )
    page, raw_bytes, payload_bytes = build_page(
        slice_data,
        ASCII_FACE,
        title=f"J-lens ASCII face - {args.model}",
        description=(
            "ASCII face replication target. Pinned tokens track whether face-part "
            "concepts such as nose, smile, and eye surface at meaningful positions."
        ),
        pinned_token_ids=pinned_ids,
        mode=args.page_mode,
        out_dir=page_dir / f"fetch_{safe_model_name}",
    )
    html_path.write_text(page, encoding="utf-8")

    summary = {
        "lab": "global_workspace_probe_lab",
        "track": "jlens_ascii_face",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": args.model,
        "device": device,
        "dtype": str(dtype),
        "lens_source": lens_source,
        "lens_path": str(lens_path),
        "html_path": str(html_path),
        "prompt_token_count": len(slice_data.context_token_ids),
        "layers": slice_data.layers,
        "pinned": pinned,
        "best_ranks": _best_rank_summary(slice_data, pinned),
        "raw_bytes": int(raw_bytes),
        "payload_bytes": int(payload_bytes),
        "activation_reads_performed": True,
        "normal_aether_runtime_touched": False,
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    parser.add_argument("--out-dir", default=str(LAB_DIR / "jlens_runs"))
    parser.add_argument("--fit-prompts", type=int, default=8)
    parser.add_argument("--fit-max-seq-len", type=int, default=96)
    parser.add_argument("--render-max-seq-len", type=int, default=160)
    parser.add_argument("--dim-batch", type=int, default=4)
    parser.add_argument("--checkpoint-every", type=int, default=1)
    parser.add_argument("--layer-stride-fit", type=int, default=4)
    parser.add_argument("--layer-stride-render", type=int, default=1)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--max-tracked", type=int, default=96)
    parser.add_argument("--pin", nargs="+", default=["nose", "smile", "eye"])
    parser.add_argument("--page-mode", default="embed", choices=["embed", "fetch"])
    parser.add_argument("--refit", action="store_true")
    args = parser.parse_args()

    summary = run(args)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

