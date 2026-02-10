import os
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


def _cors_headers(request: Request) -> dict:
    """Return CORS headers so error responses are not blocked by the browser."""
    origin = request.headers.get("origin", "*")
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "*",
        "Access-Control-Allow-Headers": "*",
    }


class PasswordAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to check password authentication for all API requests.
    Only active when OPEN_NOTEBOOK_PASSWORD environment variable is set.
    """

    def __init__(self, app, excluded_paths: Optional[list] = None):
        super().__init__(app)
        self.password = os.environ.get("OPEN_NOTEBOOK_PASSWORD")
        self.excluded_paths = excluded_paths or [
            "/",
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
        ]

    async def dispatch(self, request: Request, call_next):
        # Skip authentication if no password is set
        if not self.password:
            return await call_next(request)

        # Skip authentication for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        # Skip authentication for CORS preflight requests (OPTIONS)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Check authorization header (wrap in try/except so parsing errors return 401 with CORS)
        try:
            auth_header = request.headers.get("Authorization")

            if not auth_header:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Missing authorization header"},
                    headers={**{"WWW-Authenticate": "Bearer"}, **_cors_headers(request)},
                )

            # Expected format: "Bearer {password}"
            scheme, credentials = auth_header.split(" ", 1)
            if scheme.lower() != "bearer":
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid authorization header format"},
                    headers={**{"WWW-Authenticate": "Bearer"}, **_cors_headers(request)},
                )

            # Check password
            if credentials != self.password:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid password"},
                    headers={**{"WWW-Authenticate": "Bearer"}, **_cors_headers(request)},
                )
        except (ValueError, AttributeError):
            # split() or header value edge cases
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authorization header format"},
                headers={**{"WWW-Authenticate": "Bearer"}, **_cors_headers(request)},
            )

        # Password is correct, proceed with the request
        return await call_next(request)


# Optional: HTTPBearer security scheme for OpenAPI documentation
security = HTTPBearer(auto_error=False)


def check_api_password(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> bool:
    """
    Utility function to check API password.
    Can be used as a dependency in individual routes if needed.
    """
    password = os.environ.get("OPEN_NOTEBOOK_PASSWORD")

    # No password set, allow access
    if not password:
        return True

    # No credentials provided
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check password
    if credentials.credentials != password:
        raise HTTPException(
            status_code=401,
            detail="Invalid password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True
