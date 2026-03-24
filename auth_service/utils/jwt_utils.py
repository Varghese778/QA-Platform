"""JWT utilities for token creation and validation."""

import base64
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt

from auth_service.config import get_settings

settings = get_settings()

# In-memory key storage (for MVP; in production, load from HSM/Secret Manager)
_private_key: Optional[rsa.RSAPrivateKey] = None
_public_key: Optional[rsa.RSAPublicKey] = None
_key_id: str = "key-1"


def _ensure_keys() -> Tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    """Ensure RSA keys are loaded/generated."""
    global _private_key, _public_key

    if _private_key is None or _public_key is None:
        if settings.jwt_private_key_path and settings.jwt_public_key_path:
            # Load from files
            with open(settings.jwt_private_key_path, "rb") as f:
                _private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                )
            with open(settings.jwt_public_key_path, "rb") as f:
                _public_key = serialization.load_pem_public_key(f.read())
        else:
            # Generate ephemeral keys for development
            _private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            _public_key = _private_key.public_key()

    return _private_key, _public_key


def get_private_key() -> rsa.RSAPrivateKey:
    """Get the RSA private key for signing."""
    private_key, _ = _ensure_keys()
    return private_key


def get_public_key() -> rsa.RSAPublicKey:
    """Get the RSA public key for verification."""
    _, public_key = _ensure_keys()
    return public_key


def get_key_id() -> str:
    """Get the current key ID."""
    return _key_id


def create_access_token(
    user_id: uuid.UUID,
    email: str,
    name: str,
    roles: Dict[str, str],
    token_id: Optional[str] = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: User's UUID.
        email: User's email.
        name: User's display name.
        roles: Map of project_id to role.
        token_id: Optional token ID (generated if not provided).

    Returns:
        Signed JWT as a string.
    """
    now = datetime.now(timezone.utc)
    jti = token_id or str(uuid.uuid4())

    payload = {
        "sub": str(user_id),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + settings.jwt_access_token_ttl_seconds,
        "email": email,
        "name": name,
        "roles": roles,
        "jti": jti,
    }

    private_key = get_private_key()
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    token = jwt.encode(
        payload,
        private_key_pem,
        algorithm=settings.jwt_algorithm,
        headers={"kid": _key_id},
    )

    return token


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT access token.

    Args:
        token: JWT string.

    Returns:
        Decoded payload as a dict.

    Raises:
        jwt.InvalidTokenError: If token is invalid.
    """
    public_key = get_public_key()
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    payload = jwt.decode(
        token,
        public_key_pem,
        algorithms=[settings.jwt_algorithm],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        leeway=settings.jwt_clock_skew_seconds,
    )

    return payload


def get_jwks() -> Dict[str, Any]:
    """
    Get the JWKS (JSON Web Key Set) for public key distribution.

    Returns:
        JWKS dict with public keys.
    """
    public_key = get_public_key()
    public_numbers = public_key.public_numbers()

    # Convert to base64url encoding
    def int_to_base64url(n: int, length: int) -> str:
        data = n.to_bytes(length, byteorder="big")
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    # Calculate byte length for modulus (2048 bits = 256 bytes)
    n_bytes = (public_numbers.n.bit_length() + 7) // 8

    jwk = {
        "kty": "RSA",
        "use": "sig",
        "kid": _key_id,
        "alg": settings.jwt_algorithm,
        "n": int_to_base64url(public_numbers.n, n_bytes),
        "e": int_to_base64url(public_numbers.e, 3),
    }

    return {"keys": [jwk]}
