"""
Integration with Zone's Name Inquiry API - the heart of VerifyNG.

It takes an account number and bank code, calls Zone's real endpoint with the
required `x-Api-key` header, and interprets the response.

USE_MOCK (default "true") lets the app run with no Zone credentials by returning
realistic, Zone-shaped responses. Set USE_MOCK=false and provide ZONE_API_KEY to
call Zone's real test endpoint.
"""

import os
import logging

import httpx

logger = logging.getLogger("verifyng")

# ---------------------------------------------------------------------------
# A note on the upstream API (important - read before going live):
#
# The AppZone family exposes more than one "name inquiry" API, and they are NOT
# the same product:
#
#   * Zone (the payment switch)  -  card-present.readme.io
#       endpoint:  https://devagency.appzonegroup.com/api/v1/name-inquiry
#       auth:      API key in the `x-Api-key` HEADER
#       body:      camelCase  ->  accountNumber, bankCode
#
#   * BankOne (a core-banking product) -  docs.mybankone.com
#       endpoint:  .../Transfer/NameEnquiry
#       auth:      a `Token` inside the request BODY
#       body:      PascalCase ->  AccountNumber, Bankcode
#
# This client targets ZONE's API, because impressing Zone is the goal. It runs
# in mock mode by default, so the exact live contract does not block anything.
# When a Zone contact grants you real access, confirm the endpoint, the auth
# field, and the response field names with them, then adjust the few lines in
# _live_inquiry() to match. That is a small change, not a rewrite.
# ---------------------------------------------------------------------------

NAME_INQUIRY_PATH = "/api/v1/name-inquiry"

# A test account number from Zone's documentation (the "successful" case).
# Used only in mock mode so the app works without live credentials.
_MOCK_SUCCESS_ACCOUNTS = {
    "3243017687": "JOHN OKAFOR",
}


class NameInquiryResult:
    """A simple container for the outcome of a name inquiry."""

    def __init__(self, verified: bool, account_name: str | None, message: str):
        self.verified = verified
        self.account_name = account_name
        self.message = message


def name_inquiry(account_number: str, bank_code: str) -> NameInquiryResult:
    """Look up the account holder's name. Uses mock or live mode based on config."""
    use_mock = os.environ.get("USE_MOCK", "true").lower() == "true"
    if use_mock:
        return _mock_inquiry(account_number, bank_code)
    return _live_inquiry(account_number, bank_code)


def _mock_inquiry(account_number: str, bank_code: str) -> NameInquiryResult:
    logger.info("Mock name inquiry (no live call made)")
    name = _MOCK_SUCCESS_ACCOUNTS.get(account_number)
    if name:
        return NameInquiryResult(True, name, "Account verified")
    return NameInquiryResult(False, None, "Account number does not exist")


def _live_inquiry(account_number: str, bank_code: str) -> NameInquiryResult:
    # This is written for ZONE's card-present Name Inquiry API. If your Zone
    # contact points you to a different endpoint/format, adjust these lines.
    base_url = os.environ.get("ZONE_BASE_URL", "https://devagency.appzonegroup.com")
    api_key = os.environ.get("ZONE_API_KEY", "")
    url = base_url + NAME_INQUIRY_PATH

    headers = {"x-Api-key": api_key, "Content-Type": "application/json"}
    payload = {"accountNumber": account_number, "bankCode": bank_code}

    logger.info("Calling Zone Name Inquiry at %s", url)
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        logger.error("Could not reach Zone: %s", exc)
        return NameInquiryResult(False, None, "Could not reach Zone")

    if resp.status_code != 200:
        logger.warning("Zone returned HTTP %s", resp.status_code)
        return NameInquiryResult(False, None, f"Zone returned status {resp.status_code}")

    data = resp.json()
    # The exact field name depends on Zone's response shape, so we read a few
    # likely spots defensively. Confirm against the live response when you have
    # working credentials. (For reference, BankOne's API returns the name in a
    # field called "Name"; Zone's card-present API may differ.)
    account_name = (
        data.get("accountName")
        or data.get("account_name")
        or data.get("Name")
        or (data.get("data") or {}).get("accountName")
    )
    if account_name:
        return NameInquiryResult(True, account_name, "Account verified")
    return NameInquiryResult(False, None, data.get("message", "Account not found"))
