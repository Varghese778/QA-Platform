"""Authentication-related Pydantic schemas."""

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from auth_service.models.enums import GrantType, TokenTypeHint


class TokenRequest(BaseModel):
    """Token endpoint request schema."""

    grant_type: GrantType
    identity_token: Optional[str] = Field(
        None,
        description="IdP-issued OIDC ID token (required for oidc_exchange)",
    )
    refresh_token: Optional[str] = Field(
        None,
        description="Opaque refresh token (required for refresh_token grant)",
    )
    api_key: Optional[str] = Field(
        None,
        description="API key (required for api_key grant)",
    )


class TokenResponse(BaseModel):
    """Token endpoint response schema."""

    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int = Field(description="Token TTL in seconds")
    refresh_token: Optional[str] = Field(
        None,
        description="Refresh token (not returned for api_key grant)",
    )


class RevokeRequest(BaseModel):
    """Token revocation request schema."""

    token: str
    token_type_hint: Optional[TokenTypeHint] = None


class RevokeResponse(BaseModel):
    """Token revocation response schema."""

    revoked: bool = True


class LogoutResponse(BaseModel):
    """Logout response schema."""

    logged_out: bool = True


class JWK(BaseModel):
    """JSON Web Key representation."""

    kty: str = Field(description="Key type (e.g., RSA)")
    use: str = Field(description="Key use (sig for signature)")
    kid: str = Field(description="Key ID")
    alg: str = Field(description="Algorithm (e.g., RS256)")
    n: str = Field(description="RSA modulus")
    e: str = Field(description="RSA exponent")


class JWKSResponse(BaseModel):
    """JWKS endpoint response schema."""

    keys: List[JWK]


class JWTClaims(BaseModel):
    """JWT claims structure (for documentation/validation)."""

    sub: str = Field(description="User ID")
    iss: str = Field(description="Issuer")
    aud: str = Field(description="Audience")
    iat: int = Field(description="Issued at (Unix timestamp)")
    exp: int = Field(description="Expiration (Unix timestamp)")
    email: str
    name: str
    roles: Dict[str, str] = Field(
        description="Map of project_id to role",
    )
    jti: str = Field(description="Token ID")
