"""Lambda entry point for the demo API, fronted by CloudFront.

CloudFront serves the React bundle from S3 and forwards ``/api/*`` to this
function through an HTTP API. There is no viewer authentication: the demo URL is
public on purpose. What is guarded is the *path* to the function, because the API
Gateway endpoint is reachable directly on the internet and every request here can
spend money (Bedrock tokens plus $7 per 1,000 searches).

CloudFront injects a custom header that only it knows, and requests arriving
without it are refused. The API Gateway authorizer checks the same header first,
so this middleware is the second of two identical gates: cheap to keep, and it
means a misconfigured route cannot expose the agent.

The check is skipped when ``DEMO_ORIGIN_SECRET`` is absent, so local development
via uvicorn is unaffected.

Spend is bounded by reserved concurrency on this function rather than by a login.
See ``deploy/app-hosting.yaml``.
"""

from __future__ import annotations

import hmac
import os

from fastapi import Request
from fastapi.responses import JSONResponse
from mangum import Mangum

from api.main import app

# Header CloudFront adds to every origin request. Kept non-obvious so it is not
# guessable from a wordlist.
ORIGIN_SECRET_HEADER = "x-demo-origin-secret"

# Health check stays open so CloudFront and curl can probe without the secret.
UNPROTECTED_PATHS = {"/api/health"}


def _equal(left: str, right: str) -> bool:
    """Constant-time comparison, so a timing side channel cannot leak the secret."""
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


@app.middleware("http")
async def enforce_origin_secret(request: Request, call_next):
    """Refuse requests that did not arrive through CloudFront."""
    if request.url.path in UNPROTECTED_PATHS:
        return await call_next(request)

    expected = os.environ.get("DEMO_ORIGIN_SECRET", "")
    if expected:
        presented = request.headers.get(ORIGIN_SECRET_HEADER, "")
        if not presented or not _equal(presented, expected):
            # Deliberately vague: do not confirm to a prober that the header exists.
            return JSONResponse({"detail": "Not found."}, status_code=404)

    return await call_next(request)


# Mangum translates the API Gateway v2 payload shape into ASGI. lifespan is off
# because there is nothing to start up per container and it adds cold-start
# latency.
handler = Mangum(app, lifespan="off", api_gateway_base_path="/")
