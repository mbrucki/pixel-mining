"""
Example composition helpers: a central circle and neighbor picks.

Nothing here is required by the pixel-mining technique. This module only
supports the demo in this repository (circle in the middle, left/top
neighbors, optional circle isolation).
"""

import math

# Example numeric taste for this demo's neighbor rule.
BACKGROUND_TOLERANCE = 5
CIRCLE_TOLERANCE = 13


def circle_center(width: int, height: int) -> tuple[int, int]:
    return width // 2, height // 2


def circle_radius(width: int) -> int:
    return width // 4


def in_circle(col: int, row: int, width: int, height: int) -> bool:
    """Example shape: disk centered on the canvas with radius width/4."""
    cx, cy = circle_center(width, height)
    r = circle_radius(width)
    dx = col - cx
    dy = row - cy
    return math.sqrt(dx * dx + dy * dy) <= r


def pixel_tolerance(col: int, row: int, width: int, height: int) -> int:
    if in_circle(col, row, width, height):
        return CIRCLE_TOLERANCE
    return BACKGROUND_TOLERANCE


def _to_int_tuple(arr) -> tuple[int, int, int]:
    return (int(arr[0]), int(arr[1]), int(arr[2]))


def get_neighbors(
    col: int,
    row: int,
    width: int,
    height: int,
    pixels,
) -> tuple:
    """Example neighbor picks for the demo acceptance rule.

    Uses the immediate left and top pixels when they exist. On the first
    column / first row, falls back to the other available neighbor or the
    seed pixel. If the current pixel is outside the circle, skips circle
    pixels when choosing those neighbors (circle isolation: an optional
    composition effect used in this example).

    Returns (left_rgb, top_rgb, top_right_rgb_or_None).
    """
    pixel_in_circle = in_circle(col, row, width, height)

    if col > 0:
        left_rgb = _to_int_tuple(pixels[col - 1, row])
        if not pixel_in_circle and in_circle(col - 1, row, width, height):
            left_rgb = _find_non_circle_left(col, row, width, height, pixels)
    elif row > 0:
        left_rgb = _to_int_tuple(pixels[col, row - 1])
        if not pixel_in_circle and in_circle(col, row - 1, width, height):
            left_rgb = _find_non_circle_top(col, row, width, height, pixels)
    else:
        left_rgb = _to_int_tuple(pixels[0, 0])

    if row > 0:
        top_rgb = _to_int_tuple(pixels[col, row - 1])
        if not pixel_in_circle and in_circle(col, row - 1, width, height):
            top_rgb = _find_non_circle_top(col, row, width, height, pixels)
    else:
        top_rgb = left_rgb

    top_right_rgb = None
    if row > 0 and col < width - 1:
        if pixel_in_circle or not in_circle(col + 1, row - 1, width, height):
            top_right_rgb = _to_int_tuple(pixels[col + 1, row - 1])

    return left_rgb, top_rgb, top_right_rgb


def _find_non_circle_left(col, row, width, height, pixels):
    for search_col in range(col - 2, -1, -1):
        if not in_circle(search_col, row, width, height):
            return _to_int_tuple(pixels[search_col, row])
    return _to_int_tuple(pixels[0, 0])


def _find_non_circle_top(col, row, width, height, pixels):
    for search_row in range(row - 2, -1, -1):
        if not in_circle(col, search_row, width, height):
            return _to_int_tuple(pixels[col, search_row])
    return _to_int_tuple(pixels[0, 0])
