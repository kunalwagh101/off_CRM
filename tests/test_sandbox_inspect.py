"""Regression for Docker's per-network inspect address (D-553)."""
import pytest

from verification.test_sandbox_live import _bridge_ipv4


@pytest.mark.parametrize('legacy', [{}, {'IPAddress':'192.0.2.99'}])
def test_reads_named_bridge_network(legacy):
    assert _bridge_ipv4({'NetworkSettings':{**legacy,'Networks':{'bridge':{'IPAddress':'172.17.0.2'}}}}) == '172.17.0.2'


@pytest.mark.parametrize('networks', [{}, {'other':{'IPAddress':'172.17.0.2'}}, {'bridge':{'IPAddress':''}}, {'bridge':{'IPAddress':'not-an-ip'}}])
def test_missing_or_invalid_bridge_fails_closed(networks):
    with pytest.raises(AssertionError, match='bridge IPv4'):
        _bridge_ipv4({'NetworkSettings':{'IPAddress':'192.0.2.99','Networks':networks}})
