"""CogniMap Lossless v2 — Multi-Stage Residual Prediction (RVQ-style)

Stage 1: Adaptive per-block causal prediction (from v1)
Stage 2: Predict Stage 1's residual using local residual patterns
Stage 3: The remaining residual should be near-zero

Each stage reduces the energy in the residual, making zlib compress better.
This is the image equivalent of Residual Vector Quantization.

Run: .venv/Scripts/python papers/compression_experiment/cognimap_lossless_v2.py
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


# ── Stage 1: Adaptive causal prediction (best of 7 strategies) ────────

def pred_left(img, y, x):
    if x == 0: return np.int16(128) if y == 0 else img[y-1, x]
    return img[y, x-1]

def pred_top(img, y, x):
    if y == 0: return np.int16(128) if x == 0 else img[y, x-1]
    return img[y-1, x]

def pred_avg(img, y, x):
    if y == 0 and x == 0: return np.int16(128)
    if y == 0: return img[y, x-1]
    if x == 0: return img[y-1, x]
    return (img[y, x-1].astype(np.int16) + img[y-1, x].astype(np.int16)) // 2

def pred_paeth(img, y, x):
    if y == 0 and x == 0: return np.int16(128)
    if y == 0: return img[y, x-1]
    if x == 0: return img[y-1, x]
    a = img[y, x-1].astype(np.int32)
    b = img[y-1, x].astype(np.int32)
    c = img[y-1, x-1].astype(np.int32)
    p = a + b - c
    pa, pb, pc = np.abs(p - a), np.abs(p - b), np.abs(p - c)
    if hasattr(pa, '__len__'):
        result = np.zeros_like(a, dtype=np.int16)
        for ch in range(len(pa)):
            if pa[ch] <= pb[ch] and pa[ch] <= pc[ch]: result[ch] = a[ch]
            elif pb[ch] <= pc[ch]: result[ch] = b[ch]
            else: result[ch] = c[ch]
        return result
    if pa <= pb and pa <= pc: return np.int16(a)
    elif pb <= pc: return np.int16(b)
    return np.int16(c)

def pred_gradient(img, y, x):
    if y == 0 or x == 0: return pred_avg(img, y, x)
    val = img[y, x-1].astype(np.int16) + img[y-1, x].astype(np.int16) - img[y-1, x-1].astype(np.int16)
    return np.clip(val, 0, 255).astype(np.int16)

def pred_median(img, y, x):
    if y == 0 or x == 0: return pred_avg(img, y, x)
    vals = np.array([img[y, x-1], img[y-1, x], img[y-1, x-1]], dtype=np.int16)
    if hasattr(vals[0], '__len__'):
        return np.median(vals, axis=0).astype(np.int16)
    return np.int16(np.median(vals))

PREDICTORS = [pred_left, pred_top, pred_avg, pred_paeth, pred_gradient, pred_median]


def stage1_compress(image: np.ndarray, block_size: int = 4):
    """Stage 1: try all predictors per block, pick best."""
    h, w = image.shape[:2]
    channels = image.shape[2] if len(image.shape) > 2 else 1
    img16 = image.astype(np.int16)

    bh = (h + block_size - 1) // block_size
    bw = (w + block_size - 1) // block_size
    strategy = np.zeros((bh, bw), dtype=np.uint8)
    residual = np.zeros_like(img16)

    for by in range(bh):
        for bx in range(bw):
            y0, x0 = by * block_size, bx * block_size
            y1, x1 = min(y0 + block_size, h), min(x0 + block_size, w)

            best_cost = float('inf')
            best_idx = 0
            best_res = None

            for pi, pred_fn in enumerate(PREDICTORS):
                block_res = np.zeros((y1-y0, x1-x0, channels) if channels > 1 else (y1-y0, x1-x0), dtype=np.int16)
                for y in range(y0, y1):
                    for x in range(x0, x1):
                        block_res[y-y0, x-x0] = img16[y, x] - pred_fn(img16, y, x)
                cost = np.abs(block_res).sum()
                if cost < best_cost:
                    best_cost = cost
                    best_idx = pi
                    best_res = block_res

            strategy[by, bx] = best_idx
            residual[y0:y1, x0:x1] = best_res

    return residual, strategy


# ── Stage 2: Predict residual patterns ────────────────────────────────

def stage2_predict_residual(residual: np.ndarray, window: int = 3):
    """Predict residual values from their local neighborhood.

    For each residual pixel, predict it from the average of
    already-decoded residual neighbors in a causal window.
    """
    h, w = residual.shape[:2]
    channels = residual.shape[2] if len(residual.shape) > 2 else 1
    predicted_res = np.zeros_like(residual)

    for y in range(h):
        for x in range(w):
            # Gather causal neighbors (already decoded)
            neighbors = []
            for dy in range(-window, 1):
                for dx in range(-window, window + 1):
                    ny, nx = y + dy, x + dx
                    if (dy == 0 and dx >= 0):
                        continue  # Skip current and future pixels in current row
                    if 0 <= ny < h and 0 <= nx < w:
                        neighbors.append(residual[ny, nx])

            if neighbors:
                # Weighted average: closer neighbors get more weight
                arr = np.array(neighbors, dtype=np.float32)
                predicted_res[y, x] = np.int16(np.mean(arr, axis=0))

    return predicted_res


def stage2_predict_residual_fast(residual: np.ndarray):
    """Fast Stage 2: predict residual from immediate causal neighbors only.

    Uses left, top, top-left, top-right residuals.
    Much faster than the windowed version.
    """
    h, w = residual.shape[:2]
    channels = residual.shape[2] if len(residual.shape) > 2 else 1
    predicted = np.zeros_like(residual)

    for y in range(h):
        for x in range(w):
            count = 0
            total = np.zeros(channels if channels > 1 else 1, dtype=np.float32) if channels > 1 else 0.0

            if x > 0:
                total = total + residual[y, x-1].astype(np.float32)
                count += 1
            if y > 0:
                total = total + residual[y-1, x].astype(np.float32)
                count += 1
            if y > 0 and x > 0:
                total = total + residual[y-1, x-1].astype(np.float32)
                count += 1
            if y > 0 and x < w - 1:
                total = total + residual[y-1, x+1].astype(np.float32)
                count += 1

            if count > 0:
                predicted[y, x] = np.int16(total / count)

    return predicted


# ── Quality Metrics ────────────────────────────────────────────────────

def psnr(original, compressed):
    mse = np.mean((original.astype(float) - compressed.astype(float)) ** 2)
    if mse == 0: return float('inf')
    return 10 * np.log10(255.0 ** 2 / mse)


# ── Main ───────────────────────────────────────────────────────────────

def run_experiment():
    print("=" * 70)
    print("CogniMap Lossless v2 - Multi-Stage Residual (RVQ-style)")
    print("=" * 70)

    img = Image.open(str(TEST_IMAGE))
    image = np.array(img)
    h, w = image.shape[:2]
    channels = image.shape[2] if len(image.shape) > 2 else 1
    print(f"\nImage: {TEST_IMAGE.name} | {image.shape} | Raw: {image.nbytes/1024:.0f} KB")

    original_hash = hashlib.sha256(image.tobytes()).hexdigest()[:16]

    # Baselines
    buf = BytesIO(); Image.fromarray(image).save(buf, format="PNG", optimize=True)
    png_size = buf.tell()
    raw_zlib = zlib.compress(image.tobytes(), 9)
    print(f"PNG: {png_size/1024:.0f} KB ({image.nbytes/png_size:.1f}x)")
    print(f"zlib raw: {len(raw_zlib)/1024:.0f} KB ({image.nbytes/len(raw_zlib):.1f}x)")

    # ── Stage 1: Adaptive prediction ─────────────────────────────────

    print(f"\n--- Stage 1: Adaptive causal prediction ---")
    t0 = time.time()
    residual1, strategy1 = stage1_compress(image, block_size=4)
    t1 = time.time()
    print(f"  Time: {t1-t0:.1f}s")

    r1_bytes = residual1.astype(np.int16).tobytes()
    r1_compressed = zlib.compress(r1_bytes, 9)
    s1_compressed = zlib.compress(strategy1.tobytes(), 9)
    stage1_total = len(r1_compressed) + len(s1_compressed) + 20  # header

    r1_zeros = np.sum(residual1 == 0) / residual1.size * 100
    r1_mean = np.abs(residual1).mean()
    print(f"  Residual: mean|r|={r1_mean:.2f} zeros={r1_zeros:.1f}%")
    print(f"  Compressed: {stage1_total/1024:.0f} KB ({image.nbytes/stage1_total:.1f}x)")
    print(f"  vs PNG: {'BETTER' if stage1_total < png_size else 'WORSE'} by {abs(1-stage1_total/png_size)*100:.1f}%")

    # ── Stage 2: Predict the residual ────────────────────────────────

    print(f"\n--- Stage 2: Residual-of-residual prediction ---")
    t0 = time.time()
    predicted_r1 = stage2_predict_residual_fast(residual1)
    residual2 = residual1 - predicted_r1
    t2 = time.time()
    print(f"  Time: {t2-t0:.1f}s")

    r2_bytes = residual2.astype(np.int16).tobytes()
    r2_compressed = zlib.compress(r2_bytes, 9)
    stage2_total = len(r2_compressed) + len(s1_compressed) + 20

    r2_zeros = np.sum(residual2 == 0) / residual2.size * 100
    r2_mean = np.abs(residual2).mean()
    improvement = (1 - len(r2_compressed) / len(r1_compressed)) * 100
    print(f"  Residual: mean|r|={r2_mean:.2f} zeros={r2_zeros:.1f}%")
    print(f"  Compressed: {stage2_total/1024:.0f} KB ({image.nbytes/stage2_total:.1f}x)")
    print(f"  vs Stage 1: {'BETTER' if improvement > 0 else 'WORSE'} by {abs(improvement):.1f}%")
    print(f"  vs PNG: {'BETTER' if stage2_total < png_size else 'WORSE'} by {abs(1-stage2_total/png_size)*100:.1f}%")

    # ── Stage 3: One more pass ───────────────────────────────────────

    print(f"\n--- Stage 3: Third-order residual ---")
    t0 = time.time()
    predicted_r2 = stage2_predict_residual_fast(residual2)
    residual3 = residual2 - predicted_r2
    t3 = time.time()
    print(f"  Time: {t3-t0:.1f}s")

    r3_bytes = residual3.astype(np.int16).tobytes()
    r3_compressed = zlib.compress(r3_bytes, 9)
    stage3_total = len(r3_compressed) + len(s1_compressed) + 20

    r3_zeros = np.sum(residual3 == 0) / residual3.size * 100
    r3_mean = np.abs(residual3).mean()
    improvement3 = (1 - len(r3_compressed) / len(r1_compressed)) * 100
    print(f"  Residual: mean|r|={r3_mean:.2f} zeros={r3_zeros:.1f}%")
    print(f"  Compressed: {stage3_total/1024:.0f} KB ({image.nbytes/stage3_total:.1f}x)")
    print(f"  vs Stage 1: {'BETTER' if improvement3 > 0 else 'WORSE'} by {abs(improvement3):.1f}%")
    print(f"  vs PNG: {'BETTER' if stage3_total < png_size else 'WORSE'} by {abs(1-stage3_total/png_size)*100:.1f}%")

    # ── Verify lossless reconstruction ───────────────────────────────

    print(f"\n--- Lossless Verification ---")

    # Reconstruct Stage 1 from strategy + residual1
    # (We need to replay the prediction to verify)
    img16 = image.astype(np.int16)
    bh = (h + 3) // 4
    bw = (w + 3) // 4

    # Verify Stage 1 residual
    recon1 = np.zeros_like(img16)
    for by in range(bh):
        for bx in range(bw):
            y0, x0 = by * 4, bx * 4
            y1, x1 = min(y0 + 4, h), min(x0 + 4, w)
            pred_fn = PREDICTORS[strategy1[by, bx]]
            for y in range(y0, y1):
                for x in range(x0, x1):
                    pred = pred_fn(recon1, y, x)
                    recon1[y, x] = pred + residual1[y, x]

    recon1_img = np.clip(recon1, 0, 255).astype(np.uint8)
    stage1_hash = hashlib.sha256(recon1_img.tobytes()).hexdigest()[:16]
    stage1_match = stage1_hash == original_hash
    print(f"  Stage 1 reconstruction: {'PASS' if stage1_match else 'FAIL'} (hash={stage1_hash})")

    # Verify Stage 2: residual2 = residual1 - predicted_r1
    # So residual1 = residual2 + predicted_r1
    # But predicted_r1 depends on residual1 (causal), so we need to replay
    reconstructed_r1 = np.zeros_like(residual1)
    for y in range(h):
        for x in range(w):
            # Predict from already-reconstructed residual1 neighbors
            count = 0
            total = np.zeros(channels, dtype=np.float32) if channels > 1 else 0.0
            if x > 0:
                total = total + reconstructed_r1[y, x-1].astype(np.float32)
                count += 1
            if y > 0:
                total = total + reconstructed_r1[y-1, x].astype(np.float32)
                count += 1
            if y > 0 and x > 0:
                total = total + reconstructed_r1[y-1, x-1].astype(np.float32)
                count += 1
            if y > 0 and x < w - 1:
                total = total + reconstructed_r1[y-1, x+1].astype(np.float32)
                count += 1
            pred_r = np.int16(total / count) if count > 0 else np.int16(0)
            reconstructed_r1[y, x] = residual2[y, x] + pred_r

    # Now reconstruct image from reconstructed_r1
    recon2 = np.zeros_like(img16)
    for by in range(bh):
        for bx in range(bw):
            y0, x0 = by * 4, bx * 4
            y1, x1 = min(y0 + 4, h), min(x0 + 4, w)
            pred_fn = PREDICTORS[strategy1[by, bx]]
            for y in range(y0, y1):
                for x in range(x0, x1):
                    pred = pred_fn(recon2, y, x)
                    recon2[y, x] = pred + reconstructed_r1[y, x]

    recon2_img = np.clip(recon2, 0, 255).astype(np.uint8)
    stage2_hash = hashlib.sha256(recon2_img.tobytes()).hexdigest()[:16]
    stage2_match = stage2_hash == original_hash
    max_diff = np.max(np.abs(image.astype(np.int16) - recon2_img.astype(np.int16)))
    print(f"  Stage 2 reconstruction: {'PASS' if stage2_match else 'FAIL'} (hash={stage2_hash}, max_diff={max_diff})")

    # Save reconstructed
    Image.fromarray(recon2_img).save(str(OUTPUT_DIR / "cognimap_v2_restored.png"))

    # ── Summary ──────────────────────────────────────────────────────

    print(f"\n" + "=" * 70)
    print("MULTI-STAGE SUMMARY")
    print("=" * 70)
    print(f"  {'Stage':10s} {'Size':>8s} {'Ratio':>6s} {'mean|r|':>8s} {'zeros%':>7s} {'vs PNG':>8s}")
    print(f"  {'-'*10} {'-'*8} {'-'*6} {'-'*8} {'-'*7} {'-'*8}")
    print(f"  {'Raw':10s} {image.nbytes/1024:7.0f}K {1.0:5.1f}x {'---':>8s} {'---':>7s} {'---':>8s}")
    print(f"  {'zlib':10s} {len(raw_zlib)/1024:7.0f}K {image.nbytes/len(raw_zlib):5.1f}x {'---':>8s} {'---':>7s} {(1-len(raw_zlib)/png_size)*100:+7.1f}%")
    print(f"  {'PNG':10s} {png_size/1024:7.0f}K {image.nbytes/png_size:5.1f}x {'---':>8s} {'---':>7s} {'  0.0%':>8s}")
    print(f"  {'Stage 1':10s} {stage1_total/1024:7.0f}K {image.nbytes/stage1_total:5.1f}x {r1_mean:8.2f} {r1_zeros:6.1f}% {(1-stage1_total/png_size)*100:+7.1f}%")
    print(f"  {'Stage 2':10s} {stage2_total/1024:7.0f}K {image.nbytes/stage2_total:5.1f}x {r2_mean:8.2f} {r2_zeros:6.1f}% {(1-stage2_total/png_size)*100:+7.1f}%")
    print(f"  {'Stage 3':10s} {stage3_total/1024:7.0f}K {image.nbytes/stage3_total:5.1f}x {r3_mean:8.2f} {r3_zeros:6.1f}% {(1-stage3_total/png_size)*100:+7.1f}%")
    print(f"\n  Stage 1 lossless: {'YES' if stage1_match else 'NO'}")
    print(f"  Stage 2 lossless: {'YES' if stage2_match else 'NO'}")


if __name__ == "__main__":
    run_experiment()
