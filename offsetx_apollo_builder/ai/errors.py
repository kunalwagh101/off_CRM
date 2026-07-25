from __future__ import annotations

from typing import Any


class AIModuleError(RuntimeError):
    """Base class for every failure raised inside the AI module."""


class RegistryError(AIModuleError):
    """The provider registry file is missing, malformed, or self-contradictory."""


class PolicyViolation(AIModuleError):
    """A caller asked for something the trust-tier rules forbid.

    Raised *before* any network call.  Carries structured detail so the API layer
    can explain the refusal to the owner instead of dumping a stack trace.
    """

    def __init__(
        self,
        message: str,
        *,
        provider_id: str = "",
        tier: str = "",
        data_class: str = "",
        requested_policy: str = "",
        allowed_policy: str = "",
    ) -> None:
        super().__init__(message)
        self.provider_id = provider_id
        self.tier = tier
        self.data_class = data_class
        self.requested_policy = requested_policy
        self.allowed_policy = allowed_policy

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": "policy_violation",
            "message": str(self),
            "provider_id": self.provider_id,
            "tier": self.tier,
            "data_class": self.data_class,
            "requested_policy": self.requested_policy,
            "allowed_policy": self.allowed_policy,
        }


class EgressBlocked(AIModuleError):
    """The pre-flight scanner found forbidden content in an outbound payload.

    This is deliberately *not* a redaction.  Section 5.5.3 of the build brief
    requires the call to stop and the owner to be told, because a hit means the
    payload builder has a bug worth fixing.
    """

    def __init__(self, message: str, *, findings: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.findings = findings or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": "egress_blocked",
            "message": str(self),
            "findings": self.findings,
        }


class NoPermittedProvider(AIModuleError):
    """Every configured provider was filtered out before the call could happen.

    Fail-closed behaviour: an empty candidate set is an error, never a silent
    downgrade to a lower-trust model.
    """

    def __init__(self, message: str, *, considered: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.considered = considered or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": "no_permitted_provider",
            "message": str(self),
            "considered": self.considered,
        }
