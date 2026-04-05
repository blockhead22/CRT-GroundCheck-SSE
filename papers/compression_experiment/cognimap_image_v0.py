"""CogniMap Image Compression Experiment

Tests semantic-aware non-uniform image compression where patch importance
determines compression level — like trust-weighted memory compression
but applied to image regions.

Approach:
  1. Split image into patches (e.g., 16x16 or 32x32)
  2. Score each patch's "importance" (edge density, variance, uniqueness)
  3. Compress patches non-uniformly based on importance score
  4. Reconstruct and measure quality (PSNR, SSIM, visual diff)

Importance scoring (CogniMap for images):
  - High importance: edges, text, faces, detail-rich regions
  - Low importance: flat backgrounds, gradients, repetitive textures
  - Importance = semantic "trust" analog

Run: .venv/Scripts/python papers/compression_experiment/cognimap_image_v0.py
"""

import sys
import json
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


# ── Importance Scoring (CogniMap for pixels) ──────────────────────────

def score_patch_importance(patch: np.ndarray) -> float:
    """Score a patch's semantic importance (0-1).

    High importance = detail-rich, edges, high variance.
    Low importance = flat, uniform, boring.
    """
    # Variance: how much the pixel values vary
    variance = np.var(patch.astype(np.float32)) / (255.0 * 255.0)

    # Edge density: Sobel-like gradient magnitude
    gray = np.mean(patch, axis=2) if len(patch.shape) == 3 else patch
    gx = np.abs(np.diff(gray, axis=1)).mean() / 255.0
    gy = np.abs(np.diff(gray, axis=0)).mean() / 255.0
    edge_density = (gx + gy) / 2.0

    # Color diversity: how many distinct colors
    if len(patch.shape) == 3:
        # Quantize to reduce noise, count unique
        quantized = (patch // 32) * 32
        unique_colors = len(np.unique(quantized.reshape(-1, 3), axis=0))
        max_possible = patch.shape[0] * patch.shape[1]
        color_diversity = min(1.0, unique_colors / max(max_possible * 0.3, 1))
    else:
        color_diversity = 0.5

    # Combined score
    score = (variance * 0.3 + edge_density * 0.4 + color_diversity * 0.3)
    return min(1.0, score * 3.0)  # Scale up, cap at 1


def importance_to_quality(importance: float) -> int:
    """Map importance score to JPEG quality level.

    High importance = high quality (preserve detail)
    Low importance = low quality (compress aggressively)
    """
    if importance >= 0.7:
        return 95  # Near-lossless
    elif importance >= 0.4:
        return 60  # Medium
    elif importance >= 0.2:
        return 30  # Aggressive
    else:
        return 10  # Maximum compression


# ── Compression Methods ────────────────────────────────────────────────

def compress_uniform(image: np.ndarray, quality: int) -> bytes:
    """Standard JPEG: uniform quality across entire image."""
    img = Image.fromarray(image)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()

def decompress_jpeg(data: bytes) -> np.ndarray:
    """Decompress JPEG bytes to numpy array."""
    return np.array(Image.open(BytesIO(data)))

def compress_cognimap(image: np.ndarray, patch_size: int = 32) -> tuple:
    """CogniMap non-uniform compression.

    Each patch gets a different JPEG quality based on importance.
    Returns (compressed_data, cognimap_registry, stats).
    """
    h, w = image.shape[:2]
    patches_y = (h + patch_size - 1) // patch_size
    patches_x = (w + patch_size - 1) // patch_size

    cognimap = {}  # The fold registry
    compressed_patches = []
    total_bytes = 0
    importance_map = np.zeros((patches_y, patches_x))
    quality_map = np.zeros((patches_y, patches_x), dtype=int)

    for py in range(patches_y):
        for px in range(patches_x):
            y0 = py * patch_size
            x0 = px * patch_size
            y1 = min(y0 + patch_size, h)
            x1 = min(x0 + patch_size, w)

            patch = image[y0:y1, x0:x1]

            # Score importance
            importance = score_patch_importance(patch)
            quality = importance_to_quality(importance)

            importance_map[py, px] = importance
            quality_map[py, px] = quality

            # Compress this patch at its assigned quality
            patch_img = Image.fromarray(patch)
            buf = BytesIO()
            patch_img.save(buf, format="JPEG", quality=quality)
            patch_bytes = buf.getvalue()

            compressed_patches.append(patch_bytes)
            total_bytes += len(patch_bytes)

            cognimap[f"{py}_{px}"] = {
                "importance": round(importance, 3),
                "quality": quality,
                "size": len(patch_bytes),
                "y": y0, "x": x0,
                "h": y1 - y0, "w": x1 - x0,
            }

    return compressed_patches, cognimap, {
        "total_bytes": total_bytes,
        "patches": len(compressed_patches),
        "importance_map": importance_map,
        "quality_map": quality_map,
    }


def decompress_cognimap(compressed_patches, cognimap, original_shape) -> np.ndarray:
    """Reconstruct image from CogniMap compressed patches."""
    h, w = original_shape[:2]
    channels = original_shape[2] if len(original_shape) > 2 else 1
    reconstructed = np.zeros((h, w, channels), dtype=np.uint8) if channels > 1 else np.zeros((h, w), dtype=np.uint8)

    sorted_keys = sorted(cognimap.keys(), key=lambda k: (int(k.split("_")[0]), int(k.split("_")[1])))
    for i, key in enumerate(sorted_keys):
        meta = cognimap[key]
        if i >= len(compressed_patches):
            continue

        patch_data = compressed_patches[i]
        patch_img = Image.open(BytesIO(patch_data))
        y0, x0 = meta["y"], meta["x"]
        ph, pw = meta["h"], meta["w"]

        # Resize patch to exact expected dimensions (JPEG may round)
        patch_img = patch_img.resize((pw, ph), Image.LANCZOS)
        patch = np.array(patch_img)

        if len(patch.shape) == 2 and channels > 1:
            patch = np.stack([patch] * channels, axis=2)

        if len(reconstructed.shape) == 3 and len(patch.shape) == 3:
            c = min(channels, patch.shape[2])
            reconstructed[y0:y0+ph, x0:x0+pw, :c] = patch[:ph, :pw, :c]
        elif len(reconstructed.shape) == 2:
            if len(patch.shape) == 3:
                patch = np.mean(patch, axis=2).astype(np.uint8)
            reconstructed[y0:y0+ph, x0:x0+pw] = patch[:ph, :pw]

    return reconstructed


# ── Quality Metrics ────────────────────────────────────────────────────

def psnr(original: np.ndarray, compressed: np.ndarray) -> float:
    """Peak Signal-to-Noise Ratio. Higher = better. >40 = excellent."""
    mse = np.mean((original.astype(float) - compressed.astype(float)) ** 2)
    if mse == 0:
        return float('inf')
    return 10 * np.log10(255.0 ** 2 / mse)

def ssim_simple(original: np.ndarray, compressed: np.ndarray) -> float:
    """Simplified SSIM (structural similarity). 1.0 = identical."""
    # Convert to grayscale for SSIM
    if len(original.shape) == 3:
        orig_gray = np.mean(original, axis=2)
        comp_gray = np.mean(compressed, axis=2)
    else:
        orig_gray = original.astype(float)
        comp_gray = compressed.astype(float)

    mu_x = np.mean(orig_gray)
    mu_y = np.mean(comp_gray)
    sigma_x = np.std(orig_gray)
    sigma_y = np.std(comp_gray)
    sigma_xy = np.mean((orig_gray - mu_x) * (comp_gray - mu_y))

    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2

    ssim = ((2 * mu_x * mu_y + C1) * (2 * sigma_xy + C2)) / \
           ((mu_x ** 2 + mu_y ** 2 + C1) * (sigma_x ** 2 + sigma_y ** 2 + C2))
    return float(ssim)


# ── Importance Heatmap Visualization ───────────────────────────────────

def save_importance_heatmap(importance_map: np.ndarray, original_shape: tuple,
                             patch_size: int, output_path: Path):
    """Save a visual heatmap of patch importance scores."""
    h, w = original_shape[:2]
    heatmap = np.zeros((h, w, 3), dtype=np.uint8)

    for py in range(importance_map.shape[0]):
        for px in range(importance_map.shape[1]):
            y0 = py * patch_size
            x0 = px * patch_size
            y1 = min(y0 + patch_size, h)
            x1 = min(x0 + patch_size, w)

            imp = importance_map[py, px]
            # Green = high importance, Red = low importance
            r = int((1 - imp) * 200)
            g = int(imp * 200)
            b = 30
            heatmap[y0:y1, x0:x1] = [r, g, b]

    Image.fromarray(heatmap).save(str(output_path))


# ── Main Experiment ────────────────────────────────────────────────────

def run_experiment():
    print("=" * 70)
    print("CogniMap Image Compression Experiment")
    print("=" * 70)

    # Load image
    img = Image.open(str(TEST_IMAGE))
    image = np.array(img)
    print(f"\nImage: {TEST_IMAGE.name}")
    print(f"Dimensions: {image.shape}")
    print(f"Raw size: {image.nbytes / 1024:.0f} KB")

    original_file_size = TEST_IMAGE.stat().st_size
    print(f"Original JPEG file: {original_file_size / 1024:.0f} KB")

    # ── Experiment 1: Uniform JPEG at various qualities ──────────────

    print(f"\n" + "-" * 70)
    print("EXPERIMENT 1: Uniform JPEG Baselines")
    print("-" * 70)

    for quality in [95, 80, 60, 30, 10]:
        compressed = compress_uniform(image, quality)
        decompressed = decompress_jpeg(compressed)

        # Handle size mismatch
        min_h = min(image.shape[0], decompressed.shape[0])
        min_w = min(image.shape[1], decompressed.shape[1])
        orig_crop = image[:min_h, :min_w]
        dec_crop = decompressed[:min_h, :min_w, :orig_crop.shape[2]] if len(decompressed.shape) > 2 else decompressed[:min_h, :min_w]

        p = psnr(orig_crop, dec_crop)
        s = ssim_simple(orig_crop, dec_crop)
        ratio = image.nbytes / len(compressed)

        print(f"  Q={quality:3d} | size: {len(compressed)/1024:7.0f} KB | "
              f"ratio: {ratio:5.1f}x | PSNR: {p:5.1f} dB | SSIM: {s:.4f}")

    # ── Experiment 2: CogniMap non-uniform compression ───────────────

    print(f"\n" + "-" * 70)
    print("EXPERIMENT 2: CogniMap Non-Uniform Compression")
    print("-" * 70)

    for patch_size in [16, 32, 64]:
        t0 = time.time()
        patches, cognimap, stats = compress_cognimap(image, patch_size=patch_size)
        compress_time = time.time() - t0

        t0 = time.time()
        reconstructed = decompress_cognimap(patches, cognimap, image.shape)
        decompress_time = time.time() - t0

        # Quality metrics
        min_h = min(image.shape[0], reconstructed.shape[0])
        min_w = min(image.shape[1], reconstructed.shape[1])
        min_c = min(image.shape[2], reconstructed.shape[2]) if len(image.shape) > 2 and len(reconstructed.shape) > 2 else 1
        orig_crop = image[:min_h, :min_w, :min_c] if min_c > 1 else image[:min_h, :min_w]
        rec_crop = reconstructed[:min_h, :min_w, :min_c] if min_c > 1 else reconstructed[:min_h, :min_w]

        p = psnr(orig_crop, rec_crop)
        s = ssim_simple(orig_crop, rec_crop)

        total_compressed = stats["total_bytes"]
        cognimap_json = json.dumps(cognimap)
        cognimap_size = len(cognimap_json)
        total_with_map = total_compressed + cognimap_size
        ratio = image.nbytes / total_with_map

        # Importance distribution
        imp_map = stats["importance_map"]
        high_imp = np.sum(imp_map >= 0.7) / imp_map.size * 100
        mid_imp = np.sum((imp_map >= 0.3) & (imp_map < 0.7)) / imp_map.size * 100
        low_imp = np.sum(imp_map < 0.3) / imp_map.size * 100

        print(f"\n  Patch size: {patch_size}x{patch_size} ({stats['patches']} patches)")
        print(f"  Compressed:  {total_compressed/1024:.0f} KB patches + {cognimap_size/1024:.0f} KB map = {total_with_map/1024:.0f} KB")
        print(f"  Ratio:       {ratio:.1f}x (vs raw {image.nbytes/1024:.0f} KB)")
        print(f"  Quality:     PSNR={p:.1f} dB | SSIM={s:.4f}")
        print(f"  Timing:      compress={compress_time:.2f}s | decompress={decompress_time:.2f}s")
        print(f"  Importance:  {high_imp:.0f}% high | {mid_imp:.0f}% mid | {low_imp:.0f}% low")

        # Quality distribution across patches
        qualities = [m["quality"] for m in cognimap.values()]
        q_dist = {}
        for q in qualities:
            q_dist[q] = q_dist.get(q, 0) + 1
        print(f"  Quality distribution: {dict(sorted(q_dist.items()))}")

        # Save outputs for patch_size=32
        if patch_size == 32:
            Image.fromarray(reconstructed).save(str(OUTPUT_DIR / "cognimap_reconstructed.jpg"), quality=95)
            save_importance_heatmap(imp_map, image.shape, patch_size, OUTPUT_DIR / "importance_heatmap.png")
            with open(str(OUTPUT_DIR / "cognimap_registry.json"), "w") as f:
                json.dump(cognimap, f, indent=2)
            print(f"  Saved: cognimap_reconstructed.jpg, importance_heatmap.png, cognimap_registry.json")

    # ── Experiment 3: Compare to JPEG at same file size ──────────────

    print(f"\n" + "-" * 70)
    print("EXPERIMENT 3: CogniMap vs JPEG at Same File Size")
    print("-" * 70)

    # Get CogniMap size at patch_size=32
    patches_32, cognimap_32, stats_32 = compress_cognimap(image, patch_size=32)
    cognimap_total = stats_32["total_bytes"] + len(json.dumps(cognimap_32))

    # Find JPEG quality that produces similar file size
    best_q = 10
    best_diff = float('inf')
    for q in range(5, 96):
        jpeg_data = compress_uniform(image, q)
        diff = abs(len(jpeg_data) - cognimap_total)
        if diff < best_diff:
            best_diff = diff
            best_q = q

    jpeg_matched = compress_uniform(image, best_q)
    jpeg_dec = decompress_jpeg(jpeg_matched)

    rec_32 = decompress_cognimap(patches_32, cognimap_32, image.shape)

    min_h = min(image.shape[0], jpeg_dec.shape[0], rec_32.shape[0])
    min_w = min(image.shape[1], jpeg_dec.shape[1], rec_32.shape[1])
    min_c = min(image.shape[2] if len(image.shape)>2 else 1,
                jpeg_dec.shape[2] if len(jpeg_dec.shape)>2 else 1,
                rec_32.shape[2] if len(rec_32.shape)>2 else 1)

    o = image[:min_h, :min_w, :min_c] if min_c > 1 else image[:min_h, :min_w]
    j = jpeg_dec[:min_h, :min_w, :min_c] if min_c > 1 else jpeg_dec[:min_h, :min_w]
    c = rec_32[:min_h, :min_w, :min_c] if min_c > 1 else rec_32[:min_h, :min_w]

    jpeg_psnr = psnr(o, j)
    jpeg_ssim = ssim_simple(o, j)
    cogni_psnr = psnr(o, c)
    cogni_ssim = ssim_simple(o, c)

    print(f"  Target size: ~{cognimap_total/1024:.0f} KB")
    print(f"  JPEG Q={best_q:2d}: {len(jpeg_matched)/1024:.0f} KB | PSNR={jpeg_psnr:.1f} dB | SSIM={jpeg_ssim:.4f}")
    print(f"  CogniMap:    {cognimap_total/1024:.0f} KB | PSNR={cogni_psnr:.1f} dB | SSIM={cogni_ssim:.4f}")

    if cogni_psnr > jpeg_psnr:
        print(f"\n  >> CogniMap wins by +{cogni_psnr - jpeg_psnr:.1f} dB PSNR at same size")
    else:
        print(f"\n  >> JPEG wins by +{jpeg_psnr - cogni_psnr:.1f} dB PSNR at same size")

    if cogni_ssim > jpeg_ssim:
        print(f"  >> CogniMap wins by +{(cogni_ssim - jpeg_ssim):.4f} SSIM")
    else:
        print(f"  >> JPEG wins by +{(jpeg_ssim - cogni_ssim):.4f} SSIM")

    # ── Summary ──────────────────────────────────────────────────────

    print(f"\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Original image: {image.nbytes/1024:.0f} KB raw, {original_file_size/1024:.0f} KB JPEG")
    print(f"  CogniMap (32px): {cognimap_total/1024:.0f} KB ({image.nbytes/cognimap_total:.1f}x vs raw)")
    print(f"  vs JPEG at same size: {'CogniMap' if cogni_psnr > jpeg_psnr else 'JPEG'} has better PSNR")
    print(f"  vs JPEG at same size: {'CogniMap' if cogni_ssim > jpeg_ssim else 'JPEG'} has better SSIM")
    print(f"\n  Key insight: CogniMap allocates quality non-uniformly.")
    print(f"  Important regions (edges, detail) get Q=95.")
    print(f"  Unimportant regions (flat, uniform) get Q=10.")
    print(f"  At the same total file size, this should preserve")
    print(f"  perceptual quality better than uniform JPEG.")
    print(f"\n  Output files in: {OUTPUT_DIR}")


if __name__ == "__main__":
    run_experiment()
