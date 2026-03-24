"""Security utilities for hashing and token generation."""

import hashlib
import secrets
from typing import Tuple


def generate_api_key(length: int = 64) -> Tuple[str, str]:
    """
    Generate a new API key.

    Args:
        length: Length of the hex string (default 64 characters = 32 bytes).

    Returns:
        Tuple of (raw_key, key_hash).
    """
    raw_key = secrets.token_hex(length // 2)
    key_hash = hash_token(raw_key)
    return raw_key, key_hash


def generate_refresh_token() -> Tuple[str, str]:
    """
    Generate a new opaque refresh token.

    Returns:
        Tuple of (raw_token, token_hash).
    """
    raw_token = secrets.token_urlsafe(48)
    token_hash = hash_token(raw_token)
    return raw_token, token_hash


def hash_token(token: str) -> str:
    """
    Hash a token using SHA-256.

    Args:
        token: Raw token value.

    Returns:
        Hex-encoded SHA-256 hash.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token_hash(raw_token: str, stored_hash: str) -> bool:
    """
    Verify a token against its stored hash.

    Args:
        raw_token: Raw token value to verify.
        stored_hash: Stored SHA-256 hash.

    Returns:
        True if the token matches the hash.
    """
    return secrets.compare_digest(hash_token(raw_token), stored_hash)
