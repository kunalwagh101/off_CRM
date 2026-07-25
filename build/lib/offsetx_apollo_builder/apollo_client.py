"""Thin Apollo API client with retries, fixed-window friendly throttling, and safe defaults."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests


class ApolloApiError(RuntimeError):
    pass


@dataclass
class ApolloClient:
    api_key: str
    base_url: str = "https://api.apollo.io/api/v1"
    timeout_seconds: int = 45
    sleep_seconds: float = 0.75
    max_retries: int = 4

    @classmethod
    def from_env(cls) -> "ApolloClient":
        api_key = os.getenv("APOLLO_API_KEY", "").strip()
        if not api_key:
            raise ApolloApiError("APOLLO_API_KEY is missing. Put it in .env, not in chat.")
        base_url = os.getenv("APOLLO_BASE_URL", "https://api.apollo.io/api/v1").rstrip("/")
        return cls(api_key=api_key, base_url=base_url)

    @property
    def headers(self) -> dict[str, str]:
        # Apollo expects the API key in the x-api-key header.
        return {
            "accept": "application/json",
            "content-type": "application/json",
            "cache-control": "no-cache",
            "x-api-key": self.api_key,
        }

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            if self.sleep_seconds:
                time.sleep(self.sleep_seconds)
            try:
                response = requests.post(url, json=payload, headers=self.headers, timeout=self.timeout_seconds)
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(min(2 ** attempt, 20))
                continue

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                sleep_for = float(retry_after) if retry_after and retry_after.isdigit() else min(2 ** attempt * 2, 60)
                time.sleep(sleep_for)
                continue
            if 500 <= response.status_code < 600:
                last_error = ApolloApiError(f"Apollo {response.status_code}: {response.text[:500]}")
                time.sleep(min(2 ** attempt, 30))
                continue
            if not response.ok:
                raise ApolloApiError(f"Apollo {response.status_code}: {response.text[:1000]}")
            try:
                return response.json()
            except ValueError as exc:
                raise ApolloApiError(f"Apollo returned non-JSON response: {response.text[:500]}") from exc
        raise ApolloApiError(f"Apollo request failed after retries: {last_error}")

    def people_search(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post("mixed_people/api_search", payload)

    def bulk_people_enrich(self, details: list[dict[str, Any]], *, reveal_personal_emails: bool = False) -> dict[str, Any]:
        if not 1 <= len(details) <= 10:
            raise ValueError("Apollo bulk people enrichment supports 1 to 10 people per call.")
        payload = {"details": details, "reveal_personal_emails": reveal_personal_emails}
        return self.post("people/bulk_match", payload)
