# The AI module

How off_CRM talks to AI providers, and why no provider can reach your mailbox.

This is the practical guide. `BUILD_STATE.md` is the working record of what is
built and what is not.

---

## The one rule

**Models never pull. off_CRM pushes.**

No AI provider gets a credential, a tool, a connector, a database handle, a
retrieval interface, or any query path into your mailbox, your CRM, or your
notes. A model receives a constructed payload and returns text. That is the only
channel that exists.

A model that can *ask* for data has access. A model that can only *receive* a
payload does not.

---

## Trust tiers

Every provider sits in a tier, decided by **two** things: which country it is
under, and what its data-retention terms say. Passing one is not enough.

| Tier | Who | Example | May receive |
|---|---|---|---|
| **A** Highest trust | Europe, or running on your own machine | Mistral, local Ollama | Public content, a person's public details, your templates and drafts, CRM notes |
| **B** Default trust | USA, Canada, allied | OpenAI, Anthropic, Groq | Public content, a person's public details, your templates |
| **C** Restricted | China, and anything demoted for weak terms | DeepSeek, Kimi, Qwen, GLM, Google free tier | Public content, a person's public name/company/title |
| **D** Blocked | Routers and aggregators, anything unlisted | OpenRouter, Together | Nothing |

**Why Google is in C:** its free tier's terms allow submitted content to be used
to improve Google products. Good country, weak terms — so it drops a tier. Move
to paid billing, re-read the terms, then pin `trust_tier: B` in the config with
a note.

**Why aggregators are in D:** they route to a third party that changes per model
and per day. The company actually processing your data is not knowable in
advance, so nothing is sent.

**Chinese models are useful here, not banned.** At tier C, DeepSeek and Kimi can
personalise from a person's public profile and do coding and research work. They
do not get your email address, your template, your notes or your mailbox.

**Want a Chinese model with your private data?** Run the weights yourself.
DeepSeek is openly licensed. Self-hosted sits at tier A because nothing leaves
the machine.

---

## Data policies

The tier sets a ceiling. You pick the level under it.

| Policy | What actually leaves |
|---|---|
| `strict` | Category and question structure. Nobody is identifiable. |
| `minimal` | The person's public name, company, title and public hook, plus your one-line positioning. Email addresses become `<RECIPIENT_1>`. |
| `standard` | The above, plus your template text and campaign notes. Addresses still tokenised. |
| `full` | No field restrictions. Real addresses can leave. |

Defaults: tier A and B start at `standard`, tier C at `minimal`, tier D at
`strict`.

### Using `full` on a restricted provider

You can. It is deliberate, not silent:

1. Connectors → the provider card → **Allow anyway…**
2. Type why. A reason is required.
3. The decision is stored with who made it and when, and shown on the card.

Three things stay blocked at **every** level, including `full`: credentials,
mail headers, and off_CRM's internal field names. Those are never legitimate
outbound content.

---

## Mailbox

Blocked for every provider, in every country, by default.

To unlock it for a workspace, type exactly:

```
ALLOW MAILBOX CONTENT TO LEAVE
```

Even unlocked, tier C and D are still refused. Unlocking mailbox egress does not
flatten the tiers underneath it.

---

## Adding a provider

Edit `config/providers.yaml`. Never Python, never TypeScript.

```yaml
  - id: my_provider
    name: My Provider
    jurisdiction: DE          # ISO-3166 alpha-2, or XX for routers
    adapter: openai_compatible
    base_url: https://api.example.com/v1
    default_model: my-model-large
    models:
      - id: my-model-large
        context_window: 128000
        cost_per_1m_input_usd: 1.00
        cost_per_1m_output_usd: 3.00
        good_at: [writing, reasoning]
    trains_on_input: false
    retention: Does not train on API inputs. EU hosted.
    key_url: https://example.com/keys
    verified_on: 2026-07-25
```

`jurisdiction` and `retention` are required. An entry missing either is
rejected at load — unknown terms cannot be treated as safe.

The tier is derived. To pin one, add `trust_tier: B` and say why in a comment.

**About `verified_on`:** public "free LLM API" lists go stale fast. That date
records when a human last read the provider's own policy page. Re-check in the
provider's console before relying on a limit.

---

## How a call is made

1. **Tier filter.** Providers not permitted to hold this data class are removed.
   This runs first. Cost never overrides it.
2. **Quota filter.** Providers with nothing left today are skipped, not called.
3. **Payload construction.** Built from an empty dict, adding only what the
   policy permits. Never a copy of an internal object with fields deleted — a
   field you forget to delete is a leak.
4. **Pre-flight scan.** A hit **blocks the call and raises**. It does not redact.
   Under allowlist construction, forbidden content means the builder has a bug,
   and quietly cleaning it would hide that bug forever.
5. **Call.**
6. **Log.** Provider, tier, task, exact payload, timestamp.

Failover walks the remaining candidates **within the same tier only**. A task
carrying restricted data fails closed rather than dropping to a lower tier.

---

## Checking it yourself

The point of the egress log is that you do not have to take any of this on
trust.

**What was sent** in the sidebar → any row → **Inspect**. The payload shown is
byte-for-byte what left the machine.

Blocked calls are listed too, with what was found and where.

In code:

```bash
python -m pytest tests/test_ai_egress_wall.py -v
```

Thirty cases covering the §5.12 acceptance requirements: private data refused on
lower tiers, addresses blocked, mailbox unreachable, no retrieval interface
exposed, failover never crossing tiers, and an AST check that no module outside
the broker can reach a provider.

---

## For developers

Every outbound call goes through the broker. There is no second path, and
`tests/test_ai_egress_wall.py` fails the build if one appears.

```python
from offsetx_apollo_builder.ai import (
    DataClass, EgressRequest, PersonPublic,
)

request = EgressRequest(
    task_type="draft_email",
    data_class=DataClass.PERSON_PUBLIC,
    person=PersonPublic.from_contact(contact_row),
    positioning_line=settings.positioning_line,
    template_text=template.body,
)
result = broker.call(request, settings, system_prompt=SYSTEM, expect_json=True)
```

`PersonPublic` has no email field. That is not an oversight — it means an
address cannot reach a payload through the person path even by mistake.

To offer a new field to models, add it to `EgressRequest` **and** to
`build_payload` under the right policy level. If you only do the first, it never
leaves. That is the intended failure mode.

### Errors you should handle

| Exception | HTTP | Meaning |
|---|---|---|
| `PolicyViolation` | 403 | The tier rules forbid this, before any call |
| `EgressBlocked` | 422 | The scanner found something. Nothing was sent. |
| `NoPermittedProvider` | 409 | Nobody eligible — none connected, all out of quota, or all wrong tier |
| `RegistryError` | 400 | Config problem, or an unlisted provider |

Each carries `.to_dict()` with structured detail, so the UI can explain the
refusal instead of showing a status code.
