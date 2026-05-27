"""OTP helpers — generate a 6-digit code and hash it for safe storage."""

import hashlib
import secrets


def generate_otp() -> str:
    """Return a cryptographically random 6-digit OTP string."""
    return str(secrets.randbelow(900_000) + 100_000)


def hash_otp(plain_otp: str) -> str:
    """Return a SHA-256 hex digest of the OTP.

    SHA-256 is appropriate here because OTPs are short-lived (10 min),
    randomly generated, and verified in constant time — bcrypt's cost
    is unnecessary overhead for a 6-digit value that expires quickly.
    """
    return hashlib.sha256(plain_otp.encode()).hexdigest()


def verify_otp(plain_otp: str, stored_hash: str) -> bool:
    """Return True if plain_otp matches the stored hash."""
    return secrets.compare_digest(hash_otp(plain_otp), stored_hash)
