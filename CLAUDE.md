@AGENTS.md

## Claude Code

`AGENTS.md` above is the vendor-neutral brief every coding agent gets; Claude Code
reads `CLAUDE.md` rather than `AGENTS.md`, so this file imports it instead of
repeating it.

Engineering principles load from `.claude/rules/ponytail.md`.

Before reporting anything as done, run `python scripts/verify_board.py` and report
what it actually says.
