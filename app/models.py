"""
Request and response shapes for VerifyNG.

FastAPI uses these Pydantic models to validate incoming data automatically and
to generate the interactive API documentation. If a request doesn't match the
shape (for example an account number that isn't exactly 10 digits), FastAPI
rejects it before our code even runs.
"""

from pydantic import BaseModel, Field


class VerifyRequest(BaseModel):
    account_number: str = Field(
        ...,
        pattern=r"^\d{10}$",
        description="A 10-digit Nigerian bank account number.",
        examples=["3243017687"],
    )
    bank_code: str = Field(
        ...,
        description="Zone bank code for the recipient's bank.",
        examples=["400"],
    )


class VerifyResponse(BaseModel):
    verified: bool
    account_number: str
    bank_code: str
    account_name: str | None = None
    message: str
