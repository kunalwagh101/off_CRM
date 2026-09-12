"""Run-scoped page-read cache rules for autonomous browser work.

A cache hit must mean "the same page we already captured", not merely "a URL
that looks close enough".  The canonicaliser is therefore deliberately
conservative: it removes only well-known analytics/ad click identifiers and
keeps functional query parameters, path and fragment intact.

The cache itself belongs to :mod:`agent.run`, not :class:`browser.page.Page`.
A Page is browser state and may outlive a single agent run; putting research
memory there would let one run accidentally inherit another run's evidence.
"""

from __future__ import annotations

from urllib.parse import unquote_plus, urlsplit, urlunsplit

TRACKING_PARAMETER_PREFIXES = ("utm_", "mtm_")
TRACKING_PARAMETER_NAMES = frozenset(
    {
        "_ga",
        "_gl",
        "_hsenc",
        "_hsmi",
        "dclid",
        "fbclid",
        "gad_source",
        "gbraid",
        "gclid",
        "igshid",
        "li_fat_id",
        "mc_cid",
        "mc_eid",
        "msclkid",
        "ttclid",
        "twclid",
        "wbraid",
        "yclid",
        "gclsrc",
        "vero_id",
        "wickedid",
        "oly_anon_id",
        "oly_enc_id",
        "s_kwcid",
        "mkt_tok",
    }
)

# These verbs can change the document represented by the current URL.  A cached
# read of that document must not survive them. Navigation is handled separately
# because it invalidates the destination, not necessarily the page being left.
CONTENT_MUTATING_ACTIONS = frozenset(
    {"click", "type", "press", "scroll", "select", "wait_for"}
)
NAVIGATION_ACTIONS = frozenset({"goto", "back"})


def canonical_page_url(url: str) -> str:
    """Return the conservative identity used only for one run's read cache.

    We intentionally do *not* drop generic parameters such as ``source``,
    ``ref`` or ``page``. They are frequently functional. Likewise fragments are
    preserved because hash-routed web applications may render entirely
    different screens at the same path.
    """

    raw = str(url or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return raw

    # Relative/data/about URLs have no normal network host. Preserve them
    # byte-for-byte except for the scheme so the cache cannot over-collapse.
    if not parsed.netloc:
        return urlunsplit(
            (parsed.scheme.lower(), parsed.netloc, parsed.path, parsed.query, parsed.fragment)
        )

    netloc = parsed.netloc
    if "@" in netloc:
        userinfo, host_port = netloc.rsplit("@", 1)
        netloc = f"{userinfo}@{host_port.lower()}"
    else:
        netloc = netloc.lower()

    kept: list[str] = []
    for part in parsed.query.split("&") if parsed.query else ():
        encoded_key = part.partition("=")[0]
        key = unquote_plus(encoded_key).strip().casefold()
        if key in TRACKING_PARAMETER_NAMES:
            continue
        if any(key.startswith(prefix) for prefix in TRACKING_PARAMETER_PREFIXES):
            continue
        kept.append(part)

    return urlunsplit(
        (
            parsed.scheme.lower(),
            netloc,
            parsed.path,
            "&".join(kept),
            parsed.fragment,
        )
    )
