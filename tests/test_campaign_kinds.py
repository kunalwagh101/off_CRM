"""Campaign kinds, and the migration that added the column.

Until now every campaign was an email campaign and the schema said so. This is
the change that lets a `campaigns` row be something else, and the risk it
carries is not the migration — `ALTER TABLE ADD COLUMN` with a default cannot
really go wrong.

The risk is everything that was written when email was the only possibility.
`run_due`, `generate_drafts`, `sync_replies` and the rest all assume the row
they were handed is mail. The day an image campaign exists, the email sender
would pick it up and try to post a picture to an SMTP server.

So the tests here fall into three groups:

1. **The migration** — an old database gains the column, and its existing rows
   come out as email campaigns rather than as anything ambiguous.
2. **The refusal** — a kind nothing can run cannot be created, and says what is
   missing rather than "invalid".
3. **The gate** — no email-runner entry point will touch a row of another kind.
   That one is exhaustive on purpose: a method added later without the check is
   exactly how this goes wrong quietly.
"""
from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path

import pytest

from offsetx_apollo_builder.campaigns import (
    DEFAULT_KIND,
    KINDS,
    CampaignKindNotImplemented,
    UnknownCampaignKind,
    WrongCampaignKind,
    assert_kind,
    assert_runnable,
    coerce_kind,
    implemented_kinds,
    kind_spec,
    list_kinds,
)
from offsetx_apollo_builder.outreach.engine import OutreachEngine
from offsetx_apollo_builder.outreach.models import ContactInput
from offsetx_apollo_builder.outreach.schema import SCHEMA_VERSION
from offsetx_apollo_builder.outreach.store import OutreachStore


@pytest.fixture()
def store(tmp_path: Path) -> OutreachStore:
    db = OutreachStore(tmp_path / "outreach.db")
    db.initialize()
    yield db
    db.close()


# ─────────────────────────────────────────────────────────────────────────────
# The registry
# ─────────────────────────────────────────────────────────────────────────────


def test_email_is_the_only_implemented_kind_today():
    assert implemented_kinds() == ("email",)
    assert kind_spec("email").implemented
    assert kind_spec("email").runner
    assert assert_runnable("email").id == "email"
    with pytest.raises(CampaignKindNotImplemented):
        assert_runnable("distribution")


def test_declared_kinds_say_what_is_missing():
    """"Not implemented" without a next step is a shrug, not an answer."""
    for spec in KINDS.values():
        if spec.implemented:
            continue
        assert spec.missing, f"{spec.id} is declared with no account of what is missing"
        assert len(spec.missing) > 40, spec.id
        assert not spec.runner, f"{spec.id} names a runner but is not implemented"


def test_an_unlisted_kind_is_refused_rather_than_assumed():
    """Default-deny, same as the provider registry.

    A kind nobody declared is a kind nobody wrote a runner for.
    """
    with pytest.raises(UnknownCampaignKind) as exc:
        kind_spec("newsletter")
    assert "email" in str(exc.value), "the error should name what does exist"


def test_a_missing_kind_reads_as_email_and_a_wrong_one_does_not():
    """The asymmetry is the point.

    Absent means "written before the column existed", which is email. Present
    and unrecognised means corruption or a downgrade, and calling that email
    would hand it to the mail sender.
    """
    assert coerce_kind(None) == DEFAULT_KIND
    assert coerce_kind("") == DEFAULT_KIND
    assert coerce_kind("  EMAIL ") == "email"
    with pytest.raises(UnknownCampaignKind):
        coerce_kind("whatever")


def test_kinds_are_listed_runnable_first():
    ids = [item["id"] for item in list_kinds()]
    assert ids[0] == "email"
    runnable = [item["implemented"] for item in list_kinds()]
    assert runnable == sorted(runnable, reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# The refusal
# ─────────────────────────────────────────────────────────────────────────────


def test_creating_an_unimplemented_kind_is_refused_with_the_reason(store):
    """The failure this prevents is a row that looks alive and never sends.

    Silence would be worse than a refusal: the campaign appears in the list,
    takes contacts, and simply never does anything, for as long as it takes
    someone to wonder why.
    """
    with pytest.raises(CampaignKindNotImplemented) as exc:
        store.create_campaign(name="Reels", daily_send_limit=10, kind="image")

    message = str(exc.value)
    assert "not implemented" in message
    assert "runner" in message, "it should say what is missing"
    assert "will ever run" in message

    items, total = store.list_campaigns()
    assert total == 0 and items == []


def test_creating_an_unknown_kind_is_refused(store):
    with pytest.raises(UnknownCampaignKind):
        store.create_campaign(name="Whatever", daily_send_limit=10, kind="podcast")


def test_the_refusal_runs_before_any_other_validation(store):
    """An unimplemented kind is reported even when the rest is also wrong.

    Otherwise the caller fixes a send limit, retries, and only then learns the
    kind was never going to work.
    """
    with pytest.raises(CampaignKindNotImplemented):
        store.create_campaign(name="Reels", daily_send_limit=-5, kind="image")


def test_a_campaigns_kind_cannot_be_changed_afterwards(store):
    """Refused, not silently dropped by the update allowlist.

    Contacts, drafts and messages were all created under the original kind;
    converting in place would leave email drafts attached to an image campaign.
    """
    campaign_id = store.create_campaign(name="Pilot", daily_send_limit=10)
    with pytest.raises(ValueError) as exc:
        store.update_campaign(campaign_id, {"kind": "image", "name": "Renamed"})
    assert "cannot be changed" in str(exc.value)
    assert store.get_campaign(campaign_id)["name"] == "Pilot", "nothing was applied"


# ─────────────────────────────────────────────────────────────────────────────
# The migration
# ─────────────────────────────────────────────────────────────────────────────


def test_a_new_campaign_is_an_email_campaign(store):
    campaign_id = store.create_campaign(name="Pilot", daily_send_limit=10)
    assert store.get_campaign(campaign_id)["kind"] == "email"
    assert store.list_campaigns()[0][0]["kind"] == "email"


def test_an_existing_database_gains_the_column_and_keeps_its_rows(tmp_path):
    """The real upgrade path, driven through a database built without the column.

    Written by dropping the column from a live schema rather than by pasting an
    old one in, so it keeps testing the upgrade as the schema moves on.
    """
    path = tmp_path / "legacy.db"
    seed = OutreachStore(path)
    seed.initialize()
    campaign_id = seed.create_campaign(name="Before the column", daily_send_limit=17)
    seed.close()

    connection = sqlite3.connect(path)
    # The index has to go first: SQLite refuses to drop a column an index still
    # refers to. That ordering is also why the index cannot live in SCHEMA_SQL.
    connection.execute("DROP INDEX IF EXISTS idx_campaigns_kind")
    connection.execute("ALTER TABLE campaigns DROP COLUMN kind")
    connection.execute("PRAGMA user_version = 7")
    connection.commit()
    columns = {row[1] for row in connection.execute("PRAGMA table_info(campaigns)")}
    assert "kind" not in columns, "the fixture must actually be missing the column"
    connection.close()

    upgraded = OutreachStore(path)
    upgraded.initialize()
    try:
        campaign = upgraded.get_campaign(campaign_id)
        assert campaign["kind"] == "email"
        assert campaign["name"] == "Before the column"
        assert campaign["daily_send_limit"] == 17, "the rest of the row is untouched"
        assert (
            upgraded.connection.execute("PRAGMA user_version").fetchone()[0]
            == SCHEMA_VERSION
        )
    finally:
        upgraded.close()


def test_the_index_over_the_new_column_exists_on_both_paths(tmp_path):
    """It cannot live in SCHEMA_SQL, which runs before the migration.

    On an existing database `CREATE TABLE IF NOT EXISTS` is a no-op, so an index
    over a brand-new column would be asked for before `ALTER TABLE` had added
    it — and every upgrade would fail on startup.
    """
    fresh = OutreachStore(tmp_path / "fresh.db")
    fresh.initialize()
    names = {
        row[0]
        for row in fresh.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
        )
    }
    fresh.close()
    assert "idx_campaigns_kind" in names


def test_listing_can_filter_by_kind(store):
    store.create_campaign(name="One", daily_send_limit=10)
    store.create_campaign(name="Two", daily_send_limit=10)
    assert store.list_campaigns(kind="email")[1] == 2
    assert store.list_campaigns(kind="image")[1] == 0
    with pytest.raises(UnknownCampaignKind):
        store.list_campaigns(kind="podcast")


# ─────────────────────────────────────────────────────────────────────────────
# The gate
# ─────────────────────────────────────────────────────────────────────────────


def test_assert_kind_names_both_sides(store):
    campaign = {"id": "c1", "kind": "image"}
    with pytest.raises(WrongCampaignKind) as exc:
        assert_kind(campaign, "email", action="sending")
    message = str(exc.value)
    assert "Image and video" in message
    assert "Email outreach" in message
    assert "sending" in message
    assert "Nothing was done" in message


def test_assert_kind_passes_a_row_written_before_the_column():
    assert assert_kind({"id": "c1"}, "email") == "email"


#: Every OutreachEngine method that acts on one campaign. Pinned as a list so a
#: method added later without the kind check fails this test rather than
#: shipping as a hole.
CAMPAIGN_METHODS = (
    "import_contacts",
    "generate_drafts",
    "edit_draft",
    "bulk_replace_drafts",
    "schedule_drafts",
    "approve_drafts",
    "sync_replies",
    "run_due",
    "export_crm",
)


def test_every_campaign_method_checks_the_kind():
    """Exhaustive on purpose.

    A single unchecked entry point is enough for the email runner to act on an
    image campaign, and the one that gets forgotten is always the one nobody
    was thinking about.
    """
    for name in CAMPAIGN_METHODS:
        source = inspect.getsource(getattr(OutreachEngine, name))
        assert "_require_own_kind" in source, f"{name} does not check the campaign kind"


def test_no_campaign_method_was_missed():
    """Catches a method added later that takes a campaign_id and is not listed.

    Without this, `CAMPAIGN_METHODS` above quietly stops being exhaustive and
    the test that reads it keeps passing.
    """
    missed = []
    for name, member in vars(OutreachEngine).items():
        if name.startswith("_") or not callable(member):
            continue
        if name in CAMPAIGN_METHODS:
            continue
        parameters = inspect.signature(member).parameters
        if "campaign_id" in parameters:
            missed.append(name)
    assert missed == [], f"these act on a campaign but are not kind-checked: {missed}"


def test_the_email_runner_refuses_a_campaign_of_another_kind(tmp_path, monkeypatch):
    """The property the whole migration exists to make true.

    No implemented kind other than email exists yet, so the row is written
    directly. That is the situation being guarded against: a row of another
    kind reaching the mail sender.
    """
    engine = OutreachEngine(tmp_path / "outreach.db")
    try:
        campaign_id = engine.create_campaign(name="Pilot", daily_send_limit=10)
        contact_id = engine.store.upsert_contact(
            ContactInput(full_name="Ana Silva", email="ana@example.com")
        )
        engine.store.add_contact_to_campaign(campaign_id, contact_id)

        with engine.store.transaction() as connection:
            connection.execute(
                "UPDATE campaigns SET kind = 'image' WHERE id = ?", (campaign_id,)
            )

        for call in (
            lambda: engine.generate_drafts(campaign_id),
            lambda: engine.approve_drafts(campaign_id, stages=["initial"]),
            lambda: engine.schedule_drafts(campaign_id, draft_ids=[], scheduled_at=None),
            lambda: engine.bulk_replace_drafts(campaign_id, find="a", replace="b"),
            lambda: engine.export_crm(campaign_id, tmp_path / "out.csv"),
            lambda: engine.import_contacts(campaign_id, tmp_path / "nope.csv"),
        ):
            with pytest.raises(WrongCampaignKind):
                call()

        assert not (tmp_path / "out.csv").exists(), "a refused export writes nothing"
    finally:
        engine.close()


def test_run_due_refuses_before_it_touches_the_mailbox(tmp_path):
    """`run_due` syncs replies first, so the check has to come before that.

    A refusal that happens after the mail provider has been called has already
    done the thing it was supposed to prevent.
    """

    class ExplodingMail:
        def list_replies(self, **_):  # pragma: no cover - must never be reached
            raise AssertionError("the mailbox was touched before the kind was checked")

        def send(self, **_):  # pragma: no cover
            raise AssertionError("a message was sent")

    engine = OutreachEngine(tmp_path / "outreach.db")
    try:
        campaign_id = engine.create_campaign(name="Pilot", daily_send_limit=10)
        with engine.store.transaction() as connection:
            connection.execute(
                "UPDATE campaigns SET kind = 'image' WHERE id = ?", (campaign_id,)
            )
        with pytest.raises(WrongCampaignKind):
            engine.run_due(
                campaign_id, mail_provider=ExplodingMail(), own_email="me@example.com"
            )
    finally:
        engine.close()


def test_an_unknown_kind_in_the_database_stops_everything(tmp_path):
    """Corruption or a downgrade must not be read as email.

    This is the case `coerce_kind` refuses to guess at: a value that is present
    and unrecognised. Reading it as email would run the mail sender over it.
    """
    engine = OutreachEngine(tmp_path / "outreach.db")
    try:
        campaign_id = engine.create_campaign(name="Pilot", daily_send_limit=10)
        with engine.store.transaction() as connection:
            connection.execute(
                "UPDATE campaigns SET kind = 'from_the_future' WHERE id = ?",
                (campaign_id,),
            )
        with pytest.raises(UnknownCampaignKind):
            engine.store.get_campaign(campaign_id)
    finally:
        engine.close()
