"""
CLI entry point: python -m pixel_mining

Mines a square image with the example rules in this repo (left/top neighbor
tolerance, optional central circle), saves a PNG, and optionally writes a
JSON nonce log for chain replay.
"""

import argparse
import json
import os
import time

import numpy as np
from PIL import Image

from .core import derive_seed, hash_to_rgb, mine_pixel
from .geometry import get_neighbors, in_circle


def main():
    parser = argparse.ArgumentParser(
        description="Mine a pixel image using SHA-256 proof-of-work (teaching demo)."
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
        "--seed",
        type=str,
        default=None,
        help="Arbitrary seed material (any string). Hashed to start the chain.",
    )
    parser.add_argument(
        "--timestamp",
        type=int,
        default=None,
        help="Convenience: use this millisecond timestamp string as the seed. "
        "Ignored if --seed is set.",
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
        help="Example background neighbor tolerance (default: 5). "
        "Higher values mine faster. Try 15 for a quick demo.",
    )
    parser.add_argument(
        "--circle-tolerance",
        type=int,
        default=13,
        help="Example circle-region neighbor tolerance (default: 13)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-pixel progress output",
    )
    args = parser.parse_args()

    width = args.width
    height = args.height if args.height else width

    if args.seed is not None:
        seed_material = args.seed
    elif args.timestamp is not None:
        seed_material = str(args.timestamp)
    else:
        seed_material = str(int(time.time() * 1000))

    total_pixels = width * height
    bg_tol = args.bg_tolerance
    circle_tol = args.circle_tolerance

    seed_hash = derive_seed(seed_material)

    print("Pixel Mining", flush=True)
    print(f"  Canvas: {width} x {height} ({total_pixels:,} pixels)")
    print(f"  Seed material: {seed_material!r}")
    print(f"  Seed hash: {seed_hash[:16]}...")
    print(f"  Example tolerances: background={bg_tol}, circle={circle_tol}")
    print(flush=True)

    pixels = np.zeros((width, height, 3), dtype=np.uint8)
    previous_hashes = {}
    nonce_log = {}

    # First pixel: color from the seed hash (nonce recorded as 0 for the log).
    seed_nonce = 0
    seed_rgb = hash_to_rgb(seed_hash)
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
                col, row, width, height, pixels
            )

            tolerance = (
                circle_tol if in_circle(col, row, width, height) else bg_tol
            )

            if col > 0:
                prev_hash = previous_hashes[(col - 1, row)]
            elif row > 0:
                prev_hash = previous_hashes[(0, row - 1)]
            else:
                prev_hash = previous_hashes[(0, 0)]

            new_hash, rgb, nonce = mine_pixel(
                prev_hash, left_rgb, top_rgb, tolerance, top_right_rgb
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

    img_array = np.swapaxes(pixels, 0, 1)
    img = Image.fromarray(img_array, "RGB")
    safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in seed_material)[
        :48
    ]
    png_path = os.path.join(
        args.output_dir, f"mined_{safe_label}_{width}x{height}.png"
    )
    img.save(png_path)

    print(flush=True)
    print(
        f"Done. {total_pixels:,} pixels mined in {elapsed:.1f}s "
        f"({total_pixels / elapsed:.1f} px/s)"
    )
    print(f"  Image: {png_path}", flush=True)

    if args.save_nonces:
        verification = {
            "seed_material": seed_material,
            "seed_hash": seed_hash,
            "width": width,
            "height": height,
            "bg_tolerance": bg_tol,
            "circle_tolerance": circle_tol,
            "nonces": nonce_log,
        }
        json_path = os.path.join(
            args.output_dir, f"nonces_{safe_label}_{width}x{height}.json"
        )
        with open(json_path, "w") as f:
            json.dump(verification, f, indent=2)
        print(f"  Nonces: {json_path}")


if __name__ == "__main__":
    main()
