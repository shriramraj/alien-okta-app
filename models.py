from pydantic import BaseModel, EmailStr, Field


class VerifyHumanRequest(BaseModel):
    email: EmailStr = Field(..., examples=["user@example.com"])
    attestation: str = Field(..., examples=["I am a human proof string"])
    nonce: str = Field(..., examples=["unique-nonce-abc123"])


class VerifyHumanResponse(BaseModel):
    human_verified: bool
    verification_id: str | None = None
    expires_in_seconds: int | None = None  # verification TTL when verified
    reason: str | None = None  # set on failure


class EligibilityRequest(BaseModel):
    email: EmailStr = Field(..., examples=["user@example.com"])
    nonce: str = Field(..., examples=["unique-nonce-abc123"])


class EligibilityResponse(BaseModel):
    eligible: bool
    okta_user_id: str | None = None
    group_id: str | None = None
    email: str
    reason: str | None = None


class ClaimRequest(BaseModel):
    email: EmailStr = Field(..., examples=["user@example.com"])
    nonce: str = Field(..., examples=["unique-nonce-abc123"])
    amount: int = Field(..., examples=[100], ge=1)


class ClaimResponse(BaseModel):
    claim_token: str
    expires_in_seconds: int
    okta_user_id: str
    reason: str | None = None
