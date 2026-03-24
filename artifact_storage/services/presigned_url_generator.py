"""Pre-Signed URL Generator - create temporary download URLs."""

import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from artifact_storage.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class PreSignedURLGenerator:
    """Generator for temporary pre-signed download URLs."""

    @staticmethod
    def generate_token(
        artifact_id: UUID,
        project_id: UUID,
        ttl_seconds: int = None,
    ) -> str:
        """
        Generate a pre-signed URL token.

        Args:
            artifact_id: Artifact ID to download
            project_id: Project ID
            ttl_seconds: Time-to-live in seconds (default from settings)

        Returns:
            Encoded token
        """
        if ttl_seconds is None:
            ttl_seconds = settings.presigned_url_ttl_seconds

        # Create expiration time
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

        # Create payload
        payload = {
            "artifact_id": str(artifact_id),
            "project_id": str(project_id),
            "expires_at": expires_at.isoformat(),
        }

        # Serialize and sign
        payload_json = json.dumps(payload, sort_keys=True)
        payload_bytes = payload_json.encode("utf-8")

        # HMAC-SHA256 signature
        signature = hmac.new(
            settings.token_secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).digest()

        # Combine payload and signature
        token_data = payload_bytes + b"|" + signature

        # Base64 encode
        token = base64.b64encode(token_data).decode("utf-8")

        logger.debug(f"Generated pre-signed token for artifact {artifact_id}")
        return token

    @staticmethod
    def verify_token(token: str) -> dict:
        """
        Verify and decode a pre-signed URL token.

        Args:
            token: Encoded token

        Returns:
            Decoded payload

        Raises:
            ValueError: If token is invalid or expired
        """
        try:
            # Base64 decode
            token_data = base64.b64decode(token.encode("utf-8"))

            # Split payload and signature
            parts = token_data.split(b"|")
            if len(parts) != 2:
                raise ValueError("Invalid token format")

            payload_bytes, signature = parts

            # Verify signature
            expected_signature = hmac.new(
                settings.token_secret.encode("utf-8"),
                payload_bytes,
                hashlib.sha256,
            ).digest()

            if not hmac.compare_digest(signature, expected_signature):
                raise ValueError("Invalid token signature")

            # Deserialize payload
            payload_json = payload_bytes.decode("utf-8")
            payload = json.loads(payload_json)

            # Check expiration
            expires_at = datetime.fromisoformat(payload["expires_at"])
            if datetime.now(timezone.utc) > expires_at:
                raise ValueError("Token expired")

            logger.debug(f"Verified pre-signed token for artifact {payload['artifact_id']}")
            return payload

        except (ValueError, json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Token verification failed: {e}")
            raise ValueError(f"Invalid pre-signed token: {e}")

    @staticmethod
    def generate_download_url(
        artifact_id: UUID,
        project_id: UUID,
        base_url: str,
        ttl_seconds: int = None,
    ) -> tuple[str, datetime]:
        """
        Generate a full download URL with token.

        Args:
            artifact_id: Artifact ID
            project_id: Project ID
            base_url: Base URL of the service (e.g., https://api.example.com)
            ttl_seconds: Time-to-live in seconds

        Returns:
            Tuple of (download_url, expires_at)
        """
        if ttl_seconds is None:
            ttl_seconds = settings.presigned_url_ttl_seconds

        token = PreSignedURLGenerator.generate_token(
            artifact_id, project_id, ttl_seconds
        )

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

        download_url = (
            f"{base_url}/internal/v1/artifacts/{artifact_id}/download?token={token}"
        )

        return download_url, expires_at
