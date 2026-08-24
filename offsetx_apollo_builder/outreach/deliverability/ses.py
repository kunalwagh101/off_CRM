from __future__ import annotations

import re
from datetime import datetime
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formataddr, make_msgid
from typing import Any, Mapping

from ..models import IncomingMessage, SendResult
from .models import (
    AmbiguousDeliveryError,
    PermanentDeliveryError,
    RetryableDeliveryError,
    valid_email,
)

_HEADER_NAME = re.compile(r"^[A-Za-z0-9-]{1,78}$")
_TAG = re.compile(r"^[A-Za-z0-9_-]{1,256}$")


def _boto3_client(region: str) -> Any:
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - exercised without the optional extra
        raise RuntimeError(
            "Amazon SES support is not installed. Run: uv sync --extra email --locked"
        ) from exc
    return boto3.client("sesv2", region_name=region)


class SesMailProvider:
    provider_type = "ses"

    def __init__(
        self,
        *,
        region: str,
        configuration_set: str = "",
        client: Any | None = None,
    ):
        if not region:
            raise ValueError("Amazon SES region is required")
        self.region = region
        self.configuration_set = configuration_set.strip()
        self.client = client or _boto3_client(region)

    def identity_status(self, identity: str) -> dict[str, Any]:
        if not identity:
            raise ValueError("Amazon SES identity is required")
        return dict(self.client.get_email_identity(EmailIdentity=identity))

    @staticmethod
    def _safe_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
        result: dict[str, str] = {}
        for raw_name, raw_value in (headers or {}).items():
            name = str(raw_name)
            value = str(raw_value)
            if not _HEADER_NAME.fullmatch(name) or "\n" in value or "\r" in value:
                raise ValueError("Email header contains invalid characters")
            lowered = name.lower()
            if lowered in {"to", "from", "subject", "reply-to", "message-id", "date"}:
                raise ValueError(f"Email header cannot override {name}")
            result[name] = value
        return result

    def send_message(
        self,
        *,
        to_email: str,
        subject: str,
        body: str,
        thread_id: str = "",
        in_reply_to: str = "",
        references: str = "",
        idempotency_key: str = "",
        from_email: str = "",
        from_name: str = "",
        reply_to: str = "",
        headers: Mapping[str, str] | None = None,
        tags: Mapping[str, str] | None = None,
    ) -> SendResult:
        del thread_id
        if not valid_email(to_email, ascii_only=True):
            raise PermanentDeliveryError("SES requires a valid ASCII recipient address")
        if not valid_email(from_email, ascii_only=True):
            raise PermanentDeliveryError("SES requires a valid ASCII From address")
        if reply_to and not valid_email(reply_to, ascii_only=True):
            raise PermanentDeliveryError("SES Reply-To address is invalid")

        message = EmailMessage()
        message["To"] = to_email
        message["From"] = formataddr((from_name, from_email)) if from_name else from_email
        message["Subject"] = subject
        message["Message-ID"] = make_msgid(domain=from_email.rsplit("@", 1)[1])
        if reply_to:
            message["Reply-To"] = reply_to
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
        if references:
            message["References"] = references
        if idempotency_key:
            message["X-off-CRM-Idempotency-Key"] = idempotency_key
        for name, value in self._safe_headers(headers).items():
            message[name] = value
        message.set_content(body)

        request: dict[str, Any] = {
            "FromEmailAddress": from_email,
            "Destination": {"ToAddresses": [to_email]},
            "Content": {"Raw": {"Data": message.as_bytes(policy=SMTP)}},
        }
        if self.configuration_set:
            request["ConfigurationSetName"] = self.configuration_set
        email_tags = []
        for name, value in (tags or {}).items():
            clean_name = str(name)
            clean_value = str(value)[:256]
            if _TAG.fullmatch(clean_name) and clean_value and "\n" not in clean_value:
                email_tags.append({"Name": clean_name, "Value": clean_value})
        if email_tags:
            request["EmailTags"] = email_tags

        try:
            response = self.client.send_email(**request)
        except Exception as exc:
            self._raise_provider_error(exc)
            raise AssertionError("unreachable")
        message_id = str(response.get("MessageId", "")).strip()
        if not message_id:
            raise AmbiguousDeliveryError("SES returned no MessageId; provider state is unknown")
        return SendResult(
            provider_message_id=message_id,
            thread_id=message_id,
            internet_message_id=str(message["Message-ID"]),
            raw={
                "provider": "ses",
                "region": self.region,
                "configuration_set": self.configuration_set,
                "response_metadata": response.get("ResponseMetadata", {}),
            },
        )

    @staticmethod
    def _raise_provider_error(exc: Exception) -> None:
        response = getattr(exc, "response", {}) or {}
        error = response.get("Error", {}) if isinstance(response, dict) else {}
        metadata = response.get("ResponseMetadata", {}) if isinstance(response, dict) else {}
        code = str(error.get("Code") or exc.__class__.__name__)
        message = str(error.get("Message") or exc)[:1000]
        status = int(metadata.get("HTTPStatusCode") or 0)
        if status == 429 or status >= 500 or code in {
            "TooManyRequestsException",
            "LimitExceededException",
            "ThrottlingException",
            "ServiceUnavailableException",
        }:
            retry_after = metadata.get("HTTPHeaders", {}).get("retry-after")
            raise RetryableDeliveryError(
                f"SES temporarily refused the request: {message}",
                retry_after_seconds=int(retry_after) if str(retry_after).isdigit() else None,
            ) from exc
        if code in {
            "BadRequestException",
            "MessageRejected",
            "MailFromDomainNotVerifiedException",
            "NotFoundException",
            "AccessDeniedException",
        } or status in {400, 401, 403, 404}:
            raise PermanentDeliveryError(f"SES rejected the message: {message}") from exc
        if exc.__class__.__name__ in {"EndpointConnectionError", "ConnectTimeoutError"}:
            raise RetryableDeliveryError(f"SES connection failed before a response: {message}") from exc
        raise AmbiguousDeliveryError(f"SES delivery state is unknown: {message}") from exc

    def list_replies(self, *, since: datetime, own_email: str) -> list[IncomingMessage]:
        del since, own_email
        return []
