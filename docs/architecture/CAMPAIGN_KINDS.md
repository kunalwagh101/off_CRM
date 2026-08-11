# Campaign kinds

`campaigns` has a `kind` column. Email is one kind; more are coming
(`CAMPAIGN_TYPES.md`). The registry is `offsetx_apollo_builder/campaigns.py`.

```
offsetx-outreach campaign-kinds                  # what exists, and what can run
offsetx-outreach create-campaign "Q3" --kind email
offsetx-outreach list-campaigns --kind email
GET  /api/v1/campaign-kinds
POST /api/v1/campaigns  {"name": "...", "kind": "email"}
```

---

## The migration is the easy half

`ALTER TABLE campaigns ADD COLUMN kind TEXT NOT NULL DEFAULT 'email'` cannot
really go wrong. Every row written before the column existed **was** an email
campaign, because nothing else existed, so the column default backfills them
correctly and there is no data migration to get wrong.

The hard half is everything written back when email was the only possibility.
`run_due`, `generate_drafts`, `sync_replies` and the rest all assume the row
they were handed is mail. **The day an image campaign exists, the email sender
would pick it up and try to post a picture to an SMTP server.**

So the column arrives with a gate, not on its own.

---

## Three kinds, one of which works

| Kind | Sends | Runs? |
|---|---|---|
| `email` | an email | ✅ `outreach.engine.OutreachEngine` |
| `image` | a picture or a video | ❌ declared, not built |
| `distribution` | a post | ❌ declared, not built |

**Why declare kinds that do not work?** Because the failure mode of adding a
`kind` column early is a database full of campaigns no runner will ever pick up
— rows that look alive in a list, take contacts, and simply never send, for as
long as it takes someone to wonder why.

A declared kind refuses at creation, with what is missing:

```
$ offsetx-outreach create-campaign "Reels" --kind image
Image and video campaigns are declared but not implemented yet. Still missing:
a runner, a generator pool, the swipe approval surface, and the quality gates.
The AI layer's tiers, verify loop, eval harness and traffic shifting already
transfer; the campaign runner does not. Creating one now would put a row in the
database that nothing will ever run.
```

Leaving them out until they work would lose the thing worth having, which is
that `kind` means something checkable from the day it exists. A test asserts
every unimplemented kind carries a `missing` sentence — *"not implemented"*
without a next step is a shrug rather than an answer.

The UI shows them for the same reason. A picker that hides them looks like the
feature was never planned; one that shows them with the reason says where the
product is going. Select an unbuilt kind and the email-shaped fields disappear,
the reason appears, and the submit button is disabled.

---

## Absent means email; wrong means stop

The asymmetry in `coerce_kind` is deliberate:

| Value | Read as | Why |
|---|---|---|
| missing / `None` / `""` | `email` | Written before the column existed, when email was all there was |
| `"image"` | `image` | Declared kind |
| `"from_the_future"` | **raises** | Corruption, or a database written by a newer version |

Falling back to `email` on an unrecognised value would be the friendlier-looking
choice and the dangerous one: it would hand an unknown campaign to the mail
sender. Default-deny, same as the provider registry refusing an unlisted
provider.

---

## The gate

`OutreachEngine._require_own_kind` loads the campaign and refuses it if another
kind owns it. Every entry point that acts on one campaign calls it:

`import_contacts`, `generate_drafts`, `edit_draft`, `bulk_replace_drafts`,
`schedule_drafts`, `approve_drafts`, `sync_replies`, `run_due`, `export_crm`.

Two tests keep that list honest:

- one asserts each of those methods contains the check;
- one walks every public method on `OutreachEngine`, finds the ones taking a
  `campaign_id`, and **fails if any is not in the list**. Without the second,
  the first quietly stops being exhaustive the day someone adds a method.

`run_due` is checked *before* it syncs replies. A refusal that happens after the
mail provider has been called has already done the thing it was meant to
prevent, so there is a test whose mail provider raises if it is touched at all.

The error names both sides and says nothing happened:

> Campaign `'c1'` is a Image and video campaign, and sending is the Email
> outreach runner. Nothing was done.

---

## Kind is fixed at creation

`update_campaign` **refuses** a `kind` change rather than dropping it through
the allowlist. Contacts, drafts and messages were all created under the
original kind; converting in place would leave email drafts attached to an image
campaign. Create a new campaign instead.

---

## The settings blob, deliberately not built

`CAMPAIGN_TYPES.md` proposed `kind` plus a per-kind settings blob. Only the
column is here.

Email's settings live in real columns that are validated and indexed, and no
other kind can be created yet — so a `settings_json` today would be an
unvalidated blob with **no writer**: a dumping ground waiting for whoever needs
a field in a hurry.

Adding a column to SQLite is additive and costs exactly the same later as now.
The *validator* is the part that has to exist before the blob does, and it
cannot be written until there is a kind whose settings are known.

---

## Notes for whoever builds the second kind

- `kind` is on the row, and `assert_kind` is the check. Give the new runner its
  own `CAMPAIGN_KIND` and its own `_require_own_kind`, and its entry points go
  in that runner's exhaustiveness test.
- Flip `implemented=True` and fill `runner` in the registry. The refusal, the
  API, the CLI and the picker all follow from that one field.
- The email-shaped columns stay at their defaults. `uses_email_columns=False`
  is what tells the UI not to ask for a send window.
- Add `settings_json` **with its validator**, not before.
- `campaigns.py` sits at the package root, not inside `outreach/`, on purpose:
  the registry is above the email runner, not part of it.
