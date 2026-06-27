"""
VerifyNG - an account name verification service built on Zone's Name Inquiry API.

Endpoints:
  GET  /health   - liveness check (handy for containers)
  POST /verify   - verify an account number and return the account holder's name
  GET  /recent   - the last few checks from this run (demo convenience)

Interactive API docs are auto-generated at /docs.
"""

import os
import logging
from collections import deque
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI

from app.models import VerifyRequest, VerifyResponse
from app import zone_client

# Load .env (local development). In the container there is no .env, so this is a
# no-op and the real values come from the container's environment variables.
load_dotenv()

# --- Observability -----------------------------------------------------------
# If an Application Insights connection string is set, send logs and traces
# there. We always log to stdout too (Azure Container Instances captures it).
APPINSIGHTS = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
if APPINSIGHTS:
    from azure.monitor.opentelemetry import configure_azure_monitor
    configure_azure_monitor(connection_string=APPINSIGHTS)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("verifyng")
# Set the level explicitly. When Application Insights is configured it attaches a
# handler to the root logger, which makes basicConfig() above a no-op and leaves
# the level at WARNING - so our INFO logs would never be sent. This line ensures
# they always emit, locally and in the cloud.
logger.setLevel(logging.INFO)

app = FastAPI(
    title="VerifyNG",
    description="Account name verification built on Zone's Name Inquiry API.",
    version="1.0.0",
)

# Keep the last 20 checks in memory so /recent can show them (demo only).
_recent: deque = deque(maxlen=20)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/verify", response_model=VerifyResponse)
def verify(request: VerifyRequest):
    masked = _mask(request.account_number)
    logger.info("Verify request: %s / bank %s", masked, request.bank_code)

    result = zone_client.name_inquiry(request.account_number, request.bank_code)

    _recent.appendleft({
        "account_number": masked,
        "bank_code": request.bank_code,
        "verified": result.verified,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    })
    logger.info("Verify result: verified=%s", result.verified)

    return VerifyResponse(
        verified=result.verified,
        account_number=request.account_number,
        bank_code=request.bank_code,
        account_name=result.account_name,
        message=result.message,
    )


@app.get("/recent")
def recent():
    return {"count": len(_recent), "checks": list(_recent)}


def _mask(account_number: str) -> str:
    """Mask the middle digits for privacy in logs and history."""
    if len(account_number) >= 6:
        return account_number[:3] + "****" + account_number[-3:]
    return "****"