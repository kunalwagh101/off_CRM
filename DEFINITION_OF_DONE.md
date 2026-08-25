# Definition of Ready · Definition of Done

Two gates. `scripts/verify_board.py` enforces what can be enforced mechanically;
the rest is a checklist that a human reviewer applies. Nothing here is advisory.

---

## Definition of Ready — to enter `READY`

An item may be pulled only when **all** of these hold:

- [ ] Acceptance criteria are written as Given/When/Then and each one is
      machine-testable. "Works well" is not an acceptance criterion.
- [ ] Every upstream dependency is `DONE`, or the dependency is named and the
      item sits in `BLOCKED` instead.
- [ ] The data and contracts it touches are known — schema, endpoint shape,
      file format. Not "we will see when we get there".
- [ ] **No open question is filed against it.** An item with an unanswered
      `Q-nn` cannot be `READY`, because the answer may change its shape and the
      work would be redone.
- [ ] It is a vertical slice. If it delivers a layer rather than a capability,
      it is not ready; it is a task inside something else.

---

## Definition of Done — to enter `DONE`

Every box, every time. This is a claim about the repository, not about intent.

- [ ] **Code implemented.** No TODO, no FIXME, no `NotImplementedError`, no
      stub function, no hardcoded fixture standing in for real data anywhere in
      the slice.
- [ ] **Tests exist and are named in the evidence block**, covering *each*
      acceptance criterion. A story with three criteria and one test is not done.
- [ ] **The test command was actually run this session** and its output is
      pasted into the evidence block. Not "should pass".
- [ ] **Error handling, input validation, authorisation and data-integrity
      paths are covered** — including the failing cases, not only the happy one.
- [ ] **Docs and CHANGELOG updated.** If state changed, the migration and its
      rollback are written down and the rollback has been executed once.
- [ ] **Board updated and `scripts/verify_board.py` passes.**

**A story that has code but no run test is `IN_REVIEW`, not `DONE`.** There is
no third state for "I am fairly sure it works".

---

## The evidence block

Every `DONE` item on the board carries one, indented beneath it:

```
- S-01.02.03 · A story title
  tests: tests/test_thing.py::test_the_rule_applies_at_the_boundary
  command: python -m pytest tests/test_thing.py -q
  result: 12 passed (2026-08-25)
  code: offsetx_apollo_builder/thing.py
  commit: a1b2c3d
```

| Field | Rule |
|---|---|
| `tests` | A path that exists. A `::test_name` is re-run by the verifier. Several are comma-separated. |
| `command` | The exact command. The verifier does not invent one. |
| `result` | What the run printed, and when. |
| `code` | The file(s) the slice lives in. Each must exist. A `:start-end` range must be within the file's length. |
| `commit` | The sha the evidence was taken at. |

**No resolvable evidence → the item cannot be `DONE`.** This is not subject to a
judgement that it is obviously working.

---

## WIP limit

`IN_PROGRESS` holds at most **2** items. Nothing new is pulled while an item is
`IN_PROGRESS` or `BLOCKED` — finish it, or escalate it with a linked `Q-nn` or a
named external dependency.

`BLOCKED` with no escalation is a process violation, and the verifier fails on it.

---

## Change control

New scope gets a **new ID** and is re-planned. It is never absorbed into an item
already in flight — that is how an increment quietly triples and a date becomes
meaningless.

Scope that is cut moves to `DEFERRED` with a reason and the trigger to revisit
it. **Descoping is the owner's decision, not the builder's.**
