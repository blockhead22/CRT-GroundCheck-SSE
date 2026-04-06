"""CogniMap Lossless v3 — CALIC-style Gradient-Adaptive Prediction

v2 showed multi-stage doesn't help (residual is already noise).
v3 approach: better FIRST-stage prediction using wider context.

CALIC insight: predict based on local gradient direction.
  - If horizontal gradient is strong: predict from top (horizontal edge)
  - If vertical gradient is strong: predict from left (vertical edge)
  - If smooth: predict from weighted average of all neighbors
  - The weights adapt per-pixel based on local texture direction

No blocks. No strategy map. Pure per-pixel adaptive prediction.
The CogniMap overhead drops to near-zero because there's no strategy
to store — the prediction is deterministic from decoded context.

Run: .venv/Scripts/python papers/compression_experiment/cognimap_lossless_v3.py
"""

import sys
import zlib
import hashlib
import time
import struct
from pathlib import Path
from io import BytesIO

import numpy as np
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
TEST_IMAGE = SCRIPT_DIR / "test_image.jpg"
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ── Gradient-Adaptive Predictor ────────────────────────────────────────

def compress_calic_style(image: np.ndarray) -> tuple:
    """CALIC-style gradient-adaptive prediction.

    For each pixel, compute local gradients from decoded neighbors
    and use them to weight the prediction adaptively.
    """
    h, w = image.shape[:2]
    channels = image.shape[2] if len(image.shape) > 2 else 1
    img16 = image.astype(np.int16)
    residual = np.zeros_like(img16)

    for y in range(h):
        for x in range(w):
            if y == 0 and x == 0:
                pred = np.int16(128) if channels == 1 else np.full(channels, 128, dtype=np.int16)
            elif y == 0:
                pred = img16[y, x-1]
            elif x == 0:
                pred = img16[y-1, x]
            else:
                # Gather neighbors
                W = img16[y, x-1]       # West (left)
                N = img16[y-1, x]       # North (top)
                NW = img16[y-1, x-1]    # Northwest
                NE = img16[y-1, min(x+1, w-1)]  # Northeast

                # Compute gradients
                dh = np.abs(W.astype(np.int32) - NW.astype(np.int32))  # horizontal change
                dv = np.abs(N.astype(np.int32) - NW.astype(np.int32))  # vertical change

                if channels > 1:
                    dh_sum = dh.sum()
                    dv_sum = dv.sum()
                else:
                    dh_sum = int(dh)
                    dv_sum = int(dv)

                if dh_sum + dv_sum == 0:
                    # Perfectly flat — predict average
                    pred = (W.astype(np.int16) + N.astype(np.int16)) // 2
                elif dh_sum > dv_sum + 32:
                    # Strong horizontal gradient (horizontal edge)
                    # Predict from North (pixels above are more similar)
                    pred = N
                elif dv_sum > dh_sum + 32:
                    # Strong vertical gradient (vertical edge)
                    # Predict from West (pixels to left are more similar)
                    pred = W
                elif dh_sum > dv_sum + 8:
                    # Moderate horizontal — weighted toward N
                    alpha = min(0.8, 0.5 + (dh_sum - dv_sum) / max(dh_sum + dv_sum, 1) * 0.5)
                    pred = np.int16(alpha * N.astype(np.float32) + (1-alpha) * W.astype(np.float32))
                elif dv_sum > dh_sum + 8:
                    # Moderate vertical — weighted toward W
                    alpha = min(0.8, 0.5 + (dv_sum - dh_sum) / max(dh_sum + dv_sum, 1) * 0.5)
                    pred = np.int16(alpha * W.astype(np.float32) + (1-alpha) * N.astype(np.float32))
                else:
                    # Smooth region — use Paeth-like prediction with NE
                    p = W.astype(np.int32) + N.astype(np.int32) - NW.astype(np.int32)
                    # Clamp and add NE influence for diagonal textures
                    ne_weight = 0.1
                    p = np.int16(p * (1 - ne_weight) + NE.astype(np.int32) * ne_weight)
                    pred = np.clip(p, 0, 255).astype(np.int16)

            residual[y, x] = img16[y, x] - pred

    return residual


def compress_calic_v2(image: np.ndarray) -> tuple:
    """Enhanced CALIC with wider context (7 neighbors)."""
    h, w = image.shape[:2]
    channels = image.shape[2] if len(image.shape) > 2 else 1
    img16 = image.astype(np.int16)
    residual = np.zeros_like(img16)

    for y in range(h):
        for x in range(w):
            if y == 0 and x == 0:
                pred = np.int16(128) if channels == 1 else np.full(channels, 128, dtype=np.int16)
            elif y == 0:
                pred = img16[y, x-1]
            elif x == 0:
                pred = img16[y-1, x]
            elif y == 1 or x == 1 or x >= w - 1:
                # Limited context — use simple Paeth
                a = img16[y, x-1].astype(np.int32)
                b = img16[y-1, x].astype(np.int32)
                c = img16[y-1, x-1].astype(np.int32)
                p = a + b - c
                pa, pb, pc = np.abs(p-a), np.abs(p-b), np.abs(p-c)
                if channels > 1:
                    pred = np.zeros(channels, dtype=np.int16)
                    for ch in range(channels):
                        if pa[ch] <= pb[ch] and pa[ch] <= pc[ch]: pred[ch] = a[ch]
                        elif pb[ch] <= pc[ch]: pred[ch] = b[ch]
                        else: pred[ch] = c[ch]
                else:
                    if pa <= pb and pa <= pc: pred = np.int16(a)
                    elif pb <= pc: pred = np.int16(b)
                    else: pred = np.int16(c)
            else:
                # Full context: 7 neighbors
                W = img16[y, x-1]           # West
                N = img16[y-1, x]           # North
                NW = img16[y-1, x-1]        # Northwest
                NE = img16[y-1, x+1]        # Northeast
                WW = img16[y, x-2]          # West-West
                NN = img16[y-2, x]          # North-North
                NNW = img16[y-2, x-1] if x > 0 else img16[y-2, x]  # North-North-West

                # CALIC gradient computation
                dh = np.abs(W.astype(np.int32) - NW.astype(np.int32)) + \
                     np.abs(N.astype(np.int32) - NE.astype(np.int32)) + \
                     np.abs(NW.astype(np.int32) - NNW.astype(np.int32))

                dv = np.abs(N.astype(np.int32) - NW.astype(np.int32)) + \
                     np.abs(W.astype(np.int32) - WW.astype(np.int32)) + \
                     np.abs(NW.astype(np.int32) - NNW.astype(np.int32))

                if channels > 1:
                    dh_s = dh.sum()
                    dv_s = dv.sum()
                else:
                    dh_s = int(dh)
                    dv_s = int(dv)

                if dh_s > dv_s + 80:
                    # Strong horizontal edge
                    pred = N
                elif dv_s > dh_s + 80:
                    # Strong vertical edge
                    pred = W
                elif dh_s > dv_s + 32:
                    # Moderate horizontal
                    pred = np.int16((3 * N.astype(np.int32) + W.astype(np.int32)) // 4)
                elif dv_s > dh_s + 32:
                    # Moderate vertical
                    pred = np.int16((W.astype(np.int32) * 3 + N.astype(np.int32)) // 4)
                else:
                    # Smooth — weighted combination
                    # CALIC formula: (W + N) / 2 + (NE - NW) / 4
                    base = (W.astype(np.int32) + N.astype(np.int32)) // 2
                    correction = (NE.astype(np.int32) - NW.astype(np.int32)) // 4
                    pred = np.clip(base + correction, 0, 255).astype(np.int16)

            residual[y, x] = img16[y, x] - pred

    return residual


def decompress_calic_v2(residual: np.ndarray, shape: tuple) -> np.ndarray:
    """Reconstruct from CALIC v2 residual (same prediction, causal)."""
    h, w = shape[:2]
    channels = shape[2] if len(shape) > 2 else 1
    img16 = np.zeros(shape, dtype=np.int16)

    for y in range(h):
        for x in range(w):
            if y == 0 and x == 0:
                pred = np.int16(128) if channels == 1 else np.full(channels, 128, dtype=np.int16)
            elif y == 0:
                pred = img16[y, x-1]
            elif x == 0:
                pred = img16[y-1, x]
            elif y == 1 or x == 1 or x >= w - 1:
                a = img16[y, x-1].astype(np.int32)
                b = img16[y-1, x].astype(np.int32)
                c = img16[y-1, x-1].astype(np.int32)
                p = a + b - c
                pa, pb, pc = np.abs(p-a), np.abs(p-b), np.abs(p-c)
                if channels > 1:
                    pred = np.zeros(channels, dtype=np.int16)
                    for ch in range(channels):
                        if pa[ch] <= pb[ch] and pa[ch] <= pc[ch]: pred[ch] = a[ch]
                        elif pb[ch] <= pc[ch]: pred[ch] = b[ch]
                        else: pred[ch] = c[ch]
                else:
                    if pa <= pb and pa <= pc: pred = np.int16(a)
                    elif pb <= pc: pred = np.int16(b)
                    else: pred = np.int16(c)
            else:
                W = img16[y, x-1]
                N = img16[y-1, x]
                NW = img16[y-1, x-1]
                NE = img16[y-1, x+1]
                WW = img16[y, x-2]
                NN = img16[y-2, x]
                NNW = img16[y-2, x-1] if x > 0 else img16[y-2, x]

                dh = np.abs(W.astype(np.int32) - NW.astype(np.int32)) + \
                     np.abs(N.astype(np.int32) - NE.astype(np.int32)) + \
                     np.abs(NW.astype(np.int32) - NNW.astype(np.int32))
                dv = np.abs(N.astype(np.int32) - NW.astype(np.int32)) + \
                     np.abs(W.astype(np.int32) - WW.astype(np.int32)) + \
                     np.abs(NW.astype(np.int32) - NNW.astype(np.int32))

                dh_s = dh.sum() if channels > 1 else int(dh)
                dv_s = dv.sum() if channels > 1 else int(dv)

                if dh_s > dv_s + 80:
                    pred = N
                elif dv_s > dh_s + 80:
                    pred = W
                elif dh_s > dv_s + 32:
                    pred = np.int16((3 * N.astype(np.int32) + W.astype(np.int32)) // 4)
                elif dv_s > dh_s + 32:
                    pred = np.int16((W.astype(np.int32) * 3 + N.astype(np.int32)) // 4)
                else:
                    base = (W.astype(np.int32) + N.astype(np.int32)) // 2
                    correction = (NE.astype(np.int32) - NW.astype(np.int32)) // 4
                    pred = np.clip(base + correction, 0, 255).astype(np.int16)

            img16[y, x] = pred + residual[y, x]

    return np.clip(img16, 0, 255).astype(np.uint8)


# ── Main ───────────────────────────────────────────────────────────────

def run_experiment():
    print("=" * 70)
    print("CogniMap Lossless v3 - CALIC-style Gradient-Adaptive")
    print("=" * 70)

    img = Image.open(str(TEST_IMAGE))
    image = np.array(img)
    print(f"\nImage: {TEST_IMAGE.name} | {image.shape} | Raw: {image.nbytes/1024:.0f} KB")
    original_hash = hashlib.sha256(image.tobytes()).hexdigest()[:16]

    # Baselines
    buf = BytesIO(); Image.fromarray(image).save(buf, format="PNG", optimize=True)
    png_size = buf.tell()
    raw_zlib = zlib.compress(image.tobytes(), 9)
    print(f"PNG: {png_size/1024:.0f} KB ({image.nbytes/png_size:.1f}x)")
    print(f"zlib: {len(raw_zlib)/1024:.0f} KB ({image.nbytes/len(raw_zlib):.1f}x)")

    # ── v1 baseline (block-adaptive, from previous experiments) ──────

    print(f"\n--- v1: Block-adaptive (4x4, 6 predictors) ---")
    # Quick estimate from v1 results
    print(f"  (from v1): ~2031 KB, 2.2x, -18.9% vs PNG")

    # ── v3a: Simple gradient-adaptive ────────────────────────────────

    print(f"\n--- v3a: Simple gradient-adaptive (4 neighbors) ---")
    t0 = time.time()
    residual_a = compress_calic_style(image)
    ta = time.time() - t0

    r_bytes = residual_a.astype(np.int16).tobytes()
    r_compressed = zlib.compress(r_bytes, 9)
    total_a = len(r_compressed) + 20  # Just residual + tiny header (no strategy map!)

    zeros_a = np.sum(residual_a == 0) / residual_a.size * 100
    mean_a = np.abs(residual_a).mean()
    print(f"  Time: {ta:.1f}s")
    print(f"  Residual: mean|r|={mean_a:.2f} zeros={zeros_a:.1f}%")
    print(f"  Size: {total_a/1024:.0f} KB ({image.nbytes/total_a:.1f}x)")
    print(f"  vs PNG: {(1-total_a/png_size)*100:+.1f}%")
    print(f"  vs zlib: {(1-total_a/len(raw_zlib))*100:+.1f}%")
    print(f"  CogniMap overhead: 0 KB (prediction is deterministic from context)")

    # ── v3b: Enhanced CALIC (7 neighbors) ────────────────────────────

    print(f"\n--- v3b: Enhanced CALIC (7 neighbors, gradient zones) ---")
    t0 = time.time()
    residual_b = compress_calic_v2(image)
    tb = time.time() - t0

    r_bytes_b = residual_b.astype(np.int16).tobytes()
    r_compressed_b = zlib.compress(r_bytes_b, 9)
    total_b = len(r_compressed_b) + 20

    zeros_b = np.sum(residual_b == 0) / residual_b.size * 100
    mean_b = np.abs(residual_b).mean()
    print(f"  Time: {tb:.1f}s")
    print(f"  Residual: mean|r|={mean_b:.2f} zeros={zeros_b:.1f}%")
    print(f"  Size: {total_b/1024:.0f} KB ({image.nbytes/total_b:.1f}x)")
    print(f"  vs PNG: {(1-total_b/png_size)*100:+.1f}%")
    print(f"  vs zlib: {(1-total_b/len(raw_zlib))*100:+.1f}%")

    # ── Verify lossless ──────────────────────────────────────────────

    print(f"\n--- Lossless Verification ---")
    t0 = time.time()
    restored = decompress_calic_v2(residual_b, image.shape)
    td = time.time() - t0

    restored_hash = hashlib.sha256(restored.tobytes()).hexdigest()[:16]
    identical = original_hash == restored_hash
    max_diff = np.max(np.abs(image.astype(np.int16) - restored.astype(np.int16)))
    print(f"  Decompress time: {td:.1f}s")
    print(f"  Bit-identical: {'YES' if identical else 'NO'} (max_diff={max_diff})")

    Image.fromarray(restored).save(str(OUTPUT_DIR / "cognimap_v3_restored.png"))

    # ── Summary ──────────────────────────────────────────────────────

    print(f"\n" + "=" * 70)
    print("COMPARISON")
    print("=" * 70)
    print(f"  {'Method':25s} {'Size':>8s} {'Ratio':>6s} {'mean|r|':>8s} {'zeros':>6s} {'vs PNG':>8s} {'Map':>5s}")
    print(f"  {'-'*25} {'-'*8} {'-'*6} {'-'*8} {'-'*6} {'-'*8} {'-'*5}")
    print(f"  {'PNG':25s} {png_size/1024:7.0f}K {image.nbytes/png_size:5.1f}x {'---':>8s} {'---':>6s} {'0.0%':>8s} {'0':>5s}")
    print(f"  {'zlib (no prediction)':25s} {len(raw_zlib)/1024:7.0f}K {image.nbytes/len(raw_zlib):5.1f}x {'---':>8s} {'---':>6s} {(1-len(raw_zlib)/png_size)*100:+7.1f}% {'0':>5s}")
    print(f"  {'v1 block-adaptive':25s} {'2031':>7s}K {'2.2':>5s}x {'1.81':>8s} {'37.7':>5s}% {'-18.9%':>8s} {'~6K':>5s}")
    print(f"  {'v3a gradient (4-nbr)':25s} {total_a/1024:7.0f}K {image.nbytes/total_a:5.1f}x {mean_a:8.2f} {zeros_a:5.1f}% {(1-total_a/png_size)*100:+7.1f}% {'0':>5s}")
    print(f"  {'v3b CALIC (7-nbr)':25s} {total_b/1024:7.0f}K {image.nbytes/total_b:5.1f}x {mean_b:8.2f} {zeros_b:5.1f}% {(1-total_b/png_size)*100:+7.1f}% {'0':>5s}")

    best = min(total_a, total_b)
    best_name = "v3a" if total_a < total_b else "v3b"
    print(f"\n  Best CogniMap: {best_name} at {best/1024:.0f} KB")
    if best < png_size:
        print(f"  >>> BEATS PNG by {(1-best/png_size)*100:.1f}% <<<")
    else:
        print(f"  Gap to PNG: {(best/png_size - 1)*100:.1f}% larger")
        print(f"  Gap closing: v1 was -18.9%, now {(1-best/png_size)*100:+.1f}%")


if __name__ == "__main__":
    run_experiment()
