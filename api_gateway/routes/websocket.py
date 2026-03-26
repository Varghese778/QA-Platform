"""WebSocket proxy route for real-time job status updates."""

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
import websockets

from api_gateway.config import get_settings
from api_gateway.core.jwt_validator import JWTValidator, JWTValidationError

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["websocket"])

# Global JWT validator instance
_jwt_validator: JWTValidator = None


async def get_jwt_validator() -> JWTValidator:
    """Get or create JWT validator."""
    global _jwt_validator
    if _jwt_validator is None:
        _jwt_validator = JWTValidator()
        await _jwt_validator.initialize()
    return _jwt_validator


@router.websocket("/ws/v1/jobs/{job_id}/status")
async def job_status_websocket(
    websocket: WebSocket,
    job_id: UUID,
    token: str = Query(None, description="JWT token for authentication"),
):
    """
    WebSocket endpoint for real-time job status updates.

    Authentication:
    - Pass JWT token as query parameter: ?token=<jwt>
    - Or use Sec-WebSocket-Protocol header with token

    Events sent:
    - { "event_type": "stage_started", "stage": "...", "timestamp": "..." }
    - { "event_type": "stage_completed", "stage": "...", "timestamp": "..." }
    - { "event_type": "job_completed", "status": "...", "timestamp": "..." }
    - { "event_type": "error", "message": "...", "timestamp": "..." }
    """
    # Extract token from query param or subprotocol
    auth_token = token
    if not auth_token:
        # Check subprotocol for token
        protocols = websocket.headers.get("sec-websocket-protocol", "").split(",")
        for protocol in protocols:
            protocol = protocol.strip()
            if protocol.startswith("access_token."):
                auth_token = protocol.replace("access_token.", "")
                break

    if not auth_token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Validate JWT
    try:
        jwt_validator = await get_jwt_validator()
        payload = await jwt_validator.validate_token(auth_token)
        claims = jwt_validator.extract_claims(payload)
        caller_id = claims["user_id"]
        roles = claims.get("roles", {})
    except JWTValidationError as e:
        logger.warning(f"WebSocket auth failed: {e.message}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Accept WebSocket connection
    await websocket.accept()

    # Connect to upstream WebSocket (Use valid UUID format for project_id to avoid 403/422 rejection)
    project_id = "00000000-0000-0000-0000-000000000001"
    upstream_url = f"{settings.async_service_url.replace('http', 'ws')}/internal/v1/ws/v1/jobs/{job_id}/status?project_id={project_id}"

    try:
        async with websockets.connect(
            upstream_url,
            additional_headers={
                "X-Caller-ID": caller_id,
                "X-Request-ID": str(UUID(int=0)),
                "Origin": "http://api-gateway:8080", # Ensure internal origin is accepted
            },
        ) as upstream_ws:
            # Bidirectional proxy
            async def forward_to_client():
                """Forward messages from upstream to client."""
                try:
                    async for message in upstream_ws:
                        await websocket.send_text(message)
                except websockets.exceptions.ConnectionClosed:
                    pass

            async def forward_to_upstream():
                """Forward messages from client to upstream."""
                try:
                    while True:
                        message = await websocket.receive_text()
                        await upstream_ws.send(message)
                except WebSocketDisconnect:
                    pass

            # Run both directions concurrently
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(forward_to_client()),
                    asyncio.create_task(forward_to_upstream()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()

    except websockets.exceptions.InvalidStatusCode as e:
        if e.status_code == 404:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        else:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
    except Exception as e:
        logger.error(f"WebSocket proxy error: {e}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
