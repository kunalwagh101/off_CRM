"""The harness that runs the CRM suite on PostgreSQL keeps its own rules.

`tests/conftest.py` may skip a test in PostgreSQL mode only when it reads the
CRM's SQLite file, and only with a reason. A skip with no reason, or the mode
switched on with nowhere to run, would let a failure pass as a skip. Each case
runs in a pytest of its own, with a copy of the real conftest.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

CONFTEST = (Path(__file__).parent / "conftest.py").read_text(encoding="utf-8")

MARKED = """
import pytest

@pytest.mark.crm_sqlite_file({reason})
def test_reads_the_file():
    pass
"""


@pytest.fixture
def harness(pytester, monkeypatch):
    pytester.makeconftest(CONFTEST)
    monkeypatch.delenv("OFF_CRM_TEST_CRM_ON_POSTGRES", raising=False)
    monkeypatch.setenv("OFF_CRM_TEST_POSTGRES_URL", "postgresql://nobody@127.0.0.1:1/never")
    return pytester


def test_a_file_test_runs_as_usual_when_the_mode_is_off(harness):
    harness.makepyfile(MARKED.format(reason='"opens the backup archive"'))
    harness.runpytest_subprocess().assert_outcomes(passed=1)


def test_a_file_test_is_skipped_on_postgres_and_says_why(harness, monkeypatch):
    monkeypatch.setenv("OFF_CRM_TEST_CRM_ON_POSTGRES", "1")
    harness.makepyfile(MARKED.format(reason='"opens the backup archive"'))
    result = harness.runpytest_subprocess("-rs")
    result.assert_outcomes(skipped=1)
    result.stdout.fnmatch_lines(["*reads the CRM's SQLite file: opens the backup archive*"])


@pytest.mark.parametrize("reason", ["", '""', '"   "'])
def test_a_skip_with_no_reason_is_refused(harness, reason):
    harness.makepyfile(MARKED.format(reason=reason))
    result = harness.runpytest_subprocess()
    assert result.ret != 0
    result.stderr.fnmatch_lines(["*crm_sqlite_file needs a reason*"])


def test_the_mode_without_a_database_is_refused(harness, monkeypatch):
    monkeypatch.setenv("OFF_CRM_TEST_CRM_ON_POSTGRES", "1")
    monkeypatch.delenv("OFF_CRM_TEST_POSTGRES_URL")
    harness.makepyfile("def test_anything():\n    pass\n")
    result = harness.runpytest_subprocess()
    assert result.ret != 0
    result.stderr.fnmatch_lines(["*needs OFF_CRM_TEST_POSTGRES_URL*"])
