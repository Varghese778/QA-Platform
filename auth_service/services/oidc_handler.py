"""OIDC Authentication Handler - validates IdP identity tokens."""

import logging
from dataclasses import dataclass
from typing import Optional

from auth_service.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class OIDCUserClaims:
    """Claims extracted from OIDC ID token."""

    sub: str  # IdP subject
    email: str
    name: str
    email_verified: bool = True
    idp_provider: str = "mock"


class OIDCValidationError(Exception):
    """Raised when OIDC token validation fails."""

    def __init__(self, message: str, error_code: str = "invalid_token"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class OIDCAuthHandler:
    """
    Validates IdP identity tokens and extracts user claims.

    For MVP, this mocks the external IdP network call.
    In production, this would validate against the IdP's JWKS endpoint.
    """

    def __init__(self):
        self.issuer = settings.oidc_issuer
        self.audience = settings.oidc_audience

    async def validate_identity_token(self, identity_token: str) -> OIDCUserClaims:
        """
        Validate an OIDC identity token from the IdP.

        Args:
            identity_token: The IdP-issued ID token.

        Returns:
            OIDCUserClaims with extracted user information.

        Raises:
            OIDCValidationError: If token validation fails.
        """
        # MVP: Mock validation
        # In production, this would:
        # 1. Fetch IdP JWKS from .well-known/jwks.json
        # 2. Validate token signature using RS256/ES256
        # 3. Validate issuer, audience, expiry
        # 4. Extract claims

        if not identity_token:
            raise OIDCValidationError("Identity token is required", "missing_token")

        # Mock: Parse a simple token format for testing
        # Format: "mock_token:<sub>:<email>:<name>"
        if identity_token.startswith("mock_token:"):
            try:
                parts = identity_token.split(":")
                if len(parts) >= 4:
                    return OIDCUserClaims(
                        sub=parts[1],
                        email=parts[2],
                        name=parts[3],
                        idp_provider="mock",
                    )
            except Exception as e:
                logger.warning(f"Failed to parse mock token: {e}")
                raise OIDCValidationError("Invalid token format", "invalid_format")

        # For any other token in MVP, return mock claims based on token hash
        # This simulates successful validation
        import hashlib

        token_hash = hashlib.md5(identity_token.encode()).hexdigest()[:8]

        return OIDCUserClaims(
            sub=f"idp_sub_{token_hash}",
            email=f"user_{token_hash}@example.com",
            name=f"User {token_hash.upper()}",
            idp_provider="mock",
        )

    async def validate_token_signature(self, token: str) -> bool:
        """
        Validate just the token signature (without full claims validation).

        Args:
            token: The ID token to validate.

        Returns:
            True if signature is valid.
        """
        # MVP: Always return True for non-empty tokens
        return bool(token and len(token) > 0)
