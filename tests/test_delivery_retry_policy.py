from datetime import datetime, timezone
import pytest
from offsetx_apollo_builder.outreach.deliverability.retry import (
    delivery_retry_delay, next_worker_retry_wait, parse_retry_after, valid_poll_seconds,
)

@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), 0, .249, 61])
def test_invalid_poll(value):
    assert not valid_poll_seconds(value)

@pytest.mark.parametrize('value', [.25, 2., 60.])
def test_valid_poll(value):
    assert valid_poll_seconds(value)


def test_long_outage_stays_bounded():
    wait = None
    for _ in range(2000):
        wait = next_worker_retry_wait(.25, wait)
        assert .5 <= wait <= 60
    assert wait == 60
    assert next_worker_retry_wait(.25, None) == .5
    assert next_worker_retry_wait(.25, .5) == 1


@pytest.mark.parametrize('hint, expected', [(None,5), (0,5), (-1,5), (True,5), ('12',5), (float('inf'),5), (12,12), (3600,3600), (3601,None), (10**100,None)])
def test_retry_delay(hint, expected):
    assert delivery_retry_delay(1, hint) == expected


def test_default_delay_is_bounded():
    assert delivery_retry_delay(2, None) == 10
    assert delivery_retry_delay(1000000, None) == 3600


@pytest.mark.parametrize('header, expected', [('12',12),('0',0),('000003600',3600),('9999',3601),('9'*5000,3601),('²',None),('-5',None),('junk',None), (None,None)])
def test_parse_retry_after(header, expected):
    assert parse_retry_after(header) == expected


def test_http_date():
    now = datetime(2026, 11, 28, 0, 0, tzinfo=timezone.utc)
    assert parse_retry_after('Sat, 28 Nov 2026 00:00:30 GMT', now=now) == 30
    assert parse_retry_after('Sat, 28 Nov 2026 03:00:00 GMT', now=now) == 3601
