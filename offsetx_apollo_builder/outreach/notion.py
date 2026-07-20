"""Notion integration: one-way export of CRM data into the user's workspace.

Design rules, matching the rest of off_CRM:
- The Notion token is stored encrypted on disk (Fernet), never in SQLite.
- Export is one-way (CRM -> Notion). Notion never becomes a write source,
  so the CRM database stays the single source of truth.
- The exporter reads the target database schema first and only writes
  properties that already exist there, matched by name (case-insensitive).
  Unknown CRM fields are skipped and reported, never guessed.
- No AI provider is involved anywhere in this path.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Callable

import requests
from cryptography.fernet import Fernet, InvalidToken

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
_TIMEOUT = 20


class NotionError(RuntimeError):
    """Raised for configuration problems or Notion API failures."""


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


class NotionSettingsStore:
    """Encrypted local storage for the Notion token plus target database ids."""

    def __init__(self, data_dir: Path | str) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.key_path = self.data_dir / "notion_key.bin"
        self.secret_path = self.data_dir / "notion_secret.bin"
        self.settings_path = self.data_dir / "notion_settings.json"
        self._lock = threading.Lock()

    def _fernet(self, *, create: bool) -> Fernet:
        if not self.key_path.exists():
            if not create:
                raise NotionError("Notion encryption key is missing")
            self.key_path.write_bytes(Fernet.generate_key())
            try:
                os.chmod(self.key_path, 0o600)
            except OSError:
                pass
        try:
            return Fernet(self.key_path.read_bytes().strip())
        except (ValueError, TypeError) as exc:
            raise NotionError("Notion encryption key is invalid") from exc

    def _settings(self) -> dict[str, Any]:
        if not self.settings_path.exists():
            return {}
        try:
            payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def token(self) -> str:
        with self._lock:
            if not self.secret_path.exists():
                return ""
            try:
                return (
                    self._fernet(create=False)
                    .decrypt(self.secret_path.read_bytes())
                    .decode("utf-8")
                )
            except (NotionError, InvalidToken):
                return ""

    def status(self) -> dict[str, Any]:
        settings = self._settings()
        return {
            "connected": bool(self.token()),
            "workspace_name": str(settings.get("workspace_name", "")),
            "contacts_database_id": str(settings.get("contacts_database_id", "")),
            "sales_database_id": str(settings.get("sales_database_id", "")),
        }

    def update(
        self,
        *,
        token: str | None = None,
        workspace_name: str | None = None,
        contacts_database_id: str | None = None,
        sales_database_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if token is not None and token.strip():
                encrypted = self._fernet(create=True).encrypt(token.strip().encode("utf-8"))
                _atomic_write(self.secret_path, encrypted)
                try:
                    os.chmod(self.secret_path, 0o600)
                except OSError:
                    pass
            settings = self._settings()
            for key, value in (
                ("workspace_name", workspace_name),
                ("contacts_database_id", contacts_database_id),
                ("sales_database_id", sales_database_id),
            ):
                if value is not None:
                    settings[key] = value.strip()
            _atomic_write(
                self.settings_path,
                json.dumps(settings, ensure_ascii=False, indent=2).encode("utf-8"),
            )
        return self.status()

    def disconnect(self) -> dict[str, Any]:
        with self._lock:
            for path in (self.secret_path, self.settings_path):
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
        return self.status()


class NotionClient:
    """Thin wrapper over the Notion REST API with uniform error handling."""

    def __init__(self, token: str, *, session: requests.Session | None = None) -> None:
        if not token:
            raise NotionError("Notion is not connected. Add an integration token first.")
        self.session = session or requests.Session()
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self.session.request(
                method,
                f"{NOTION_API_BASE}{path}",
                headers=self.headers,
                json=payload,
                timeout=_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise NotionError(f"Could not reach Notion: {exc}") from exc
        if response.status_code == 401:
            raise NotionError("Notion rejected the token. Reconnect with a valid integration token.")
        if response.status_code == 404:
            raise NotionError(
                "Notion returned 404. Share the target page or database with your integration "
                "(Share -> Invite -> your integration) and try again."
            )
        if response.status_code >= 400:
            detail = ""
            try:
                detail = str(response.json().get("message", ""))[:300]
            except (ValueError, AttributeError):
                pass
            raise NotionError(f"Notion API error {response.status_code}: {detail or response.reason}")
        try:
            return response.json()
        except ValueError as exc:
            raise NotionError("Notion returned an unreadable response") from exc

    def me(self) -> dict[str, Any]:
        payload = self._request("GET", "/users/me")
        name = str(payload.get("name") or payload.get("bot", {}).get("owner", {}).get("type", ""))
        return {"ok": True, "bot_name": name}

    def list_databases(self) -> list[dict[str, str]]:
        payload = self._request(
            "POST",
            "/search",
            {"filter": {"value": "database", "property": "object"}, "page_size": 50},
        )
        results = []
        for item in payload.get("results", []):
            title = "".join(
                str(part.get("plain_text", "")) for part in item.get("title", [])
            ).strip()
            results.append({"id": str(item.get("id", "")), "title": title or "Untitled database"})
        return results

    def database_schema(self, database_id: str) -> dict[str, dict[str, Any]]:
        payload = self._request("GET", f"/databases/{database_id}")
        properties = payload.get("properties", {})
        if not isinstance(properties, dict):
            raise NotionError("Notion database has no readable properties")
        return {str(name): dict(spec) for name, spec in properties.items()}

    def find_page_by_property(
        self, database_id: str, property_name: str, property_type: str, value: str
    ) -> str:
        filter_key = "email" if property_type == "email" else "rich_text"
        if property_type == "title":
            filter_key = "title"
        payload = self._request(
            "POST",
            f"/databases/{database_id}/query",
            {
                "filter": {"property": property_name, filter_key: {"equals": value}},
                "page_size": 1,
            },
        )
        results = payload.get("results", [])
        return str(results[0]["id"]) if results else ""

    def create_page(self, database_id: str, properties: dict[str, Any]) -> str:
        payload = self._request(
            "POST",
            "/pages",
            {"parent": {"database_id": database_id}, "properties": properties},
        )
        return str(payload.get("id", ""))

    def update_page(self, page_id: str, properties: dict[str, Any]) -> None:
        self._request("PATCH", f"/pages/{page_id}", {"properties": properties})


def _text_value(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _property_payload(prop_type: str, value: Any) -> dict[str, Any] | None:
    text = _text_value(value)
    if prop_type == "title":
        return {"title": [{"text": {"content": text[:200] or "Untitled"}}]}
    if not text:
        return None
    if prop_type == "rich_text":
        return {"rich_text": [{"text": {"content": text[:1900]}}]}
    if prop_type == "email":
        return {"email": text[:200]}
    if prop_type == "url":
        return {"url": text[:900]}
    if prop_type == "phone_number":
        return {"phone_number": text[:60]}
    if prop_type == "select":
        return {"select": {"name": text[:90]}}
    if prop_type == "status":
        return {"status": {"name": text[:90]}}
    if prop_type == "number":
        try:
            return {"number": float(text)}
        except ValueError:
            return None
    if prop_type == "date":
        return {"date": {"start": text[:30]}}
    return None


class NotionExporter:
    """Schema-aware upsert of CRM rows into a Notion database.

    Field matching is by property NAME (case-insensitive) against the target
    database. A property the database does not have is skipped and reported
    back to the user instead of causing an error.
    """

    def __init__(self, client: NotionClient) -> None:
        self.client = client

    def _match(self, schema: dict[str, dict[str, Any]]) -> dict[str, tuple[str, str]]:
        lookup: dict[str, tuple[str, str]] = {}
        for name, spec in schema.items():
            lookup[name.strip().lower()] = (name, str(spec.get("type", "")))
        return lookup

    def export_rows(
        self,
        *,
        database_id: str,
        rows: list[dict[str, Any]],
        field_map: dict[str, str],
        upsert_field: str,
    ) -> dict[str, Any]:
        """field_map: CRM row key -> desired Notion property name."""
        if not database_id:
            raise NotionError("Pick a target Notion database first.")
        schema = self.client.database_schema(database_id)
        lookup = self._match(schema)
        title_name = next(
            (name for name, spec in schema.items() if spec.get("type") == "title"),
            "",
        )
        if not title_name:
            raise NotionError("The Notion database has no title property")

        matched: dict[str, tuple[str, str]] = {}
        skipped_fields: list[str] = []
        for row_key, wanted_name in field_map.items():
            found = lookup.get(wanted_name.strip().lower())
            if found:
                matched[row_key] = found
            else:
                skipped_fields.append(wanted_name)

        upsert_property = matched.get(upsert_field)
        created = 0
        updated = 0
        failures: list[dict[str, str]] = []
        for row in rows:
            properties: dict[str, Any] = {}
            title_written = False
            for row_key, (prop_name, prop_type) in matched.items():
                payload = _property_payload(prop_type, row.get(row_key))
                if payload is None:
                    continue
                properties[prop_name] = payload
                if prop_type == "title":
                    title_written = True
            if not title_written:
                fallback = (
                    row.get("full_name")
                    or row.get("lead_name")
                    or row.get("name")
                    or row.get("email")
                    or "Untitled"
                )
                properties[title_name] = _property_payload("title", fallback)
            try:
                page_id = ""
                key_value = _text_value(row.get(upsert_field)) if upsert_property else ""
                if upsert_property and key_value:
                    page_id = self.client.find_page_by_property(
                        database_id, upsert_property[0], upsert_property[1], key_value
                    )
                if page_id:
                    self.client.update_page(page_id, properties)
                    updated += 1
                else:
                    self.client.create_page(database_id, properties)
                    created += 1
            except NotionError as exc:
                failures.append(
                    {
                        "row": _text_value(
                            row.get("full_name") or row.get("lead_name") or row.get("email")
                        ),
                        "error": str(exc)[:300],
                    }
                )
        return {
            "created": created,
            "updated": updated,
            "failed": len(failures),
            "failures": failures[:20],
            "skipped_fields": sorted(set(skipped_fields)),
        }


CONTACT_FIELD_MAP = {
    "full_name": "Name",
    "email": "Email",
    "company": "Company",
    "title": "Title",
    "status": "Status",
    "category": "Category",
    "variant_id": "Variant",
    "linkedin_url": "LinkedIn",
}

SALES_LEAD_FIELD_MAP = {
    "lead_name": "Name",
    "company": "Company",
    "email": "Email",
    "status": "Stage",
    "setter_name": "Setter",
    "source": "Source",
    "total_deal_value": "Deal value",
    "cash_collected": "Cash collected",
    "last_touch_at": "Last touch",
}


def export_campaign_contacts(
    *,
    exporter: NotionExporter,
    database_id: str,
    list_contacts: Callable[..., tuple[list[dict[str, Any]], int]],
    campaign_id: str,
    limit: int = 500,
) -> dict[str, Any]:
    rows, _total = list_contacts(campaign_id, limit=limit, offset=0)
    if not rows:
        raise NotionError("This campaign has no contacts to export yet.")
    return exporter.export_rows(
        database_id=database_id,
        rows=rows,
        field_map=CONTACT_FIELD_MAP,
        upsert_field="email",
    )


def export_sales_leads(
    *,
    exporter: NotionExporter,
    database_id: str,
    list_leads: Callable[..., tuple[list[dict[str, Any]], int]],
    limit: int = 500,
) -> dict[str, Any]:
    rows, _total = list_leads(limit=limit, offset=0)
    if not rows:
        raise NotionError("There are no sales leads to export yet.")
    return exporter.export_rows(
        database_id=database_id,
        rows=rows,
        field_map=SALES_LEAD_FIELD_MAP,
        upsert_field="lead_name",
    )
