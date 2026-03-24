"""Request ID middleware - generates and propagates X-Request-ID."""

import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle X-Request-ID header.

    - If client provides X-Request-ID, validates it's a proper UUID and uses it
    - If not provided, generates a new UUID v4
    - Propagates the ID in the response header
    - Stores the ID in request.state for access by other components
    """

    HEADER_NAME = "X-Request-ID"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and inject/propagate request ID."""
        request_id = request.headers.get(self.HEADER_NAME)

        # Validate or generate request ID
        if request_id:
            try:
                # Validate it's a proper UUID
                uuid.UUID(request_id)
            except ValueError:
                # Invalid UUID, generate new one
                request_id = str(uuid.uuid4())
        else:
            request_id = str(uuid.uuid4())

        # Store in request state for access by other components
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers[self.HEADER_NAME] = request_id

        return response
