def validate_routes(expected, links):
    expected = tuple(expected)
    links = tuple(links)
    assert len(set(expected)) == len(expected), 'Duplicate expected route'
    assert all(isinstance(link, str) and link.startswith('#') for link in links), 'Invalid navigation link'
    actual = tuple(link[1:] for link in links)
    assert len(set(actual)) == len(actual), 'Duplicate navigation route'
    assert set(actual) == set(expected), (
        f'Missing routes: {sorted(set(expected) - set(actual))}; '
        f'Unexpected routes: {sorted(set(actual) - set(expected))}'
    )
    return expected
