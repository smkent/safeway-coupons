from __future__ import annotations

from pydantic import Field

from .offers import Model


class AuthFactorProfile(Model):
    email: str | None = None


class AuthFactor(Model):
    factor_type: str | None = None
    profile: AuthFactorProfile = Field(default_factory=AuthFactorProfile)

    @property
    def destination(self) -> str:
        return self.profile.email or self.factor_type or "?"


class AuthResponse(Model):
    status: str | None = None
    factors: list[AuthFactor] = Field(default_factory=list)

    @property
    def mfa_required(self) -> bool:
        return self.status == "MFA_REQUIRED"


class AuthError(Model):
    error_code: str | None = None
    message: str | None = None


class AuthErrorResponse(Model):
    errors: list[AuthError] = Field(default_factory=list)
