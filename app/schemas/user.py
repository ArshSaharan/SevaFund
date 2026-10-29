import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class UserRegister(BaseModel):
    email: str
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")
    full_name: str = Field(..., min_length=2)
    avatar_url: Optional[str] = None
    phone_number: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class GoogleAuthRequest(BaseModel):
    id_token: str = Field(..., description="Google ID Token from Google Sign-In SDK")

class OTPSendRequest(BaseModel):
    phone_number: str = Field(..., description="Indian 10-digit mobile number or +91XXXXXXXXXX")

class OTPSendResponse(BaseModel):
    phone_number: str
    message: str
    expires_in_seconds: int = 300
    dev_otp: Optional[str] = None  # Returned during development/testing for zero-friction testing

class OTPVerifyRequest(BaseModel):
    phone_number: str
    otp: str = Field(..., min_length=4, max_length=8)
    full_name: Optional[str] = None

class MakeAdminRequest(BaseModel):
    user_id: int
    secret_key: str

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: Optional[str] = None
    phone_number: Optional[str] = None
    full_name: str
    avatar_url: Optional[str] = None
    role: str
    is_identity_verified: bool
    is_email_verified: bool = False
    is_phone_verified: bool = False
    created_at: datetime.datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
