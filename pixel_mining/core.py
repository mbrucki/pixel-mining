"""
Core proof-of-work primitives for pixel mining.

Necessary technique:
  - Hash any seed material to start a chain
  - Link pixels: next_hash = SHA-256(prev_hash || nonce)
  - Derive RGB from the digest, limited to 0..255
  - Search nonces until an acceptance rule passes

The neighbor-tolerance helpers below are one example rule used by this
repo's demo. They are not the definition of pixel mining.
"""

import hashlib

# Fixed 8-bit channel bound. Variable / nonce-derived moduli are optional
# color-calibration choices; they are not required by the technique.
RGB_MODULUS = 256


def derive_seed(seed_material: str | bytes) -> str:
    """Return the chain's starting hash from arbitrary seed material.

    The seed can be anything hashable: text, a timestamp string, image
    bytes, audio bytes, weather data, etc. This function only requires
    that the material be provided as str or bytes.
    """
    if isinstance(seed_material, str):
        seed_material = seed_material.encode()
    return hashlib.sha256(seed_material).hexdigest()


def hash_to_rgb(hex_digest: str) -> tuple[int, int, int]:
    """Map a SHA-256 hex digest to an RGB triple in 0..255.

    This example folds hex pairs at stride-3 offsets, then mods by 256.
    Other mappings are valid as long as each channel stays in 0..255.
    """
    r = sum(int(hex_digest[i : i + 2], 16) for i in range(0, 64, 3)) % RGB_MODULUS
    g = sum(int(hex_digest[i : i + 2], 16) for i in range(1, 64, 3)) % RGB_MODULUS
    b = sum(int(hex_digest[i : i + 2], 16) for i in range(2, 64, 3)) % RGB_MODULUS
    return r, g, b


def next_hash(prev_hash_hex: str, nonce: int) -> str:
    """Next chain link: SHA-256(prev_hash || str(nonce))."""
    return hashlib.sha256((prev_hash_hex + str(nonce)).encode()).hexdigest()


def check_tolerance(
    new_rgb: tuple,
    left_rgb: tuple,
    top_rgb: tuple,
    base_tolerance: int,
    top_right_rgb: tuple | None = None,
) -> bool:
    """Example acceptance rule: stay close to left and top neighbors.

    This is a teaching demo constraint, not a required shape for pixel
    mining. Another piece could use a different predicate entirely.

    For each channel, this example sets
    eff_tol = max(base_tol, ceil(|left - top| / 2))
    and requires the candidate within eff_tol of both neighbors.
    If top_right_rgb is set, the candidate must differ in at least one
    channel (another optional anti-flatness choice).
    """
    for ch in range(3):
        gap = abs(left_rgb[ch] - top_rgb[ch])
        eff_tol = max(base_tolerance, (gap + 1) // 2)
        if abs(new_rgb[ch] - left_rgb[ch]) > eff_tol:
            return False
        if abs(new_rgb[ch] - top_rgb[ch]) > eff_tol:
            return False

    if top_right_rgb is not None and new_rgb == top_right_rgb:
        return False

    return True


# Practical deadlock avoidance for this example's constraint set.
ESCAPE_BUDGET = 256**3
ESCAPE_BUMP = 3

_PROB_SKIP_THRESHOLD = 1e-6


def mine_pixel(
    prev_hash_hex: str,
    left_rgb: tuple,
    top_rgb: tuple,
    base_tolerance: int,
    top_right_rgb: tuple | None = None,
) -> tuple[str, tuple[int, int, int], int]:
    """Search nonces until the example neighbor rule accepts a color.

    Returns (new_hash_hex, rgb, nonce).
    """
    cumulative_bump = 0
    nonce = 0

    while True:
        effective_tolerance = base_tolerance + cumulative_bump

        # Cheap reject: if the acceptance band is empty under RGB_MODULUS,
        # skip the full hash. Same idea works for other constraint shapes.
        prob = 1.0
        for ch in range(3):
            gap = abs(left_rgb[ch] - top_rgb[ch])
            eff_tol = max(effective_tolerance, (gap + 1) // 2)
            lo = max(min(left_rgb[ch], top_rgb[ch]) - eff_tol, 0)
            hi = min(max(left_rgb[ch], top_rgb[ch]) + eff_tol, RGB_MODULUS - 1)
            count = max(0, hi - lo + 1)
            prob *= count / RGB_MODULUS

        if prob <= _PROB_SKIP_THRESHOLD:
            nonce += 1
            if nonce > 0 and nonce % ESCAPE_BUDGET == 0:
                cumulative_bump += ESCAPE_BUMP
                nonce = 0
            continue

        new_hash = next_hash(prev_hash_hex, nonce)
        rgb = hash_to_rgb(new_hash)

        if check_tolerance(rgb, left_rgb, top_rgb, effective_tolerance, top_right_rgb):
            return new_hash, rgb, nonce

        nonce += 1

        if nonce > 0 and nonce % ESCAPE_BUDGET == 0:
            cumulative_bump += ESCAPE_BUMP
            nonce = 0
