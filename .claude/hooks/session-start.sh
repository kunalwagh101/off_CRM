#!/bin/bash
# SessionStart hook for off_CRM.
#
# Two jobs:
#   1. Say which repository this session is actually in, on the first line.
#   2. Install dependencies so tests and linters work without a warm-up round.
#
# Job 1 exists because of a real incident: a session was started against an
# empty sibling repository, found no commits, and reported "your repo is empty"
# instead of noticing it was in the wrong place. A repository that announces
# itself makes that failure impossible rather than unlikely.
set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"

# ── 1. Identity. Cheap, and always printed. ─────────────────────────────────
echo "=============================================================="
echo " REPO      : $(git config --get remote.origin.url 2>/dev/null | sed 's#.*/##; s#\.git$##' || echo unknown)"
echo " BRANCH    : $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
echo " HEAD      : $(git log -1 --format='%h %s' 2>/dev/null || echo 'NO COMMITS')"
echo " COMMITS   : $(git rev-list --count HEAD 2>/dev/null || echo 0)"
echo " PY FILES  : $(git ls-files '*.py' 2>/dev/null | wc -l | tr -d ' ')"
echo "--------------------------------------------------------------"
echo " Read BUILD_STATE.md first. It is the working record and is"
echo " kept current deliberately - prefer it over re-reading the code."
echo " If this is not the repository you expected, STOP and say so."
echo "=============================================================="

# Only install in the remote (web) environment; a local machine is already set up.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# ── 2. Python. `uv sync` uses pyproject + uv.lock, so it installs the full ──
# dependency set including `scrapling`, which requirements.txt omits. That
# omission is why tests/test_discovery.py has been failing in web sessions.
echo "[setup] python deps via uv sync --extra dev"
uv sync --extra dev

# `uv run` is how CI invokes pytest; make the same interpreter the default so
# a plain `python -m pytest` in a session behaves the same way.
echo "export PATH=\"$(pwd)/.venv/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
echo "export PYTHONPATH=\"$(pwd)\"" >> "$CLAUDE_ENV_FILE"

# ── 3. Frontend. ────────────────────────────────────────────────────────────
if [ -d frontend ]; then
  echo "[setup] frontend deps via npm install"
  ( cd frontend && npm install --no-audit --no-fund )
fi

echo "[setup] done"
