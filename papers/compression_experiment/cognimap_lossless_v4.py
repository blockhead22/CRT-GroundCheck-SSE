"""CogniMap Lossless v4 — v1 strategy map + CALIC-7 + YCoCg-R color decorrelation.

The "missing cell" in the v1-vs-v3 comparison: v1 had the per-block strategy
map but only basic predictors; v3 had CALIC-7 but no strategy map. The two
experiments changed two variables simultaneously, so neither isolates which
variable drove v1's win.

v4 holds the strategy map = YES while adding CALIC-7 to the predictor menu
AND adding YCoCg-R as a lossless reversible color preprocessing step.

Decision rule (from AETHER_TEST_PLAN.md):
  - If v4 beats v1 by >=5%, ship as new baseline.
  - If not, the missing cell was a non-cell — fancy predictor + map didn't help.

Run: python papers/compression_experiment/cognimap_lossless_v4.py
"""

import time
import zlib
import hashlib
import struct
from pathlib import Path
from io import BytesIO

import numpy as np
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
TEST_IMAGE = SCRIPT_DIR / "test_image.jpg"
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ── YCoCg-R: lossless reversible RGB <-> YCoCg ────────────────────────

def rgb_to_ycocg_r(rgb: np.ndarray) -> np.ndarray:
    """Lossless reversible RGB -> YCoCg-R.

    Y in [0, 255], Co and Cg in roughly [-256, 255] (signed).
    Returns int16 array with same shape as input.
    """
    R = rgb[..., 0].astype(np.int32)
    G = rgb[..., 1].astype(np.int32)
    B = rgb[..., 2].astype(np.int32)
    Co = R - B
    t = B + (Co >> 1)
    Cg = G - t
    Y = t + (Cg >> 1)
    out = np.stack([Y, Co, Cg], axis=-1).astype(np.int16)
    return out


def ycocg_r_to_rgb(ycocg: np.ndarray) -> np.ndarray:
    """Inverse of rgb_to_ycocg_r. Lossless."""
    Y = ycocg[..., 0].astype(np.int32)
    Co = ycocg[..., 1].astype(np.int32)
    Cg = ycocg[..., 2].astype(np.int32)
    t = Y - (Cg >> 1)
    G = Cg + t
    B = t - (Co >> 1)
    R = B + Co
    out = np.stack([R, G, B], axis=-1)
    # Clip to uint8 range (input was uint8, so output must be too)
    out = np.clip(out, 0, 255).astype(np.uint8)
    return out


# ── Predictors (per-pixel, causal, no clamps so int16 ranges work) ────
# Predictors operate on int16 arrays. They do NOT clamp to [0, 255]
# because input may be Co/Cg with negative values. Residual still
# carries the exact diff so losslessness is preserved.

def pred_left(img, y, x):
    if x == 0:
        return np.int16(128) if y == 0 else img[y - 1, x]
    return img[y, x - 1]


def pred_top(img, y, x):
    if y == 0:
        return np.int16(128) if x == 0 else img[y, x - 1]
    return img[y - 1, x]


def pred_avg(img, y, x):
    if y == 0 and x == 0:
        return np.int16(128)
    if y == 0:
        return img[y, x - 1]
    if x == 0:
        return img[y - 1, x]
    return (img[y, x - 1].astype(np.int32) + img[y - 1, x].astype(np.int32)) // 2


def pred_paeth(img, y, x):
    if y == 0 and x == 0:
        return np.int16(128)
    if y == 0:
        return img[y, x - 1]
    if x == 0:
        return img[y - 1, x]
    a = img[y, x - 1].astype(np.int32)
    b = img[y - 1, x].astype(np.int32)
    c = img[y - 1, x - 1].astype(np.int32)
    p = a + b - c
    pa = np.abs(p - a)
    pb = np.abs(p - b)
    pc = np.abs(p - c)
    if hasattr(pa, "__len__"):
        result = np.zeros_like(a, dtype=np.int16)
        for ch in range(len(pa)):
            if pa[ch] <= pb[ch] and pa[ch] <= pc[ch]:
                result[ch] = a[ch]
            elif pb[ch] <= pc[ch]:
                result[ch] = b[ch]
            else:
                result[ch] = c[ch]
        return result
    if pa <= pb and pa <= pc:
        return np.int16(a)
    if pb <= pc:
        return np.int16(b)
    return np.int16(c)


def pred_diagonal(img, y, x):
    if y == 0 or x == 0:
        return pred_avg(img, y, x)
    return img[y - 1, x - 1]


def pred_gradient(img, y, x):
    """Basic gradient: left + top - top_left. NO clamp to [0, 255]
    so this works on signed Co/Cg channels (D2 in baseline notes)."""
    if y == 0 or x == 0:
        return pred_avg(img, y, x)
    return (
        img[y, x - 1].astype(np.int32)
        + img[y - 1, x].astype(np.int32)
        - img[y - 1, x - 1].astype(np.int32)
    ).astype(np.int16)


def pred_median(img, y, x):
    if y == 0 or x == 0:
        return pred_avg(img, y, x)
    vals = np.array(
        [img[y, x - 1], img[y - 1, x], img[y - 1, x - 1]], dtype=np.int16
    )
    if hasattr(vals[0], "__len__"):
        return np.median(vals, axis=0).astype(np.int16)
    return np.int16(np.median(vals))


def pred_calic7(img, y, x):
    """CALIC-7: 7-neighbor gradient-adaptive predictor (from v3.compress_calic_v2).

    Uses W, N, NW, NE, WW, NN, NNW. Falls back to Paeth in boundary regions.
    No range clamp; works on signed channels.
    """
    h = img.shape[0]
    w = img.shape[1]
    if y == 0 and x == 0:
        return np.int16(128) if img.ndim == 2 else np.full(img.shape[2], 128, dtype=np.int16)
    if y == 0:
        return img[y, x - 1]
    if x == 0:
        return img[y - 1, x]
    if y == 1 or x == 1 or x >= w - 1:
        return pred_paeth(img, y, x)

    W = img[y, x - 1].astype(np.int32)
    N = img[y - 1, x].astype(np.int32)
    NW = img[y - 1, x - 1].astype(np.int32)
    NE = img[y - 1, x + 1].astype(np.int32)
    WW = img[y, x - 2].astype(np.int32)
    NNW = img[y - 2, x - 1].astype(np.int32)

    dh = np.abs(W - NW) + np.abs(N - NE) + np.abs(NW - NNW)
    dv = np.abs(N - NW) + np.abs(W - WW) + np.abs(NW - NNW)

    if hasattr(dh, "__len__"):
        dh_s = int(dh.sum())
        dv_s = int(dv.sum())
    else:
        dh_s = int(dh)
        dv_s = int(dv)

    if dh_s > dv_s + 80:
        return N.astype(np.int16)
    if dv_s > dh_s + 80:
        return W.astype(np.int16)
    if dh_s > dv_s + 32:
        return ((3 * N + W) // 4).astype(np.int16)
    if dv_s > dh_s + 32:
        return ((3 * W + N) // 4).astype(np.int16)
    base = (W + N) // 2
    correction = (NE - NW) // 4
    return (base + correction).astype(np.int16)


PREDICTORS = [
    ("left", pred_left),
    ("top", pred_top),
    ("avg", pred_avg),
    ("paeth", pred_paeth),
    ("diagonal", pred_diagonal),
    ("gradient", pred_gradient),
    ("median", pred_median),
    ("calic7", pred_calic7),  # 8th — the v4 addition
]
N_PREDICTORS = len(PREDICTORS)


# ── Adaptive Block Compression on YCoCg-R Image ────────────────────────

def compress_adaptive_ycocg(image_rgb: np.ndarray, block_size: int = 4) -> tuple:
    """Apply YCoCg-R, then v1-style per-block best-predictor selection."""
    if image_rgb.ndim != 3 or image_rgb.shape[2] != 3:
        raise ValueError("v4 expects 3-channel RGB input")

    h, w, _ = image_rgb.shape
    channels = 3

    # YCoCg-R: int16 throughout. Co, Cg may be negative.
    ycocg = rgb_to_ycocg_r(image_rgb)  # int16

    bh = (h + block_size - 1) // block_size
    bw = (w + block_size - 1) // block_size

    best_strategy = np.zeros((bh, bw), dtype=np.uint8)
    all_residuals = np.zeros_like(ycocg)
    predictor_wins = [0] * N_PREDICTORS

    for by in range(bh):
        for bx in range(bw):
            y0, x0 = by * block_size, bx * block_size
            y1, x1 = min(y0 + block_size, h), min(x0 + block_size, w)

            best_cost = float("inf")
            best_pred_idx = 0
            best_residual = None

            for pred_idx, (_, pred_fn) in enumerate(PREDICTORS):
                block_residual = np.zeros(
                    (y1 - y0, x1 - x0, channels), dtype=np.int16
                )
                for y in range(y0, y1):
                    for x in range(x0, x1):
                        pred_val = pred_fn(ycocg, y, x)
                        block_residual[y - y0, x - x0] = (
                            ycocg[y, x].astype(np.int32) - pred_val.astype(np.int32)
                        ).astype(np.int16)
                cost = int(np.abs(block_residual).sum())
                if cost < best_cost:
                    best_cost = cost
                    best_pred_idx = pred_idx
                    best_residual = block_residual

            best_strategy[by, bx] = best_pred_idx
            all_residuals[y0:y1, x0:x1] = best_residual
            predictor_wins[best_pred_idx] += 1

    # Serialize. After YCoCg-R the residuals can exceed int8 range
    # (Co/Cg residuals span [-512, 511]); always store int16.
    strategy_bytes = best_strategy.tobytes()
    residual_bytes = all_residuals.astype(np.int16).tobytes()

    compressed_strategy = zlib.compress(strategy_bytes, 9)
    compressed_residual = zlib.compress(residual_bytes, 9)

    # Header: h, w, channels, block_size + lens
    header = struct.pack("IIII", h, w, channels, block_size)
    total = (
        header
        + struct.pack("II", len(compressed_strategy), len(compressed_residual))
        + compressed_strategy
        + compressed_residual
    )

    cognimap = {
        "predictor_wins": {
            PREDICTORS[i][0]: predictor_wins[i] for i in range(N_PREDICTORS)
        },
        "residual_stats": {
            "mean_abs": float(np.abs(all_residuals).mean()),
            "max_abs": int(np.abs(all_residuals).max()),
            "zeros_pct": float(
                np.sum(all_residuals == 0) / max(all_residuals.size, 1) * 100
            ),
        },
        "sizes": {
            "raw": image_rgb.nbytes,
            "strategy_map": len(compressed_strategy),
            "residual": len(compressed_residual),
            "total": len(total),
        },
        "strategy_map_shape": list(best_strategy.shape),
    }
    return total, cognimap, best_strategy


def decompress_adaptive_ycocg(compressed: bytes) -> np.ndarray:
    """Decompress: read strategy map, replay predictions on YCoCg, inverse to RGB."""
    offset = 0
    h, w, channels, block_size = struct.unpack_from("IIII", compressed, offset)
    offset += 16
    strat_len, res_len = struct.unpack_from("II", compressed, offset)
    offset += 8

    strategy_data = zlib.decompress(compressed[offset : offset + strat_len])
    offset += strat_len
    residual_data = zlib.decompress(compressed[offset : offset + res_len])

    bh = (h + block_size - 1) // block_size
    bw = (w + block_size - 1) // block_size
    strategy = np.frombuffer(strategy_data, dtype=np.uint8).reshape(bh, bw)

    shape = (h, w, channels)
    residual = np.frombuffer(residual_data, dtype=np.int16).reshape(shape)

    # IMPORTANT: iterate pixel-by-pixel in raster order, NOT block-by-block.
    # pred_calic7 references NE = (y-1, x+1). With block-order iteration,
    # NE for the rightmost column of any non-rightmost block lives in a
    # future (not-yet-decoded) block, so the decoder would see zeros where
    # the encoder saw original pixels — predictions diverge, lossless breaks.
    # Raster order guarantees all causal neighbors (left, top, NW, NE, WW,
    # NN, NNW) are already reconstructed by the time we process (y, x).
    ycocg = np.zeros(shape, dtype=np.int16)
    for y in range(h):
        for x in range(w):
            by = y // block_size
            bx = x // block_size
            pred_idx = int(strategy[by, bx])
            _, pred_fn = PREDICTORS[pred_idx]
            pred_val = pred_fn(ycocg, y, x)
            ycocg[y, x] = (
                pred_val.astype(np.int32) + residual[y, x].astype(np.int32)
            ).astype(np.int16)

    return ycocg_r_to_rgb(ycocg)


# ── Main ───────────────────────────────────────────────────────────────

def run_experiment():
    print("=" * 70)
    print("CogniMap Lossless v4 — v1 strategy map + CALIC-7 + YCoCg-R")
    print("=" * 70)

    img = Image.open(str(TEST_IMAGE))
    image = np.array(img)
    if image.ndim == 2:
        image = np.stack([image] * 3, axis=-1)
    elif image.shape[2] == 4:
        image = image[..., :3]
    print(f"\nImage: {TEST_IMAGE.name} | shape={image.shape} | raw={image.nbytes/1024:.0f} KB")
    original_hash = hashlib.sha256(image.tobytes()).hexdigest()[:16]
    print(f"SHA256 (orig, first 16): {original_hash}")

    # Quick YCoCg-R sanity check (round-trip on the raw image, no compression)
    ycocg_test = rgb_to_ycocg_r(image)
    rgb_back = ycocg_r_to_rgb(ycocg_test)
    assert np.array_equal(image, rgb_back), (
        "YCoCg-R round-trip is not lossless — investigate before benchmarking"
    )
    print("YCoCg-R round-trip: lossless OK")

    # ── Baselines ─────────────────────────────────────────────────────
    print("\n" + "-" * 70)
    print("BASELINES")
    print("-" * 70)

    buf = BytesIO()
    Image.fromarray(image).save(buf, format="PNG", optimize=True)
    png_size = buf.tell()
    print(f"  PNG:           {png_size/1024:.0f} KB ({image.nbytes/png_size:.1f}x)")

    try:
        buf = BytesIO()
        Image.fromarray(image).save(buf, format="WEBP", lossless=True)
        webp_size = buf.tell()
        print(f"  WebP lossless: {webp_size/1024:.0f} KB ({image.nbytes/webp_size:.1f}x)")
    except Exception:
        pass

    raw_zlib = zlib.compress(image.tobytes(), 9)
    print(f"  zlib raw:      {len(raw_zlib)/1024:.0f} KB ({image.nbytes/len(raw_zlib):.1f}x)")

    # v1 reference (from prior experiment, not re-run)
    print("  v1 ref:        2031 KB (from prior run, current best)")
    print("  v3 ref:        2207 KB (from prior run)")

    # ── v4: YCoCg-R + strategy map + CALIC-7 ──────────────────────────
    print("\n" + "-" * 70)
    print("COGNIMAP v4: YCoCg-R + strategy map + CALIC-7")
    print("-" * 70)

    for bs in [16, 8, 4]:
        print(f"\n  Block size: {bs}x{bs}")
        t0 = time.time()
        compressed, cognimap, strategy = compress_adaptive_ycocg(image, block_size=bs)
        ct = time.time() - t0

        t0 = time.time()
        reconstructed = decompress_adaptive_ycocg(compressed)
        dt = time.time() - t0

        identical = np.array_equal(image, reconstructed)
        max_diff = (
            int(np.max(np.abs(image.astype(np.int16) - reconstructed.astype(np.int16))))
            if reconstructed.shape == image.shape
            else -1
        )
        recon_hash = hashlib.sha256(reconstructed.tobytes()).hexdigest()[:16]

        cogni_size = len(compressed)
        ratio = image.nbytes / cogni_size

        print(f"    Size:      {cogni_size/1024:.0f} KB ({ratio:.1f}x)")
        print(
            f"    Lossless:  {'YES' if identical else 'NO'} (max diff: {max_diff}, sha256={recon_hash})"
        )
        print(f"    Timing:    compress={ct:.1f}s | decompress={dt:.1f}s")

        wins = cognimap["predictor_wins"]
        total_blocks = sum(wins.values())
        print(f"    Predictor usage ({total_blocks} blocks):")
        for pred_name, count in sorted(wins.items(), key=lambda kv: -kv[1]):
            if count > 0:
                pct = count / total_blocks * 100
                print(f"      {pred_name:10s}: {count:5d} ({pct:.0f}%)")

        rs = cognimap["residual_stats"]
        print(
            f"    Residuals: mean|r|={rs['mean_abs']:.1f} max|r|={rs['max_abs']} zeros={rs['zeros_pct']:.0f}%"
        )

        vs_zlib = (1 - cogni_size / len(raw_zlib)) * 100
        vs_png = (1 - cogni_size / png_size) * 100
        vs_v1 = (1 - cogni_size / (2031 * 1024)) * 100
        vs_v3 = (1 - cogni_size / (2207 * 1024)) * 100
        print(f"    vs zlib:   {'BETTER' if vs_zlib > 0 else 'WORSE'} by {abs(vs_zlib):.1f}%")
        print(f"    vs PNG:    {'BETTER' if vs_png > 0 else 'WORSE'} by {abs(vs_png):.1f}%")
        print(f"    vs v1:     {'BETTER' if vs_v1 > 0 else 'WORSE'} by {abs(vs_v1):.1f}%")
        print(f"    vs v3:     {'BETTER' if vs_v3 > 0 else 'WORSE'} by {abs(vs_v3):.1f}%")

    # ── Summary ──────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("  v4 fills the missing cell in the v1-vs-v3 comparison:")
    print("    v1 = strategy map YES, CALIC-7 NO  -> 2031 KB")
    print("    v3 = strategy map NO,  CALIC-7 YES -> 2207 KB")
    print("    v4 = strategy map YES, CALIC-7 YES, plus YCoCg-R")
    print("  Decision rule: if v4 beats v1 by >=5%, ship as new baseline.")


if __name__ == "__main__":
    run_experiment()
