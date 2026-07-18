"""
pixel_mining — educational extract of the SHA-256 pixel mining technique.

Each pixel in the image is found by proof-of-work: a nonce search over SHA-256
hashes until the resulting color satisfies neighbor-tolerance constraints.
All pixels are linked in a cryptographic hash chain.

See README.md for the full explanation.
"""

__version__ = "0.1.0"
