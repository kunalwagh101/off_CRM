"""A26: the shipped image must install its runtime extras from the lock."""
import pytest

from scripts.qa.a26_image_dependency_contract import (
    ContractError,
    REQUIRED,
    _lock_versions,
    require_lock_parity,
    require_no_dev_packages,
)


@pytest.fixture
def locked():
    return {
        name: {f"{i}.0"}
        for i, name in enumerate(REQUIRED, start=1)
    }


def test_A26_all_runtime_extras_match_lock(locked):
    installed = {name: next(iter(versions)) for name, versions in locked.items()}
    assert require_lock_parity(locked, installed) == len(REQUIRED)


def test_A26_missing_postgresql_binary_fails(locked):
    installed = {name: next(iter(versions)) for name, versions in locked.items()}
    installed.pop("psycopg-binary")
    with pytest.raises(ContractError, match="psycopg-binary"):
        require_lock_parity(locked, installed)


def test_A26_installed_dependency_drift_fails(locked):
    installed = {name: next(iter(versions)) for name, versions in locked.items()}
    installed["boto3"] = "0.0.0-drift"
    with pytest.raises(ContractError, match="boto3"):
        require_lock_parity(locked, installed)


def test_A26_lock_missing_required_extra_fails(locked):
    installed = {name: next(iter(versions)) for name, versions in locked.items()}
    locked.pop("psycopg")
    with pytest.raises(ContractError, match="psycopg"):
        require_lock_parity(locked, installed)


def test_A26_allows_multi_platform_locked_versions(locked):
    installed = {name: next(iter(versions)) for name, versions in locked.items()}
    locked["boto3"].add("999.0.0")
    assert require_lock_parity(locked, installed) == len(REQUIRED)


def test_A26_production_image_must_not_install_dev_tools():
    assert require_no_dev_packages(set()) is None
    with pytest.raises(ContractError, match="pytest"):
        require_no_dev_packages({"pytest"})
    with pytest.raises(ContractError, match="ruff"):
        require_no_dev_packages({"ruff"})
    with pytest.raises(ContractError, match="playwright"):
        require_no_dev_packages({"playwright"})


def test_A26_lock_parser_reads_distinct_package_blocks():
    data = '''
[[package]]
name = "boto3"
version = "1.0"

[[package]]
name = "boto3"
version = "2.0"

[[package]]
name = "psycopg"
version = "3.0"
'''
    assert _lock_versions(data) == {"boto3": {"1.0", "2.0"}, "psycopg": {"3.0"}}


def test_A26_missing_or_unreadable_lock_rejected():
    with pytest.raises(ContractError, match="lock"):
        _lock_versions("")
