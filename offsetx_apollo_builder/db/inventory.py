"""Every store off_CRM keeps, how it keeps it today, and where `F-06.03` puts
it on the free plan (`S-06.03.01`).

On Render's free plan the data folder is wiped on every deploy and restart, so
"where does this live" decides what survives. This list is checked against the
running app rather than trusted: every service the app opens must be named here,
as a store or as keeping nothing of its own, and every file the app writes under
the data folder must belong to a store here (`tests/test_storage_inventory.py`).
The table in `docs/architecture/HOSTED_STORAGE.md` is generated from it.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path


@dataclass(frozen=True, slots=True)
class StoredThing:
    name: str
    #: What is lost if this is wiped.
    holds: str
    #: Names under the data folder; a trailing "/" is a folder, "*" a pattern.
    files: tuple[str, ...]
    #: How it is kept today, with no `OFFSETX_DATABASE_URL`.
    today: str
    #: Where it goes on the hosted topology, and which story moves it.
    hosted: str
    #: The `app.state` attribute that opens it, if one does.
    service: str = ""

    def claims(self, relative: str) -> bool:
        """Whether a path under the data folder belongs to this store."""
        top = relative.split("/", 1)[0]
        for name in self.files:
            if name.endswith("/"):
                if fnmatch(top, name[:-1]):
                    return True
            elif fnmatch(relative, name):
                return True
        return False


SQLITE = "SQLite file"
HOSTED_NOW = "follows `OFFSETX_DATABASE_URL` already"
PHASE_1 = "hosted database — `S-06.03.02`"
PHASE_2 = "hosted database — `S-06.03.03`"
LATER = "not decided — `S-06.03.06`"
FILES = "files: lost on a free-plan deploy until object storage is decided"
SETTING = "a deployment setting on a hosted install, set once"

STORES: tuple[StoredThing, ...] = (
    StoredThing(
        "Operational logs", "failure references and safe frame metadata; bounded access records",
        ("logs", "logs/"), "size-capped rotating JSON lines",
        "standard output on Render; retention is the platform's log policy",
    ),
    StoredThing(
        "AI settings and trust", "each workspace's providers, limits, trust changes and who made them",
        ("ai_workspaces.json", ".ai_workspace_write_lock.sqlite3"), "JSON file", PHASE_1, "ai_workspaces",
    ),
    StoredThing(
        "Provider keys", "every key typed in Connectors, encrypted",
        ("ai_provider_keys.enc", ".ai_master.key"), "encrypted file and its key file",
        PHASE_1 + "; the key that opens them is `OFFSETX_SECRETS_KEY`", "",
    ),
    StoredThing(
        "Spend and call counters", "how much of each daily limit is used",
        ("ai_quota.json",), "JSON file", PHASE_1, "ai_quota",
    ),
    StoredThing(
        "Workspace logins", "usernames and password hashes",
        ("workspace_auth.db*",), SQLITE, PHASE_1, "workspace_auth",
    ),
    StoredThing(
        "Egress log", "what was sent to which provider, and when",
        ("ai_egress.db*",), SQLITE, HOSTED_NOW + "; checked in `S-06.03.02`", "ai_egress_log",
    ),
    StoredThing(
        "Video timelines", "edit history, transcripts", ("video.db*",), SQLITE, HOSTED_NOW, "video_store",
    ),
    StoredThing(
        "Products and plans", "the GTM engine's products, plans and reviews",
        ("gtm.db*",), SQLITE, HOSTED_NOW, "gtm_store",
    ),
    StoredThing(
        "CRM", "campaigns, contacts, drafts, sends, replies, delivery jobs",
        ("offsetx_outreach.db*",), SQLITE + " (`OFFSETX_OUTREACH_DB`)", PHASE_2, "engine",
    ),
    StoredThing(
        "Template results", "what each template sent and how it did", ("ai_context.db*",), SQLITE, LATER, "ai_context",
    ),
    StoredThing(
        "Sent-mail recall", "the index of sent mail drafts learn from", ("ai_recall.db*",), SQLITE, LATER, "ai_recall",
    ),
    StoredThing(
        "Tools and companions", "registered tools and companion profiles", ("ai_tools.db*",), SQLITE, LATER, "ai_tools",
    ),
    StoredThing(
        "Agent routines", "routines and their runs", ("agent_routines.db*", "agent_traces/"),
        SQLITE + " and trace files", LATER, "agent_routine_store",
    ),
    StoredThing(
        "Meeting transcripts", "uploaded meetings' transcripts", ("meeting_transcripts.db*",), SQLITE, LATER,
        "meeting_store",
    ),
    StoredThing(
        "Imagery", "generated pictures' records", ("imagery.db*",), SQLITE, LATER, "image_store",
    ),
    StoredThing(
        "Posts", "scheduled and sent posts' records", ("distribution.db*",), SQLITE, LATER, "distribution_store",
    ),
    StoredThing(
        "Trends", "trend snapshots the content engine reads", ("trends.db*",), SQLITE, LATER, "trends_path",
    ),
    StoredThing(
        "Notion link", "the Notion token, encrypted, and target pages",
        ("notion_settings.json", "notion_secret.bin", "notion_key.bin"), "JSON and encrypted files", LATER, "notion",
    ),
    StoredThing(
        "Timers", "the email and content timers' settings", ("automation.json", "content_automation.json"),
        "JSON files", LATER, "automation",
    ),
    StoredThing(
        "Privacy requests", "data-subject requests and their artifacts",
        ("privacy_requests.sqlite3*", "subject_artifacts.sqlite3*"), SQLITE, LATER, "privacy",
    ),
    StoredThing(
        "Crawler", "the discovery crawler's frontier", ("crawler_frontier.sqlite3*", "crawler_runtime/"),
        SQLITE, LATER,
    ),
    StoredThing(
        "Prospecting files",
        "who was already contacted or ruled out, rejected matches, and lists waiting to be read",
        ("old_pois/", "poi_file_queue/", "offsetx_apollo_rejection_ledger.csv", "output*/"),
        "CSV files and folders", LATER,
    ),
    StoredThing(
        "Gmail link", "the Gmail sign-in token, saved again whenever it is refreshed",
        ("gmail_token.json",), "JSON file", LATER,
    ),
    StoredThing(
        "Model scores", "the eval tool's scoreboard of how each model did", ("ai_evals.db*",),
        SQLITE, "stays on disk: written by the eval tool, not the app",
    ),
    StoredThing(
        "Provider profiles (old)", "profiles saved before Connectors, and their keys",
        ("provider_profiles.json", "provider_secrets.enc", ".provider_master.key"),
        "JSON and encrypted files", "not moved: `S-06.02.35` decides whether they stay at all",
        "provider_profiles",
    ),
    StoredThing(
        "Response cache", "answers reused for fact-shaped tasks", ("ai_cache.db*",), SQLITE,
        "stays on disk: a cache, rebuilt by use", "ai_cache",
    ),
    StoredThing(
        "Media and outboxes", "picture files, rendered video, post and mail outboxes, exports",
        ("image_assets/", "video_renders/", "post_outbox/", "mail/", "exports/"), "files", FILES,
        "email_delivery",
    ),
    StoredThing(
        "Install secrets", "the session-signing secret, the local API token, the unsubscribe-link key",
        ("workspace_session_secret", "local_api_token", "email_unsubscribe.key"), "files",
        SETTING + ": `OFFSETX_SESSION_SECRET`, `OFFSETX_UNSUBSCRIBE_SECRET`",
    ),
    StoredThing(
        "Restore and lease files", "an interrupted restore's journal and the workspace lease",
        (".offsetx_restore*", ".workspace*", "previous/", "previous-database*"), "files",
        "local only: a hosted install refuses local backup",
    ),
)

#: `app.state` attributes that keep nothing of their own: they work over a store
#: listed above, or hold configuration read from the repository.
NOT_STORES: frozenset[str] = frozenset({
    "agent_routines",       # RoutineService over agent_routine_store
    "ai_broker",            # sends; records through ai_egress_log and ai_quota
    "ai_chat",              # over the CRM
    "chat_browser_runs",      # process-local running asyncio tasks; never persisted
    "chat_permission_grants",  # bounded in-memory approvals; never persisted
    "ai_registry",          # config/providers.yaml, read only
    "campaign_locks",       # in memory
    "companions",           # over ai_tools and the CRM
    "content_automation",   # its settings are content_automation.json, under "Timers"
    "discovery_fetcher_factory",
    "hosted_storage",       # the hosted database itself; what it holds is listed per store
    "meeting_transcriber",  # over meeting_store
    "recovery_gate",        # in memory
    "sales",                # over the CRM
    "settings",
    "sns_verifier",         # in memory
})


def owner_of(relative: str) -> StoredThing | None:
    """The store a path under the data folder belongs to, or None."""
    for thing in STORES:
        if thing.claims(relative):
            return thing
    return None


def markdown_table() -> str:
    """The inventory as the design document shows it."""
    lines = [
        "| Store | What is lost if it is wiped | Kept today | On the hosted topology |",
        "|---|---|---|---|",
    ]
    for thing in STORES:
        lines.append(f"| {thing.name} | {thing.holds} | {thing.today} | {thing.hosted} |")
    return "\n".join(lines)


def sizes(data_dir: Path) -> list[tuple[StoredThing, int]]:
    """Bytes each store holds under a data folder, for `offsetx-db inventory`."""
    totals = {thing.name: 0 for thing in STORES}
    if data_dir.is_dir():
        for path in data_dir.rglob("*"):
            if not path.is_file():
                continue
            thing = owner_of(path.relative_to(data_dir).as_posix())
            if thing is not None:
                totals[thing.name] += path.stat().st_size
    return [(thing, totals[thing.name]) for thing in STORES]
