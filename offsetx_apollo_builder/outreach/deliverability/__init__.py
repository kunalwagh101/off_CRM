"""Deterministic email delivery protections and durable bulk sending."""

from .models import (
    EMAIL_STREAMS,
    PERMISSION_MARKETING,
    TARGETED_OUTREACH,
    TRANSACTIONAL,
    PreflightReport,
)

__all__ = [
    "EMAIL_STREAMS",
    "PERMISSION_MARKETING",
    "TARGETED_OUTREACH",
    "TRANSACTIONAL",
    "PreflightReport",
]
