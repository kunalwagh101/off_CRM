# Ponytail engineering principles

How code gets written in this repository. Applies to every change, every session.

## Before adding code

1. Understand the existing code path first.
2. Ask whether the new code is actually necessary.
3. Reuse existing code whenever possible.
4. Prefer standard-library functionality.
5. Prefer native platform/framework features.
6. Prefer already-installed dependencies.
7. Avoid unnecessary abstractions, wrappers, factories, classes, services and
   dependencies.
8. Implement the smallest clean solution that fully solves the requirement.

Before a large architectural addition, explain why the existing architecture cannot
solve it more simply.

## Never simplify away

Security controls · authentication and authorization · input validation · error
handling · data integrity · database transactions where required · concurrency
protection · observability where required · tests for important behaviour ·
accessibility · production reliability.

Do not optimise for fewer lines alone. Optimise for the smallest correct, secure,
maintainable production implementation.

## Finishing

The marginal cost of completeness is near zero. Ship the whole thing: code, tests,
documentation. No dangling threads, no workaround where the real fix is in reach, no
"we can do that later" when later is five more minutes.

One rule outranks that: completeness never means *claiming* completeness. If a piece
is unfinished, say so plainly and record the honest status on the board. That is what
finishing looks like when the work is not done yet.

## The board

`BUILD_STATE.md` is the working record and the board — §2a explains the statuses.
An entry cannot become `DONE` because someone wrote `DONE`: it must name a test, and
`python scripts/verify_board.py` runs that test and refuses the claim if it fails.
If no test exists, the honest status is `IN_REVIEW`, and the fix is to write the test,
not to change the word.
