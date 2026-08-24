from __future__ import annotations

import re
from typing import Any, Protocol

import requests

_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}\.?$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.?$"
)


class TxtResolver(Protocol):
    def query(self, name: str, record_type: str) -> list[str]: ...


class GoogleDohResolver:
    """Small DNS-over-HTTPS client; domains are public and no contact data is sent."""

    ENDPOINT = "https://dns.google/resolve"

    def __init__(self, *, session: Any | None = None, timeout_seconds: int = 10):
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds

    def query(self, name: str, record_type: str) -> list[str]:
        normalized = name.strip().lower().rstrip(".")
        if not _DOMAIN_RE.fullmatch(normalized):
            raise ValueError(f"Invalid DNS name: {name}")
        response = self.session.get(
            self.ENDPOINT,
            params={"name": normalized, "type": record_type.upper(), "do": "true"},
            headers={"Accept": "application/dns-json"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if int(payload.get("Status", -1)) not in {0, 3}:
            raise RuntimeError(f"DNS lookup returned status {payload.get('Status')}")
        return [
            str(answer.get("data", ""))
            for answer in payload.get("Answer", [])
            if isinstance(answer, dict) and answer.get("data")
        ]


def _txt(value: str) -> str:
    # DNS JSON represents split TXT strings as adjacent quoted chunks.
    chunks = re.findall(r'"([^"]*)"', value)
    return "".join(chunks) if chunks else value.strip().strip('"')


def _domain_from_email(value: str) -> str:
    return value.rsplit("@", 1)[-1].lower() if "@" in value else ""


def _aligned(candidate: str, from_domain: str) -> bool:
    candidate = candidate.lower().rstrip(".")
    from_domain = from_domain.lower().rstrip(".")
    return bool(candidate and from_domain) and (
        candidate == from_domain or candidate.endswith("." + from_domain)
    )


class DomainAuthChecker:
    def __init__(self, resolver: TxtResolver | None = None):
        self.resolver = resolver or GoogleDohResolver()

    def check(
        self,
        identity: dict[str, Any],
        *,
        provider_details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from_domain = _domain_from_email(str(identity.get("from_email", "")))
        configured_domain = str(identity.get("domain") or from_domain).lower().rstrip(".")
        if configured_domain != from_domain:
            raise ValueError("Sending identity domain must match the From address")
        details: dict[str, Any] = {"domain": from_domain, "lookups": {}, "errors": []}

        def lookup(name: str, record_type: str) -> list[str]:
            try:
                values = self.resolver.query(name, record_type)
            except Exception as exc:
                details["errors"].append(f"{record_type} {name}: {str(exc)[:300]}")
                return []
            details["lookups"][f"{record_type}:{name}"] = values
            return values

        mail_from = str(identity.get("mail_from_domain") or from_domain).lower().rstrip(".")
        spf_records = [_txt(value) for value in lookup(mail_from, "TXT")]
        spf_records = [value for value in spf_records if value.lower().startswith("v=spf1")]
        if identity.get("provider_type") == "ses":
            spf_pass = any("include:amazonses.com" in value.lower() for value in spf_records)
        else:
            spf_pass = bool(spf_records)

        dmarc_records = [_txt(value) for value in lookup(f"_dmarc.{from_domain}", "TXT")]
        dmarc_records = [value for value in dmarc_records if value.lower().startswith("v=dmarc1")]
        policy = ""
        if dmarc_records:
            match = re.search(r"(?:^|;)\s*p\s*=\s*(none|quarantine|reject)\b", dmarc_records[0], re.I)
            policy = match.group(1).lower() if match else ""

        provider_details = provider_details or {}
        verified = bool(provider_details.get("VerifiedForSendingStatus"))
        dkim_attributes = provider_details.get("DkimAttributes") or {}
        provider_dkim = str(dkim_attributes.get("Status", "")).upper()
        dkim_pass = provider_dkim == "SUCCESS"
        selector = str(identity.get("dkim_selector", "")).lower().strip()
        if selector and not dkim_pass:
            dkim_name = f"{selector}._domainkey.{from_domain}"
            dkim_values = lookup(dkim_name, "TXT") + lookup(dkim_name, "CNAME")
            dkim_pass = bool(dkim_values)

        if identity.get("provider_type") != "ses":
            # Local/Gmail do not expose an SES identity verification state.
            verified = True

        signing_domain = str(identity.get("ses_identity") or from_domain).lower()
        if "@" in signing_domain:
            signing_domain = _domain_from_email(signing_domain)
        alignment_pass = dkim_pass and _aligned(signing_domain, from_domain)
        if mail_from != from_domain:
            alignment_pass = alignment_pass or (spf_pass and _aligned(mail_from, from_domain))

        details["spf_records"] = spf_records
        details["dmarc_records"] = dmarc_records
        details["provider"] = provider_details
        return {
            "provider_verified": verified,
            "spf_status": "pass" if spf_pass else ("unknown" if details["errors"] else "fail"),
            "dkim_status": "pass" if dkim_pass else ("unknown" if details["errors"] else "fail"),
            "dmarc_status": "pass" if policy else ("unknown" if details["errors"] else "fail"),
            "alignment_status": "pass" if alignment_pass else (
                "unknown" if not dkim_pass and details["errors"] else "fail"
            ),
            "dmarc_policy": policy,
            "details": details,
        }
