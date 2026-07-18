"""
Core proof-of-work primitives for pixel mining.

This module contains the fundamental building blocks:
  - Deriving a deterministic seed from a timestamp
  - Extracting RGB color from a SHA-256 hash digest
  - Building the hash chain (each pixel's hash depends on the previous one)
  - The nonce search: finding a valid color within neighbor tolerances
"""

import hashlib


def derive_seed(timestamp_ms: int) -> dict:
    """Derive all session parameters from a millisecond timestamp.

    The timestamp is the only source of randomness. Everything else
    (the initial hash, the nonce parity, the modulo shift) follows
    deterministically from it.

    Returns a dict with:
      seed_hash   - the SHA-256 hex digest that starts the chain
      nonce_start - 0 or 1 (parity derived from timestamp)
      modulo_shift - 0..7 (offset applied to every nonce's modulus)
    """
    ts_hex = hashlib.sha256(str(timestamp_ms).encode()).hexdigest()
    ts_int = int(ts_hex, 16)

    seed_key = f"{timestamp_ms}{ts_hex}"
    seed_hash = hashlib.sha256(seed_key.encode()).hexdigest()

    return {
        "seed_hash": seed_hash,
        "nonce_start": ts_int % 2,
        "modulo_shift": ts_int % 8,
    }


def hash_to_rgb(hex_digest: str, nonce: int, modulo_shift: int) -> tuple:
    """Extract an RGB triplet from a SHA-256 hex digest and a nonce.

    The nonce controls the *modulus* (1..256) that caps each channel.
    Each channel sums hex-digit pairs sampled at stride-3 offsets through
    the 64-character digest, then takes the result modulo the modulus.

    Returns ((r, g, b), modulus).
    """
    nonce_hash = hashlib.sha256(str(nonce).encode()).hexdigest()
    nonce_number = int(nonce_hash, 16)
    modulus = (nonce_number + modulo_shift) % 256 + 1

    r = sum(int(hex_digest[i : i + 2], 16) for i in range(0, 64, 3)) % modulus
    g = sum(int(hex_digest[i : i + 2], 16) for i in range(1, 64, 3)) % modulus
    b = sum(int(hex_digest[i : i + 2], 16) for i in range(2, 64, 3)) % modulus

    return (r, g, b), modulus


def next_hash(prev_hash_hex: str, nonce: int) -> str:
    """Compute the next link in the hash chain.

    chain[n+1] = SHA-256( chain[n] || str(nonce) )

    The chain is what makes pixel mining verifiable: given the seed and
    every nonce, anyone can replay the full sequence and confirm that
    each pixel's color truly came from proof-of-work.
    """
    return hashlib.sha256((prev_hash_hex + str(nonce)).encode()).hexdigest()


def check_tolerance(
    new_rgb: tuple,
    left_rgb: tuple,
    top_rgb: tuple,
    base_tolerance: int,
    top_right_rgb: tuple | None = None,
) -> bool:
    """Check whether a candidate pixel satisfies the neighbor constraints.

    For each color channel independently:
      1. Compute the effective tolerance as the larger of the base tolerance
         and half the gap between the two neighbors (rounded up). This means
         the acceptance band always spans at least the range between neighbors.
      2. The candidate must be within that effective tolerance of *both*
         the left neighbor and the top neighbor.

    If top_right_rgb is given, the candidate must also differ from it in
    at least one channel (prevents uniform patches).
    """
    for ch in range(3):
        gap = abs(left_rgb[ch] - top_rgb[ch])
        eff_tol = max(base_tolerance, (gap + 1) // 2)
        if abs(new_rgb[ch] - left_rgb[ch]) > eff_tol:
            return False
        if abs(new_rgb[ch] - top_rgb[ch]) > eff_tol:
            return False

    if top_right_rgb is not None:
        if new_rgb == top_right_rgb:
            return False

    return True


# After this many nonces without a hit, widen tolerance by ESCAPE_BUMP
# and restart the search. Prevents infinite loops when the base tolerance
# is too tight for the local color constraints.
ESCAPE_BUDGET = 256 ** 3
ESCAPE_BUMP = 3


_PROB_SKIP_THRESHOLD = 1e-6


def mine_pixel(
    prev_hash_hex: str,
    left_rgb: tuple,
    top_rgb: tuple,
    base_tolerance: int,
    modulo_shift: int,
    top_right_rgb: tuple | None = None,
) -> tuple:
    """Search for a nonce that produces a valid pixel color.

    Iterates nonces starting from 0. For each nonce:
      1. Compute the modulus from the nonce
      2. Estimate the probability of a hit (skip if negligible)
      3. Compute the chain hash: SHA-256(prev_hash || str(nonce))
      4. Extract RGB from that hash
      5. Check neighbor tolerance
      6. If all constraints pass, return the result

    If the search exhausts ESCAPE_BUDGET nonces without a hit, the
    tolerance widens by ESCAPE_BUMP and the search restarts. This is
    rare but prevents deadlocks on pathological constraint combinations.

    Returns (new_hash_hex, rgb, nonce).
    """
    cumulative_bump = 0
    nonce = 0

    while True:
        effective_tolerance = base_tolerance + cumulative_bump

        nonce_hash = hashlib.sha256(str(nonce).encode()).hexdigest()
        nonce_number = int(nonce_hash, 16)
        modulus = (nonce_number + modulo_shift) % 256 + 1

        prob = 1.0
        for ch in range(3):
            gap = abs(left_rgb[ch] - top_rgb[ch])
            eff_tol = max(effective_tolerance, (gap + 1) // 2)
            lo = max(min(left_rgb[ch], top_rgb[ch]) - eff_tol, 0)
            hi = min(max(left_rgb[ch], top_rgb[ch]) + eff_tol, modulus - 1)
            count = max(0, hi - lo + 1)
            prob *= count / modulus if modulus > 0 else 0

        if prob <= _PROB_SKIP_THRESHOLD:
            nonce += 1
            if nonce % ESCAPE_BUDGET == 0:
                cumulative_bump += ESCAPE_BUMP
                nonce = 0
            continue

        new_hash = next_hash(prev_hash_hex, nonce)
        rgb, _ = hash_to_rgb(new_hash, nonce, modulo_shift)

        if check_tolerance(rgb, left_rgb, top_rgb, effective_tolerance, top_right_rgb):
            return new_hash, rgb, nonce

        nonce += 1

        if nonce % ESCAPE_BUDGET == 0:
            cumulative_bump += ESCAPE_BUMP
            nonce = 0
