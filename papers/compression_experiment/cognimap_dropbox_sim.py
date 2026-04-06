"""CogniMap Dropbox Simulation

Simulates the full product flow:
  1. User uploads images
  2. System compresses each with CogniMap (lossless)
  3. Original is "deleted" (we verify we DON'T need it)
  4. User requests file back
  5. System decompresses from compressed representation
  6. Verify: SHA256 matches original exactly

Also reports: total storage savings, per-file compression ratios,
and comparison to what standard cloud storage would cost.

Run: .venv/Scripts/python papers/compression_experiment/cognimap_dropbox_sim.py
"""

import sys
import os
import zlib
import hashlib
import time
import struct
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
OUTPUT_DIR = SCRIPT_DIR / "output" / "dropbox_sim"
COMPRESSED_DIR = OUTPUT_DIR / "compressed"
RESTORED_DIR = OUTPUT_DIR / "restored"


# ── Causal Prediction Engine (from lossless v0) ──────────────────────

def classify_regions(gray: np.ndarray, block_size: int = 8) -> np.ndarray:
    h, w = gray.shape
    bh = (h + block_size - 1) // block_size
    bw = (w + block_size - 1) // block_size
    region_map = np.zeros((bh, bw), dtype=np.uint8)

    for by in range(bh):
        for bx in range(bw):
            y0, x0 = by * block_size, bx * block_size
            y1, x1 = min(y0 + block_size, h), min(x0 + block_size, w)
            block = gray[y0:y1, x0:x1]
            if block.size < 4:
                region_map[by, bx] = 4
                continue

            variance = np.var(block)
            if block.shape[0] > 1 and block.shape[1] > 1:
                gy = np.mean(np.abs(np.diff(block, axis=0)))
                gx = np.mean(np.abs(np.diff(block, axis=1)))
                gyy = np.mean(np.abs(np.diff(block, axis=0, n=2))) if block.shape[0] > 2 else 0
                gxx = np.mean(np.abs(np.diff(block, axis=1, n=2))) if block.shape[1] > 2 else 0
            else:
                gy = gx = gyy = gxx = 0

            if variance < 10:
                region_map[by, bx] = 0
            elif gyy + gxx < 3 and (gy + gx) > 2:
                region_map[by, bx] = 1
            elif variance < 200 and gyy + gxx < 10:
                region_map[by, bx] = 2
            elif gyy + gxx > 15:
                region_map[by, bx] = 3
            else:
                region_map[by, bx] = 4

    return region_map


def compress_lossless(image: np.ndarray, block_size: int = 8) -> bytes:
    """Lossless compression with causal prediction."""
    h, w = image.shape[:2]
    channels = image.shape[2] if len(image.shape) > 2 else 1
    img16 = image.astype(np.int16)

    gray = np.mean(image.astype(np.float32), axis=2) if channels > 1 else image.astype(np.float32)
    region_map = classify_regions(gray, block_size)

    bh = (h + block_size - 1) // block_size
    bw = (w + block_size - 1) // block_size

    # Causal prediction
    predicted = np.zeros_like(img16)
    for y in range(h):
        for x in range(w):
            by = min(y // block_size, bh - 1)
            bx = min(x // block_size, bw - 1)
            rt = int(region_map[by, bx])

            if y == 0 and x == 0:
                predicted[y, x] = 128
            elif y == 0:
                predicted[y, x] = img16[y, x - 1]
            elif x == 0:
                predicted[y, x] = img16[y - 1, x]
            else:
                left = img16[y, x - 1]
                top = img16[y - 1, x]
                top_left = img16[y - 1, x - 1]

                if rt == 0:  # flat
                    predicted[y, x] = (left + top) // 2
                elif rt == 1:  # gradient (Paeth)
                    p = left + top - top_left
                    if channels > 1:
                        pred = np.zeros(channels, dtype=np.int16)
                        for c in range(channels):
                            pa = abs(int(p[c]) - int(left[c]))
                            pb = abs(int(p[c]) - int(top[c]))
                            pc = abs(int(p[c]) - int(top_left[c]))
                            if pa <= pb and pa <= pc: pred[c] = left[c]
                            elif pb <= pc: pred[c] = top[c]
                            else: pred[c] = top_left[c]
                        predicted[y, x] = pred
                    else:
                        pa = abs(int(p) - int(left))
                        pb = abs(int(p) - int(top))
                        pc = abs(int(p) - int(top_left))
                        if pa <= pb and pa <= pc: predicted[y, x] = left
                        elif pb <= pc: predicted[y, x] = top
                        else: predicted[y, x] = top_left
                elif rt == 3:  # edge
                    h_d = np.abs(left - top_left).sum() if channels > 1 else abs(int(left) - int(top_left))
                    v_d = np.abs(top - top_left).sum() if channels > 1 else abs(int(top) - int(top_left))
                    predicted[y, x] = top if h_d < v_d else left
                else:  # texture, complex
                    predicted[y, x] = (left + top) // 2

    residual = img16 - predicted
    residual_bytes = residual.astype(np.int16).tobytes()
    region_bytes = region_map.tobytes()

    compressed_residual = zlib.compress(residual_bytes, 9)
    compressed_region = zlib.compress(region_bytes, 9)

    # Header: h, w, channels, block_size, mode(RGB/grayscale), original format marker
    header = struct.pack('IIIII', h, w, channels, block_size, 0)
    packed = header + struct.pack('II', len(compressed_region), len(compressed_residual))
    packed += compressed_region + compressed_residual

    return packed


def decompress_lossless(compressed: bytes) -> np.ndarray:
    """Decompress to exact original."""
    offset = 0
    h, w, channels, block_size, _ = struct.unpack_from('IIIII', compressed, offset); offset += 20
    region_len, residual_len = struct.unpack_from('II', compressed, offset); offset += 8

    region_data = zlib.decompress(compressed[offset:offset + region_len]); offset += region_len
    residual_data = zlib.decompress(compressed[offset:offset + residual_len])

    bh = (h + block_size - 1) // block_size
    bw = (w + block_size - 1) // block_size
    region_map = np.frombuffer(region_data, dtype=np.uint8).reshape(bh, bw)

    shape = (h, w, channels) if channels > 1 else (h, w)
    residual = np.frombuffer(residual_data, dtype=np.int16).reshape(shape)

    img16 = np.zeros(shape, dtype=np.int16)
    for y in range(h):
        for x in range(w):
            by = min(y // block_size, bh - 1)
            bx = min(x // block_size, bw - 1)
            rt = int(region_map[by, bx])

            if y == 0 and x == 0:
                pred = np.int16(128)
            elif y == 0:
                pred = img16[y, x - 1]
            elif x == 0:
                pred = img16[y - 1, x]
            else:
                left = img16[y, x - 1]
                top = img16[y - 1, x]
                top_left = img16[y - 1, x - 1]

                if rt == 0:
                    pred = (left + top) // 2
                elif rt == 1:
                    p = left + top - top_left
                    if channels > 1:
                        pred = np.zeros(channels, dtype=np.int16)
                        for c in range(channels):
                            pa = abs(int(p[c]) - int(left[c]))
                            pb = abs(int(p[c]) - int(top[c]))
                            pc = abs(int(p[c]) - int(top_left[c]))
                            if pa <= pb and pa <= pc: pred[c] = left[c]
                            elif pb <= pc: pred[c] = top[c]
                            else: pred[c] = top_left[c]
                    else:
                        pa = abs(int(p) - int(left))
                        pb = abs(int(p) - int(top))
                        pc = abs(int(p) - int(top_left))
                        if pa <= pb and pa <= pc: pred = left
                        elif pb <= pc: pred = top
                        else: pred = top_left
                elif rt == 3:
                    h_d = np.abs(left - top_left).sum() if channels > 1 else abs(int(left) - int(top_left))
                    v_d = np.abs(top - top_left).sum() if channels > 1 else abs(int(top) - int(top_left))
                    pred = top if h_d < v_d else left
                else:
                    pred = (left + top) // 2

            img16[y, x] = pred + residual[y, x]

    return np.clip(img16, 0, 255).astype(np.uint8)


# ── Main Simulation ───────────────────────────────────────────────────

def run_simulation():
    print("=" * 70)
    print("CogniMap Dropbox Simulation")
    print("=" * 70)
    print("\nSimulating: upload -> compress -> delete original -> restore -> verify")

    # Clean output dirs
    for d in [COMPRESSED_DIR, RESTORED_DIR]:
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    # Collect test images
    image_paths = []
    for pattern in ["*.jpg", "*.jpeg", "*.png"]:
        image_paths.extend(REPO_ROOT.glob(pattern))
    image_paths.extend((SCRIPT_DIR / "test_image.jpg").parent.glob("test_image.*"))
    for f in (REPO_ROOT / "workspace" / "uploads").glob("*"):
        if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
            image_paths.append(f)

    # Deduplicate
    image_paths = list(set(image_paths))
    # Filter out output dir images
    image_paths = [p for p in image_paths if "output" not in str(p)]
    image_paths = sorted(image_paths)

    if not image_paths:
        print("No test images found!")
        return

    print(f"\nFound {len(image_paths)} images to process\n")

    results = []
    total_original = 0
    total_compressed = 0
    total_png = 0
    all_verified = True

    print(f"  {'File':40s} {'Original':>9s} {'Compressed':>11s} {'Ratio':>6s} {'Verified':>9s} {'Time':>6s}")
    print(f"  {'-'*40} {'-'*9} {'-'*11} {'-'*6} {'-'*9} {'-'*6}")

    for img_path in image_paths:
        try:
            # Step 1: Load original
            img = Image.open(str(img_path))
            image = np.array(img)
            original_hash = hashlib.sha256(image.tobytes()).hexdigest()
            original_size = image.nbytes
            file_size = img_path.stat().st_size

            # PNG baseline
            buf = bytearray()
            bio = __import__('io').BytesIO()
            Image.fromarray(image).save(bio, format="PNG", optimize=True)
            png_size = bio.tell()

            # Step 2: Compress with CogniMap
            t0 = time.time()
            compressed = compress_lossless(image)
            compress_time = time.time() - t0

            # Step 3: Save compressed representation
            comp_name = img_path.stem + ".cogni"
            comp_path = COMPRESSED_DIR / comp_name
            comp_path.write_bytes(compressed)

            # Step 4: "Delete original" (we don't actually delete, but we verify
            # we can reconstruct without it)

            # Step 5: Decompress from compressed representation
            t0 = time.time()
            restored = decompress_lossless(compressed)
            decompress_time = time.time() - t0

            # Step 6: Save restored image
            restored_path = RESTORED_DIR / (img_path.stem + "_restored" + img_path.suffix)
            Image.fromarray(restored).save(str(restored_path))

            # Step 7: Verify
            restored_hash = hashlib.sha256(restored.tobytes()).hexdigest()
            is_identical = original_hash == restored_hash
            max_diff = np.max(np.abs(image.astype(np.int16) - restored.astype(np.int16)))

            if not is_identical:
                all_verified = False

            ratio = original_size / len(compressed)
            total_original += original_size
            total_compressed += len(compressed)
            total_png += png_size

            name = img_path.name[:40]
            verify_str = "PASS" if is_identical else f"FAIL(d={max_diff})"
            total_time = compress_time + decompress_time

            print(f"  {name:40s} {original_size/1024:8.0f}K {len(compressed)/1024:10.0f}K {ratio:5.1f}x {verify_str:>9s} {total_time:5.1f}s")

            results.append({
                "file": img_path.name,
                "original_bytes": original_size,
                "compressed_bytes": len(compressed),
                "png_bytes": png_size,
                "ratio": ratio,
                "verified": is_identical,
                "compress_time": compress_time,
                "decompress_time": decompress_time,
                "dimensions": list(image.shape),
            })

        except Exception as e:
            print(f"  {img_path.name:40s} ERROR: {e}")

    # ── Summary ──────────────────────────────────────────────────────

    print(f"\n" + "=" * 70)
    print("DROPBOX SIMULATION RESULTS")
    print("=" * 70)

    print(f"\n  Files processed:    {len(results)}")
    print(f"  All verified:       {'YES - every file bit-identical' if all_verified else 'NO - some files differ'}")
    print(f"\n  Storage:")
    print(f"    Original (raw):   {total_original/1024:.0f} KB")
    print(f"    PNG (lossless):   {total_png/1024:.0f} KB ({total_original/total_png:.1f}x)")
    print(f"    CogniMap:         {total_compressed/1024:.0f} KB ({total_original/total_compressed:.1f}x)")

    vs_png = (1 - total_compressed / total_png) * 100

    print(f"\n  CogniMap vs PNG:    {'BETTER' if vs_png > 0 else 'WORSE'} by {abs(vs_png):.1f}%")

    # Cost analysis (at $0.023/GB/month — S3 standard)
    gb_original = total_original / (1024 ** 3)
    gb_compressed = total_compressed / (1024 ** 3)
    monthly_savings = (gb_original - gb_compressed) * 0.023

    print(f"\n  Cloud storage cost (at S3 $0.023/GB/month):")
    print(f"    Original:  ${gb_original * 0.023:.6f}/month")
    print(f"    CogniMap:  ${gb_compressed * 0.023:.6f}/month")
    print(f"    Savings:   ${monthly_savings:.6f}/month per {len(results)} files")
    if total_original > 0:
        pct_savings = (1 - total_compressed / total_original) * 100
        print(f"    At 1TB:    ${0.023 * (pct_savings/100):.2f}/month saved")
        print(f"    At 1PB:    ${23.0 * (pct_savings/100):.2f}/month saved")

    print(f"\n  Compressed files: {COMPRESSED_DIR}")
    print(f"  Restored files:   {RESTORED_DIR}")
    print(f"\n  Product promise: 'Upload your files. We compress them.")
    print(f"  When you need the original back, we decompress perfectly.")
    print(f"  Your file comes back bit-identical. SHA256 verified.'")

    # Save manifest
    manifest = {
        "total_files": len(results),
        "all_verified": all_verified,
        "total_original_bytes": total_original,
        "total_compressed_bytes": total_compressed,
        "compression_ratio": total_original / max(total_compressed, 1),
        "files": results,
    }
    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(str(manifest_path), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n  Manifest: {manifest_path}")


if __name__ == "__main__":
    run_simulation()
