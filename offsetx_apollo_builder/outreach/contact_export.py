"""Filtered contact-list export, with no durable intermediate file.

The existing full campaign export remains available separately. This endpoint
exports the *visible filters* over all pages and does not include mail bodies,
private internal notes or provider secrets.
"""
from __future__ import annotations

import csv
from io import StringIO
from typing import Any

from ..io_utils import spreadsheet_safe_cell

PAGE_SIZE = 500
MAX_EXPORT_ROWS = 50000
COLUMNS = (
    ("full_name", "Full Name"),
    ("email", "Email"),
    ("company", "Company"),
    ("title", "Title"),
    ("category", "Category"),
    ("route", "Route"),
    ("status", "Status"),
    ("variant_id", "Variant"),
    ("checkbox", "Selected"),
    ("sent_count", "Sent Count"),
    ("recipient_timezone", "Recipient Timezone"),
    ("linkedin_url", "LinkedIn URL"),
    ("hook_source", "Public Hook Source"),
)


class ContactExportError(ValueError):
    """An accurate, non-truncated export could not be produced."""


def contact_list_csv(
    store: Any,
    campaign_id: str,
    *,
    search: str = "",
    status: str = "",
    category: str = "",
    variant_id: str = "",
    selected_only: bool = False,
    max_rows: int = MAX_EXPORT_ROWS,
) -> bytes:
    """CSV for *all* filtered contacts, not just the displayed page.

    Detect changed totals and duplicate pages rather than returning a plausible
    but incomplete file when a campaign changes during an offset-based export.
    """
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([heading for _, heading in COLUMNS])
    offset = 0
    initial_total: int | None = None
    seen: set[str] = set()
    while initial_total is None or offset < initial_total:
        rows, total = store.list_campaign_contacts(
            campaign_id,
            limit=PAGE_SIZE,
            offset=offset,
            search=search,
            status=status,
            category=category,
            variant_id=variant_id,
            selected_only=selected_only,
        )
        if initial_total is None:
            initial_total = total
            if initial_total > max_rows:
                raise ContactExportError(
                    f"{initial_total} contacts match. The export limit is {max_rows}; "
                    "narrow the filters and try again."
                )
        if total != initial_total or (not rows and offset < initial_total):
            raise ContactExportError(
                "The contacts changed while exporting. Try again when edits have finished."
            )
        for item in rows:
            key = str(item["id"])
            if key in seen:
                raise ContactExportError(
                    "The contacts changed while exporting. Try again when edits have finished."
                )
            seen.add(key)
            writer.writerow([
                spreadsheet_safe_cell(
                    "Yes" if field == "checkbox" and item.get(field) else
                    "No" if field == "checkbox" else
                    item.get(field, "") if item.get(field) is not None else ""
                )
                for field, _ in COLUMNS
            ])
        offset += len(rows)
    return output.getvalue().encode("utf-8-sig")
