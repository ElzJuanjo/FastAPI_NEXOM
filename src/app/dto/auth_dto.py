"""
DTOs para autenticación: request bodies y response bodies.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    referral_code: Optional[str] = Field(default=None, description="Código de referido de quien te invitó")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., description="Token de verificación recibido por email")


class ResendVerificationRequest(BaseModel):
    email: EmailStr
    

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)
    

class Verify2FARequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)
    

class Disable2FARequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)
    

class Verify2FALoginRequest(BaseModel):
    temp_token: str
    code: str = Field(min_length=6, max_length=6)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    
    
class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    avatar_url: str | None = None
    is_active: bool
    is_verified: bool
    is_2fa_enabled: bool = False

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse


class VerifyEmailResponse(BaseModel):
    message: str
    is_verified: bool


class ResendVerificationResponse(BaseModel):
    message: str
    

class ChangePasswordResponse(BaseModel):
    message: str


class Setup2FAResponse(BaseModel):
    secret: str
    otpauth_url: str
    qr_base64: str
    

class Verify2FAResponse(BaseModel):
    message: str
    is_2fa_enabled: bool
    

class AuthLoginResponse(BaseModel):
    """Response que puede requerir 2FA."""
    user: Optional[UserResponse] = None
    tokens: Optional[TokenResponse] = None
    requires_2fa: bool = False
    temp_token: Optional[str] = None
    

class ForgotPasswordResponse(BaseModel):
    message: str
    

class ResetPasswordResponse(BaseModel):
    message: str