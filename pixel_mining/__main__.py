"""
CLI entry point: python -m pixel_mining

Mines a square image pixel by pixel using SHA-256 proof-of-work,
saves the result as a PNG, and optionally writes a JSON verification file.
"""

import argparse
import json
import os
import sys
import time

import numpy as np
from PIL import Image

from .core import derive_seed, hash_to_rgb, mine_pixel
from .geometry import get_neighbors, in_circle, pixel_tolerance


def main():
    parser = argparse.ArgumentParser(
        description="Mine a pixel art image using SHA-256 proof-of-work."
    )
    parser.add_argument(
        "--width",
        type=int,
        default=32,
        help="Canvas width in pixels (default: 32)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=None,
        help="Canvas height in pixels (default: same as width)",
    )
    parser.add_argument(
        "--timestamp",
        type=int,
        default=None,
        help="Seed timestamp in milliseconds (default: current time)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directory for output files (default: output/)",
    )
    parser.add_argument(
        "--save-nonces",
        action="store_true",
        help="Write a JSON file with every pixel's nonce for verification",
    )
    parser.add_argument(
        "--bg-tolerance",
        type=int,
        default=5,
        help="Background neighbor tolerance (default: 5, production value). "
        "Higher values mine faster with less color constraint. "
        "Try 15 for a quick demo.",
    )
    parser.add_argument(
        "--circle-tolerance",
        type=int,
        default=13,
        help="Circle region neighbor tolerance (default: 13, production value)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-pixel progress output",
    )
    args = parser.parse_args()

    width = args.width
    height = args.height if args.height else width
    timestamp_ms = args.timestamp if args.timestamp else int(time.time() * 1000)
    total_pixels = width * height
    bg_tol = args.bg_tolerance
    circle_tol = args.circle_tolerance

    seed = derive_seed(timestamp_ms)
    seed_hash = seed["seed_hash"]
    modulo_shift = seed["modulo_shift"]

    print(f"Pixel Mining", flush=True)
    print(f"  Canvas: {width} x {height} ({total_pixels:,} pixels)")
    print(f"  Seed timestamp: {timestamp_ms}")
    print(f"  Seed hash: {seed_hash[:16]}...")
    print(f"  Tolerance: background={bg_tol}, circle={circle_tol}")
    print(flush=True)

    pixels = np.zeros((width, height, 3), dtype=np.uint8)
    previous_hashes = {}
    nonce_log = {}

    # Mine the seed pixel at (0, 0)
    seed_nonce = 0
    seed_rgb, _ = hash_to_rgb(seed_hash, seed_nonce, modulo_shift)
    pixels[0, 0] = seed_rgb
    previous_hashes[(0, 0)] = seed_hash
    nonce_log["0,0"] = seed_nonce

    if not args.quiet:
        print(f"  (0, 0) seed  RGB{seed_rgb}  nonce={seed_nonce}", flush=True)

    start_time = time.time()
    pixels_done = 1

    for row in range(height):
        for col in range(width):
            if row == 0 and col == 0:
                continue

            left_rgb, top_rgb, top_right_rgb = get_neighbors(
                col, row, width, height, pixels, previous_hashes, timestamp_ms
            )

            if in_circle(col, row, width, height):
                tolerance = circle_tol
            else:
                tolerance = bg_tol

            if col > 0:
                prev_hash = previous_hashes[(col - 1, row)]
            elif row > 0:
                prev_hash = previous_hashes[(0, row - 1)]
            else:
                prev_hash = previous_hashes[(0, 0)]

            new_hash, rgb, nonce = mine_pixel(
                prev_hash, left_rgb, top_rgb, tolerance, modulo_shift, top_right_rgb
            )

            pixels[col, row] = rgb
            previous_hashes[(col, row)] = new_hash
            nonce_log[f"{col},{row}"] = nonce
            pixels_done += 1

            if not args.quiet and pixels_done % max(1, total_pixels // 20) == 0:
                elapsed = time.time() - start_time
                rate = pixels_done / elapsed if elapsed > 0 else 0
                pct = pixels_done / total_pixels * 100
                print(
                    f"  progress: {pixels_done}/{total_pixels}"
                    f" ({pct:.0f}%)  {rate:.1f} px/s",
                    flush=True,
                )

    elapsed = time.time() - start_time

    os.makedirs(args.output_dir, exist_ok=True)

    # Save PNG (pixels array is column-major [x, y], PIL expects row-major [y, x])
    img_array = np.swapaxes(pixels, 0, 1)
    img = Image.fromarray(img_array, "RGB")
    png_path = os.path.join(args.output_dir, f"mined_{timestamp_ms}_{width}x{height}.png")
    img.save(png_path)

    print(flush=True)
    print(f"Done. {total_pixels:,} pixels mined in {elapsed:.1f}s ({total_pixels / elapsed:.1f} px/s)")
    print(f"  Image: {png_path}", flush=True)

    if args.save_nonces:
        verification = {
            "timestamp_ms": timestamp_ms,
            "width": width,
            "height": height,
            "seed_hash": seed_hash,
            "modulo_shift": modulo_shift,
            "nonces": nonce_log,
        }
        json_path = os.path.join(
            args.output_dir, f"nonces_{timestamp_ms}_{width}x{height}.json"
        )
        with open(json_path, "w") as f:
            json.dump(verification, f, indent=2)
        print(f"  Nonces: {json_path}")


if __name__ == "__main__":
    main()
