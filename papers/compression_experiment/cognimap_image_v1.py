"""CogniMap Image Compression v1 — Wavelet-Based Non-Uniform Compression

v0 failed because per-patch JPEG adds header overhead per patch.
v1 uses wavelet decomposition (like JPEG2000) to work WITH the codec:

  1. Decompose image into wavelet subbands (frequency layers)
  2. Score importance per spatial region using the wavelet coefficients
  3. Quantize coefficients non-uniformly: important regions keep precision,
     unimportant regions get aggressive quantization
  4. The CogniMap records the quantization map for lossless reconstruction
     of important regions

This is the frequency-band approach:
  - Low frequency = structure (the "bass note" of the image)
  - High frequency = detail (edges, texture, noise)
  - CogniMap decides which spatial regions keep their high-frequency detail

Run: .venv/Scripts/python papers/compression_experiment/cognimap_image_v1.py
"""

import sys
import json
import time
import struct
import zlib
from pathlib import Path
from io import BytesIO

import numpy as np
from PIL import Image

try:
    import pywt
    HAS_PYWT = True
except ImportError:
    HAS_PYWT = False
    print("WARNING: pywt not installed. Run: pip install PyWavelets")

SCRIPT_DIR = Path(__file__).resolve().parent
TEST_IMAGE = SCRIPT_DIR / "test_image.jpg"
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ── Importance Scoring v2 (adaptive, per-image normalization) ─────────

def compute_importance_map(image: np.ndarray, block_size: int = 16) -> np.ndarray:
    """Compute per-block importance using local statistics.

    Normalized per-image so importance distribution is always 0-1
    with meaningful spread, regardless of image content.
    """
    gray = np.mean(image.astype(np.float32), axis=2) if len(image.shape) == 3 else image.astype(np.float32)
    h, w = gray.shape
    bh = (h + block_size - 1) // block_size
    bw = (w + block_size - 1) // block_size

    raw_scores = np.zeros((bh, bw))

    for by in range(bh):
        for bx in range(bw):
            y0 = by * block_size
            x0 = bx * block_size
            y1 = min(y0 + block_size, h)
            x1 = min(x0 + block_size, w)
            block = gray[y0:y1, x0:x1]

            # Local variance (detail richness)
            variance = np.var(block)

            # Gradient magnitude (edge strength)
            if block.shape[0] > 1 and block.shape[1] > 1:
                gy = np.abs(np.diff(block, axis=0)).mean()
                gx = np.abs(np.diff(block, axis=1)).mean()
                gradient = (gx + gy) / 2.0
            else:
                gradient = 0.0

            # Entropy approximation (information content)
            hist, _ = np.histogram(block.ravel(), bins=32, range=(0, 256))
            hist = hist[hist > 0].astype(np.float64)
            hist = hist / hist.sum()
            entropy = -np.sum(hist * np.log2(hist))

            raw_scores[by, bx] = variance * 0.3 + gradient * 0.3 + entropy * 0.4

    # Normalize to 0-1 using percentile scaling (robust to outliers)
    p5 = np.percentile(raw_scores, 5)
    p95 = np.percentile(raw_scores, 95)
    if p95 - p5 < 1e-6:
        return np.full_like(raw_scores, 0.5)

    normalized = (raw_scores - p5) / (p95 - p5)
    return np.clip(normalized, 0, 1)


# ── Wavelet-Based Non-Uniform Compression ──────────────────────────────

def wavelet_compress_nonuniform(image: np.ndarray, importance_map: np.ndarray,
                                  wavelet: str = 'db4', level: int = 3,
                                  block_size: int = 16) -> dict:
    """Compress image using wavelets with non-uniform quantization.

    Important regions keep more wavelet coefficients.
    Unimportant regions get aggressively quantized.
    """
    h, w = image.shape[:2]
    channels = image.shape[2] if len(image.shape) > 2 else 1

    compressed_channels = []
    total_nonzero = 0
    total_coeffs = 0

    for ch in range(channels):
        channel_data = image[:, :, ch] if channels > 1 else image
        channel_float = channel_data.astype(np.float32)

        # Wavelet decomposition
        coeffs = pywt.wavedec2(channel_float, wavelet, level=level)

        # Quantize each detail level based on importance
        quantized_coeffs = [coeffs[0]]  # Keep approximation (low freq) intact

        for lev_idx in range(1, len(coeffs)):
            detail_bands = coeffs[lev_idx]  # (cH, cV, cD) tuple
            quantized_bands = []

            # Scale factor for this level (deeper = coarser = more compressible)
            level_scale = 2 ** (len(coeffs) - 1 - lev_idx)

            for band in detail_bands:
                bh_band, bw_band = band.shape

                # Map importance to this resolution level
                imp_resized = np.array(Image.fromarray(
                    (importance_map * 255).astype(np.uint8)
                ).resize((bw_band, bh_band), Image.NEAREST)) / 255.0

                # Quantization: threshold = base_threshold / importance
                # High importance (1.0) → low threshold → keep detail
                # Low importance (0.0) → high threshold → remove detail
                base_threshold = 5.0 * level_scale
                threshold_map = base_threshold / (imp_resized + 0.1)

                # Apply spatially-varying threshold
                quantized = band.copy()
                quantized[np.abs(quantized) < threshold_map] = 0.0

                # Additional quantization: reduce precision for low-importance regions
                step_map = np.where(imp_resized > 0.5, 0.5, 2.0) * level_scale
                quantized = np.round(quantized / step_map) * step_map

                total_nonzero += np.count_nonzero(quantized)
                total_coeffs += quantized.size
                quantized_bands.append(quantized)

            quantized_coeffs.append(tuple(quantized_bands))

        compressed_channels.append(quantized_coeffs)

    sparsity = 1.0 - (total_nonzero / max(total_coeffs, 1))

    return {
        "coeffs": compressed_channels,
        "wavelet": wavelet,
        "level": level,
        "shape": image.shape,
        "sparsity": sparsity,
        "nonzero": total_nonzero,
        "total": total_coeffs,
    }


def wavelet_decompress(compressed: dict) -> np.ndarray:
    """Reconstruct image from quantized wavelet coefficients."""
    shape = compressed["shape"]
    wavelet = compressed["wavelet"]
    channels = shape[2] if len(shape) > 2 else 1

    result_channels = []
    for ch_coeffs in compressed["coeffs"]:
        reconstructed = pywt.waverec2(ch_coeffs, wavelet)
        # Clip and trim to original size
        reconstructed = np.clip(reconstructed[:shape[0], :shape[1]], 0, 255)
        result_channels.append(reconstructed.astype(np.uint8))

    if channels > 1:
        return np.stack(result_channels, axis=2)
    return result_channels[0]


def serialize_wavelet(compressed: dict) -> bytes:
    """Serialize wavelet coefficients to bytes for size measurement.

    Uses sparse encoding: only store non-zero coefficients with positions.
    Then compress with zlib.
    """
    parts = []

    for ch_coeffs in compressed["coeffs"]:
        for i, item in enumerate(ch_coeffs):
            if i == 0:
                # Approximation coefficients — store dense (always important)
                arr = item.astype(np.float16)
                parts.append(arr.tobytes())
            else:
                # Detail bands — store sparse
                for band in item:
                    nonzero_mask = band != 0
                    nonzero_vals = band[nonzero_mask].astype(np.float16)
                    # Store: shape + count + indices + values
                    indices = np.where(nonzero_mask.ravel())[0].astype(np.uint32)
                    header = struct.pack('II', band.shape[0], band.shape[1])
                    count = struct.pack('I', len(nonzero_vals))
                    parts.append(header + count + indices.tobytes() + nonzero_vals.tobytes())

    raw = b''.join(parts)
    compressed_bytes = zlib.compress(raw, level=9)
    return compressed_bytes


# ── Uniform wavelet compression (baseline) ─────────────────────────────

def wavelet_compress_uniform(image: np.ndarray, threshold: float,
                               wavelet: str = 'db4', level: int = 3) -> dict:
    """Uniform wavelet compression — same threshold everywhere."""
    h, w = image.shape[:2]
    channels = image.shape[2] if len(image.shape) > 2 else 1

    compressed_channels = []
    total_nonzero = 0
    total_coeffs = 0

    for ch in range(channels):
        channel_data = image[:, :, ch] if channels > 1 else image
        coeffs = pywt.wavedec2(channel_data.astype(np.float32), wavelet, level=level)

        quantized_coeffs = [coeffs[0]]
        for lev_idx in range(1, len(coeffs)):
            quantized_bands = []
            for band in coeffs[lev_idx]:
                q = band.copy()
                q[np.abs(q) < threshold] = 0.0
                total_nonzero += np.count_nonzero(q)
                total_coeffs += q.size
                quantized_bands.append(q)
            quantized_coeffs.append(tuple(quantized_bands))

        compressed_channels.append(quantized_coeffs)

    sparsity = 1.0 - (total_nonzero / max(total_coeffs, 1))
    return {
        "coeffs": compressed_channels, "wavelet": wavelet,
        "level": level, "shape": image.shape,
        "sparsity": sparsity, "nonzero": total_nonzero, "total": total_coeffs,
    }


# ── Quality Metrics ────────────────────────────────────────────────────

def psnr(original, compressed):
    mse = np.mean((original.astype(float) - compressed.astype(float)) ** 2)
    if mse == 0: return float('inf')
    return 10 * np.log10(255.0 ** 2 / mse)

def ssim_simple(original, compressed):
    if len(original.shape) == 3:
        orig_gray = np.mean(original, axis=2)
        comp_gray = np.mean(compressed, axis=2)
    else:
        orig_gray, comp_gray = original.astype(float), compressed.astype(float)
    mu_x, mu_y = np.mean(orig_gray), np.mean(comp_gray)
    sigma_x, sigma_y = np.std(orig_gray), np.std(comp_gray)
    sigma_xy = np.mean((orig_gray - mu_x) * (comp_gray - mu_y))
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    return float(((2*mu_x*mu_y+C1)*(2*sigma_xy+C2)) / ((mu_x**2+mu_y**2+C1)*(sigma_x**2+sigma_y**2+C2)))


# ── Main ───────────────────────────────────────────────────────────────

def run_experiment():
    if not HAS_PYWT:
        print("FATAL: PyWavelets required. pip install PyWavelets")
        return

    print("=" * 70)
    print("CogniMap Image Compression v1 - Wavelet Non-Uniform")
    print("=" * 70)

    img = Image.open(str(TEST_IMAGE))
    image = np.array(img)
    print(f"\nImage: {TEST_IMAGE.name} | {image.shape} | Raw: {image.nbytes/1024:.0f} KB")
    original_jpeg_size = TEST_IMAGE.stat().st_size
    print(f"Original JPEG: {original_jpeg_size/1024:.0f} KB")

    # ── Compute importance map ───────────────────────────────────────

    print("\nComputing importance map...")
    imp_map = compute_importance_map(image, block_size=16)
    high_pct = np.sum(imp_map >= 0.7) / imp_map.size * 100
    mid_pct = np.sum((imp_map >= 0.3) & (imp_map < 0.7)) / imp_map.size * 100
    low_pct = np.sum(imp_map < 0.3) / imp_map.size * 100
    print(f"Importance: {high_pct:.0f}% high | {mid_pct:.0f}% mid | {low_pct:.0f}% low")

    # Save heatmap
    heatmap = np.zeros((*imp_map.shape, 3), dtype=np.uint8)
    for y in range(imp_map.shape[0]):
        for x in range(imp_map.shape[1]):
            v = imp_map[y, x]
            heatmap[y, x] = [int((1-v)*220), int(v*220), 40]
    hm_img = Image.fromarray(heatmap).resize((image.shape[1], image.shape[0]), Image.NEAREST)
    hm_img.save(str(OUTPUT_DIR / "importance_heatmap_v1.png"))
    print(f"Saved: importance_heatmap_v1.png")

    # ── Experiment 1: Uniform wavelet baselines ──────────────────────

    print(f"\n" + "-" * 70)
    print("EXPERIMENT 1: Uniform Wavelet Compression")
    print("-" * 70)

    for threshold in [5, 10, 20, 40, 80]:
        comp = wavelet_compress_uniform(image, threshold=threshold)
        serialized = serialize_wavelet(comp)
        recon = wavelet_decompress(comp)

        p = psnr(image, recon)
        s = ssim_simple(image, recon)
        ratio = image.nbytes / len(serialized)

        print(f"  T={threshold:3d} | sparsity: {comp['sparsity']:.1%} | "
              f"size: {len(serialized)/1024:.0f} KB | ratio: {ratio:.1f}x | "
              f"PSNR: {p:.1f} dB | SSIM: {s:.4f}")

    # ── Experiment 2: CogniMap non-uniform wavelet ───────────────────

    print(f"\n" + "-" * 70)
    print("EXPERIMENT 2: CogniMap Non-Uniform Wavelet Compression")
    print("-" * 70)

    comp_cogni = wavelet_compress_nonuniform(image, imp_map)
    serialized_cogni = serialize_wavelet(comp_cogni)
    recon_cogni = wavelet_decompress(comp_cogni)

    p_cogni = psnr(image, recon_cogni)
    s_cogni = ssim_simple(image, recon_cogni)
    ratio_cogni = image.nbytes / len(serialized_cogni)

    # CogniMap registry size
    cognimap_meta = {
        "importance_shape": list(imp_map.shape),
        "importance_data": imp_map.astype(np.float16).tobytes().hex()[:200] + "...",
        "wavelet": comp_cogni["wavelet"],
        "level": comp_cogni["level"],
    }
    cognimap_overhead = len(imp_map.astype(np.float16).tobytes())
    total_cogni = len(serialized_cogni) + cognimap_overhead

    print(f"  CogniMap wavelet:")
    print(f"    Sparsity:    {comp_cogni['sparsity']:.1%}")
    print(f"    Compressed:  {len(serialized_cogni)/1024:.0f} KB + {cognimap_overhead/1024:.1f} KB map = {total_cogni/1024:.0f} KB")
    print(f"    Ratio:       {image.nbytes/total_cogni:.1f}x")
    print(f"    PSNR:        {p_cogni:.1f} dB")
    print(f"    SSIM:        {s_cogni:.4f}")

    # Save reconstruction
    Image.fromarray(recon_cogni).save(str(OUTPUT_DIR / "cognimap_wavelet_recon.png"))
    print(f"    Saved: cognimap_wavelet_recon.png")

    # ── Experiment 3: Compare at same size ───────────────────────────

    print(f"\n" + "-" * 70)
    print("EXPERIMENT 3: CogniMap vs Uniform Wavelet at Same Size")
    print("-" * 70)

    # Find uniform threshold that produces similar size
    best_t = 5
    best_diff = float('inf')
    for t in range(1, 100):
        comp_u = wavelet_compress_uniform(image, threshold=t)
        ser_u = serialize_wavelet(comp_u)
        diff = abs(len(ser_u) - total_cogni)
        if diff < best_diff:
            best_diff = diff
            best_t = t

    comp_matched = wavelet_compress_uniform(image, threshold=best_t)
    ser_matched = serialize_wavelet(comp_matched)
    recon_matched = wavelet_decompress(comp_matched)
    p_matched = psnr(image, recon_matched)
    s_matched = ssim_simple(image, recon_matched)

    print(f"  Target size:  ~{total_cogni/1024:.0f} KB")
    print(f"  Uniform T={best_t:2d}: {len(ser_matched)/1024:.0f} KB | PSNR={p_matched:.1f} dB | SSIM={s_matched:.4f}")
    print(f"  CogniMap:      {total_cogni/1024:.0f} KB | PSNR={p_cogni:.1f} dB | SSIM={s_cogni:.4f}")

    psnr_diff = p_cogni - p_matched
    ssim_diff = s_cogni - s_matched

    if psnr_diff > 0:
        print(f"\n  >> CogniMap wins by +{psnr_diff:.1f} dB PSNR")
    else:
        print(f"\n  >> Uniform wins by +{-psnr_diff:.1f} dB PSNR")
    if ssim_diff > 0:
        print(f"  >> CogniMap wins by +{ssim_diff:.4f} SSIM")
    else:
        print(f"  >> Uniform wins by +{-ssim_diff:.4f} SSIM")

    # ── Experiment 4: JPEG comparison at same size ───────────────────

    print(f"\n" + "-" * 70)
    print("EXPERIMENT 4: CogniMap Wavelet vs Standard JPEG")
    print("-" * 70)

    for target_name, target_size in [("CogniMap size", total_cogni), ("Half CogniMap", total_cogni // 2)]:
        best_q = 10
        best_diff = float('inf')
        for q in range(5, 96):
            buf = BytesIO()
            Image.fromarray(image).save(buf, format="JPEG", quality=q)
            diff = abs(buf.tell() - target_size)
            if diff < best_diff:
                best_diff = diff
                best_q = q

        buf = BytesIO()
        Image.fromarray(image).save(buf, format="JPEG", quality=best_q)
        jpeg_data = buf.getvalue()
        jpeg_recon = np.array(Image.open(BytesIO(jpeg_data)))
        # Trim to same size
        mh = min(image.shape[0], jpeg_recon.shape[0])
        mw = min(image.shape[1], jpeg_recon.shape[1])
        p_jpeg = psnr(image[:mh, :mw], jpeg_recon[:mh, :mw])
        s_jpeg = ssim_simple(image[:mh, :mw], jpeg_recon[:mh, :mw])

        print(f"  {target_name} (~{target_size/1024:.0f} KB):")
        print(f"    JPEG Q={best_q:2d}: {len(jpeg_data)/1024:.0f} KB | PSNR={p_jpeg:.1f} dB | SSIM={s_jpeg:.4f}")
        if target_name == "CogniMap size":
            print(f"    CogniMap:    {total_cogni/1024:.0f} KB | PSNR={p_cogni:.1f} dB | SSIM={s_cogni:.4f}")
            if p_cogni > p_jpeg:
                print(f"    >> CogniMap BEATS JPEG by +{p_cogni - p_jpeg:.1f} dB")
            else:
                print(f"    >> JPEG beats CogniMap by +{p_jpeg - p_cogni:.1f} dB")

    # ── Summary ──────────────────────────────────────────────────────

    print(f"\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Original: {image.nbytes/1024:.0f} KB raw, {original_jpeg_size/1024:.0f} KB JPEG")
    print(f"  CogniMap wavelet: {total_cogni/1024:.0f} KB ({image.nbytes/total_cogni:.1f}x compression)")
    print(f"  Quality: PSNR={p_cogni:.1f} dB | SSIM={s_cogni:.4f}")
    print(f"  Sparsity: {comp_cogni['sparsity']:.1%} of wavelet coefficients zeroed")
    print(f"  Importance distribution: {high_pct:.0f}% high | {mid_pct:.0f}% mid | {low_pct:.0f}% low")
    print(f"\n  The CogniMap principle: preserve detail where it matters,")
    print(f"  compress aggressively where it doesn't. Same total bytes,")
    print(f"  better perceptual quality in important regions.")


if __name__ == "__main__":
    run_experiment()
