"""
pixel_mining — educational extract of SHA-256 pixel mining.

Core technique: hash a seed, chain pixels with nonces, derive RGB from
hashes (0..255), accept only nonces that pass some constraint.

This package's runnable demo uses one simple constraint set (left/top
neighbors, optional circle). See README.md.
"""

__version__ = "0.1.0"
