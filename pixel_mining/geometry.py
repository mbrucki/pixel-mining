"""
Circle geometry and neighbor isolation for pixel mining.

The v4 algorithm divides the canvas into two regions:
  - A central circle (radius = width / 4, centered on the canvas)
  - The background (everything outside the circle)

The circle uses a looser tolerance (13) than the background (5),
allowing more color variation inside the disk.

The critical structural rule is **circle isolation**: background pixels
must never be influenced by circle pixels when selecting neighbors.
When a background pixel's natural left or top neighbor falls inside the
circle, the algorithm searches further out for the nearest non-circle
pixel instead. This keeps the two regions visually and cryptographically
independent in one direction (background ignores circle), while circle
pixels may reference background neighbors freely.
"""

import hashlib
import math

BACKGROUND_TOLERANCE = 5
CIRCLE_TOLERANCE = 13


def circle_center(width: int, height: int) -> tuple:
    return width // 2, height // 2


def circle_radius(width: int) -> int:
    return width // 4


def in_circle(col: int, row: int, width: int, height: int) -> bool:
    cx, cy = circle_center(width, height)
    r = circle_radius(width)
    dx = col - cx
    dy = row - cy
    return math.sqrt(dx * dx + dy * dy) <= r


def pixel_tolerance(col: int, row: int, width: int, height: int) -> int:
    if in_circle(col, row, width, height):
        return CIRCLE_TOLERANCE
    return BACKGROUND_TOLERANCE


def _to_int_tuple(arr) -> tuple:
    """Convert a numpy pixel (uint8) to a plain Python int tuple."""
    return (int(arr[0]), int(arr[1]), int(arr[2]))


def get_neighbors(
    col: int,
    row: int,
    width: int,
    height: int,
    pixels,
    previous_hashes: dict,
    timestamp_ms: int,
) -> tuple:
    """Select left neighbor, top neighbor, and optional top-right neighbor.

    Handles circle isolation: if the current pixel is in the background
    and a candidate neighbor is inside the circle, the algorithm searches
    for the nearest non-circle substitute.

    Returns (left_rgb, top_rgb, top_right_rgb_or_None).
    """
    pixel_in_circle = in_circle(col, row, width, height)

    # --- Left neighbor ---
    if col > 0:
        left_rgb = _to_int_tuple(pixels[col - 1, row])
        if not pixel_in_circle and in_circle(col - 1, row, width, height):
            left_rgb = _find_non_circle_left(col, row, width, height, pixels)
    elif row > 0:
        left_rgb = _hash_derived_left(
            col, row, width, height, pixels, timestamp_ms, pixel_in_circle
        )
    else:
        left_rgb = _to_int_tuple(pixels[0, 0])

    # --- Top neighbor ---
    if row > 0:
        top_rgb = _hash_derived_top(
            col, row, width, height, pixels, previous_hashes, pixel_in_circle
        )
    else:
        top_rgb = left_rgb

    # --- Top-right neighbor (for the "must differ" check) ---
    top_right_rgb = None
    if row > 0 and col < width - 1:
        if not pixel_in_circle and in_circle(col + 1, row - 1, width, height):
            top_right_rgb = None
        else:
            top_right_rgb = _to_int_tuple(pixels[col + 1, row - 1])

    return left_rgb, top_rgb, top_right_rgb


def _find_non_circle_left(col, row, width, height, pixels):
    """Walk left from (col-2, row) to find the nearest background pixel."""
    for search_col in range(col - 2, -1, -1):
        if not in_circle(search_col, row, width, height):
            return _to_int_tuple(pixels[search_col, row])
    return _to_int_tuple(pixels[0, 0])


def _hash_derived_left(col, row, width, height, pixels, timestamp_ms, pixel_in_circle):
    """For the first column (col=0), pick a pseudo-random column from the row above."""
    row_hash = hashlib.sha256(f"{timestamp_ms}_{row}".encode()).hexdigest()
    row_hash_int = int(row_hash, 16)
    random_col = row_hash_int % width

    if not pixel_in_circle and in_circle(random_col, row - 1, width, height):
        for attempt in range(width):
            candidate = (row_hash_int + attempt) % width
            if not in_circle(candidate, row - 1, width, height):
                random_col = candidate
                break

    return _to_int_tuple(pixels[random_col, row - 1])


def _hash_derived_top(col, row, width, height, pixels, previous_hashes, pixel_in_circle):
    """Select the top neighbor from a hash-derived window in the row above.

    The window is width/3 columns wide, centered on the current column.
    Which column within the window is chosen depends on the previous
    pixel's hash, so the selection is deterministic but non-trivial.
    """
    if col > 0:
        prev_hash_hex = previous_hashes[(col - 1, row)]
    else:
        prev_hash_hex = previous_hashes[(width - 1, row - 1)]

    prev_hash_int = int(prev_hash_hex, 16)

    window_size = width // 3
    if window_size % 2 == 0:
        window_size += 1
    if window_size < 1:
        window_size = 1
    half_window = window_size // 2

    window_start = col - half_window
    window_index = prev_hash_int % window_size
    top_col = max(0, min(width - 1, window_start + window_index))

    if not pixel_in_circle and in_circle(top_col, row - 1, width, height):
        found = False
        for offset in range(window_size):
            test_col = max(0, min(width - 1, window_start + offset))
            if not in_circle(test_col, row - 1, width, height):
                top_col = test_col
                found = True
                break
        if not found:
            for search_col in range(width):
                if not in_circle(search_col, row - 1, width, height):
                    top_col = search_col
                    break

    return _to_int_tuple(pixels[top_col, row - 1])
