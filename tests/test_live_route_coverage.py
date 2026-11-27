import pytest
from scripts.qa.route_coverage import validate_routes


def test_complete_inventory_is_accepted():
    assert validate_routes(('dashboard', 'settings'), ('#settings', '#dashboard')) == ('dashboard', 'settings')


@pytest.mark.parametrize('links', [('#dashboard',), ('#dashboard', '#settings', '#settings'), ('#dashboard', '#other'), ('#dashboard', '/settings')])
def test_incomplete_or_invalid_inventory_is_rejected(links):
    with pytest.raises(AssertionError):
        validate_routes(('dashboard', 'settings'), links)
