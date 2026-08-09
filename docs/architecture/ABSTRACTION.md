# Abstraction: hiding the shape, not just the names

Tokenisation answers *"who is this about"*. This answers a question no PII
scrubber asks:

> **What does this request reveal about how the business works?**

---

## The leak

Take a payload with every identifier already removed:

> "Third follow-up to a CTO at a **180-person Series B fintech** in Berlin who
> **opened twice** and never replied. **ICP: Series B fintechs, 100-250 staff.**
> Our **margin is 40%** and we close **1 in 8**."

Zero personal data. A scrubber passes it clean. And it hands over:

| Leaked | What it is |
|---|---|
| 180-person | company-size band → ICP |
| Series B | funding stage → ICP |
| 100-250 staff | your stated target band |
| **40%** | **gross margin** |
| **1 in 8** | **close rate** |
| Third follow-up | how many touches your sequence runs |
| opened twice | what your CRM tracks |

That is most of a go-to-market strategy, handed to whichever provider happened to
be cheapest.

**This was verified against the real payload builder before the fix** — every
one of those strings travelled verbatim to a tier B provider.

---

## Two operations, not one

| Operation | Removes | Protects | Status |
|---|---|---|---|
| Tokenisation | names, addresses, companies | **identity** | built earlier |
| **Abstraction** | the situation's specifics | **strategy** | this |

Neither substitutes for the other. A test asserts both run:

```python
assert "Ana Silva"  not in text   # tokenisation
assert "PERSON_1"       in text
assert "180-person" not in text   # abstraction
assert "Series B"   not in text
```

---

## Rules, not a model

Deterministic, for the same reason policy is code: **a protection that varies is
not a protection.** Same input, same output, forever.

Config-driven in `config/abstraction.yaml`, like `providers.yaml` and
`evals.yaml`. Three rule kinds:

| Kind | Does |
|---|---|
| `bucket_number` | match a number, replace with a band ("180-person" → "a mid-size company") |
| `replace_pattern` | regex → fixed replacement |
| `replace_terms` | literal terms → fixed replacement |

**Every rule only ever widens.** There is deliberately no rule that can make text
more revealing — which is why running it twice is safe, and there is a test
asserting idempotence.

---

## Applied where

- **`full` policy** — verbatim. The owner has explicitly trusted one provider
  with everything, and widening there would only degrade the copy.
- **Everything below `full`** — widened.
- Off per workspace via `abstract_business_shape`, which **defaults to on**, so a
  caller that forgets the argument gets protection rather than a leak.

Applied to `instructions`, `campaign_notes`, `public_context` and `conversation`
— campaign notes most of all, since an ICP line and a margin routinely share a
sentence.

---

## Three defects caught while building this

Each has a regression test.

**1. The margin was leaking.** The percentage rule ended in `\b`. Since `%` is
not a word character, a boundary after it **can never match**:

```python
re.compile(r"\b\d{1,3}\s?%\b").search("margin is 40% and")   # → None
re.compile(r"\b\d{1,3}\s?%" ).search("margin is 40% and")    # → matches
```

The single most commercially sensitive number in a payload passed straight
through the rule written to catch it.

**2. A rule was lying.** `first|second|third… follow-up` → "a later message in
the sequence" turned *"write a warm **first** email"* into *"write a warm **a
later message in the sequence**"* — which **inverts the meaning**.

Caught by an existing test failing. The fix is also more correct: `first` is now
left alone entirely, because **every sequence has a first message, so the word
leaks nothing.** It is the high ordinals that disclose how many steps exist. Same
for `email 1` versus `email 7`.

**3. Rule order mattered and was wrong.** `headcount` was listed before
`headcount_ranges`, so it consumed the right-hand number of "100-250 staff" and
the range rule never fired. The more specific pattern must run first.

---

## Cost to quality

Near zero on ordinary work. These all pass through untouched:

```
"Write a warm intro email about customs software."
"Keep it under 120 words and end with a question."
"Mention their talk at the trade summit."
```

The rules only fire on commercial specifics, and where they fire they leave the
useful signal: *"a later message in the sequence to a CTO at a mid-size company
who engaged before"* still tells a model everything it needs to write well.

---

## Failure mode

If the rules file is missing or malformed, **the send still happens, unwidened**.
Failing to widen must not become failing to send — that is a visible gap rather
than an outage, and `load_rules` raises loudly when the owner edits the file
badly, so a broken edit is caught at load rather than in production.
