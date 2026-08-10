# Notebook export (§4G)

You point a research notebook at what a campaign learned, and ask it questions.
This is how the sources get built.

---

## The honest version first

**NotebookLM has no public write API.** No endpoint, no token, no integration to
authorise. Anything that claims to "connect your notebook" is driving a
logged-in browser session, and that breaks the week Google moves a button.

So off_CRM produces a **bundle**: a folder of Markdown files you upload once, by
hand. Smaller than "connect your notebook", and it actually works. The same
bundle uploads to a Claude Project, a ChatGPT Project, Gemini, or a notebook you
host yourself — nothing in it is NotebookLM-shaped.

---

## The thing that makes it more than a file writer

The rule this system runs on is *models never pull, off_CRM pushes*.

**An export you drag into NotebookLM is a push.** The only difference from an
API call is that the transport is a person. The rules do not care about
transport.

So the bundle is built like a payload:

| Payload rule | How the export follows it |
|---|---|
| Built from an allowlist, starting empty | Sections are declared with the data class they carry. Nothing is copied out of the database and trimmed. |
| Resolved against a trust tier | The **destination** is a tier. NotebookLM's free tier is Google, and Google sits at C because its free-tier terms permit training on submitted content. |
| Scanned before it leaves | The same `ai/scanner.py` the broker uses. A hit blocks the whole export and raises. |
| Blocks, never redacts | A finding means the builder has a bug. Cleaning it silently would hide the bug forever. |
| Nothing silently absent | Every withheld section is listed with its reason and its fix, in the README and the manifest. |

---

## What that means in practice

Run `plan` before `export`. It writes nothing and tells you the answer:

```
$ offsetx-notebook plan --campaign <id> --target notebooklm

Tier     : C — Restricted
Policy   : pseudonymous

Included:
  00-overview.md   Overview         public
  10-audience.md   Audience shape   public
  20-people.md     People           person_public

Held back:
  Outcomes by variant: A tier C destination does not receive:
    Template text and campaign drafts.
  Templates:           (same)
  Notes you approved:  A tier C destination does not receive:
    CRM records and internal notes.
```

That is not a bug and it is not conservatism for its own sake. Your template copy
and your reply rates are the business secret. Uploading them to a free tier whose
terms permit training on them is exactly the thing the trust tiers exist to
prevent, and the export refuses on the same grounds the broker would.

**What you do get at tier C is genuinely useful**: the audience shape, and every
person's title, category, route and public hook — with names and companies as
tokens. That is a real research corpus. It is just not your playbook.

To get the playbook in, use a destination you actually trust:

```
$ offsetx-notebook export --campaign <id> --target self_hosted --out ./aug
```

or raise a destination's tier with a written reason:

```
$ offsetx-notebook export --campaign <id> --target notebooklm \
    --tier B --reason "Paid workspace agreement, training excluded, checked 2026-08" \
    --out ./aug
```

Lowering a tier needs no reason. Raising one does — an unexplained override is
indistinguishable from a mistake six months later.

---

## Destinations

| id | Tier | Policy | Why |
|---|---|---|---|
| `notebooklm` | C | pseudonymous | Google, free tier, terms permit training on submitted content. Acceptable jurisdiction, unacceptable data terms — the same demotion the provider registry applies. |
| `hosted_notebook` | B | standard | A paid tier whose terms you have read and which excludes training. off_CRM cannot verify your agreement, so this is your assertion, recorded as one. |
| `self_hosted` | A | full | Files stay on hardware you control. |

---

## Sections

Each file declares what it carries. The tier decides which survive.

| File | Section | Data class | Needs policy | Kinds |
|---|---|---|---|---|
| `00-overview.md` | Overview | public | strict | all |
| `10-audience.md` | Audience shape | public | strict | all |
| `20-people.md` | People | person_public | pseudonymous | all |
| `30-outcomes.md` | Outcomes by variant | campaign | pseudonymous | email |
| `40-what-worked.md` | What worked | campaign | pseudonymous | all |
| `50-templates.md` | Templates | campaign | standard | email |
| `60-notes.md` | Notes you approved | internal | standard | all |

Plus `README.md` (what is in it, what was held back, why) and `MANIFEST.json` (a
sha256 of every file, so you can prove the upload is what was built).

A withheld section costs nothing to withhold: its data is never fetched. A tier C
export does not load the template bodies into memory before deciding not to send
them.

---

## Never exported, at any tier, with any override

These are not policy questions. There is no flag.

| What | Why |
|---|---|
| **Reply text and any received mail** | Mailbox content is the one class no destination carries. Replies are counted so the numbers are right; the words are not written. The way to send mailbox content to a *provider* is the unlock phrase in `ai/tiers.py`, and a folder on disk is not a provider you can unlock. |
| **Email addresses** | A research notebook has no use for them, and a folder of addresses is the worst single artefact this system could produce. Tokenised out at every level including `full`. |
| **Credentials, provider keys, mail headers** | Blocked by the same scanner the broker uses. |
| **Deal values, commission, pipeline stages** | Internal revenue fields. The scanner refuses them by name. |

The mailbox guarantee is **structural, not a runtime check**. No section carries
the mailbox class, and a test pins the exact set of store methods this module may
call — `sent_messages`, `last_outgoing` and `record_reply` are not in it. Adding
one is a decision someone has to make on purpose, in a diff.

---

## Tokens, and the file that reverses them

Below `minimal` policy, people and companies become `PERSON_1` / `COMPANY_1`,
numbered **per bundle**.

Per bundle matters. One shared `PERSON_1` across two hundred people is not an
anonymised list — it is a list with the answers removed, and a notebook can say
nothing about it. The numbering means nothing between exports: `PERSON_3` in
Tuesday's bundle and `PERSON_3` in Friday's are not the same person.

Scrubbing runs on free text too, not just name fields. *"Ana Silva spoke at the
EU trade summit"* is the shape that defeats field-level minimisation, so the
public hook goes through `payload.scrub_identity` and comes out as *"PERSON_1
spoke at the EU trade summit"* — the useful part intact, the identity gone.

The campaign's **own name** is withheld below `minimal` too. "Q3 Nordic fintech
founders" is the ideal customer profile written out; it says more about the
business than the contact list does.

The map back to real people is written **outside the bundle folder**:

```
aug-export/
├── bundle/              ← upload this
│   ├── 00-overview.md
│   ├── …
│   ├── README.md
│   └── MANIFEST.json
└── identity-key.json    ← 0600, never upload
```

Not a warning inside the folder. Outside it, because "select all and upload" is
what people actually do.

---

## Not email-shaped

Per `CAMPAIGN_TYPES.md`: email is one campaign kind and more are coming.

Sections declare the kinds they apply to. `30-outcomes.md` and `50-templates.md`
are email-only; everything else is universal. An image or distribution campaign
gets the universal sections and a **stated reason** for the rest — and the reason
says *kind*, not *tier*:

> This section only applies to email campaigns, and this campaign is image.

Kind is checked before tier deliberately. Told "not trusted enough", an owner
goes looking for a permission problem that does not exist.

`campaigns` has no `kind` column yet, so `campaign_kind()` reads one and falls
back to `email`. When the column lands, this module does not change. A test
asserts the column is still absent, so the day it appears the test fails and
points at the reader that needs checking.

---

## Also not exported: anything a model wrote about your data

No AI model is involved in producing a bundle. It is read from your own database
and formatted. If a model ever summarised a section, the bundle would become a
provider call wearing a file's clothes and the tier gate would be measuring the
wrong thing — so an AST test fails the build if this module gains a route to a
transport.

---

## What is not built

- **No API endpoint and no UI screen.** CLI only, same as the tool registry.
- The web shape has a real design problem worth solving before it is built: a
  browser download of the bundle as a zip would put the identity key back inside
  the thing the owner uploads, which is exactly the failure the directory layout
  prevents. Two separate downloads is probably the answer, and it needs deciding
  rather than defaulting.
- **No scheduled re-export.** Manual command only.
- **Nothing reads the bundle back.** It is written for a notebook, not for
  off_CRM.
