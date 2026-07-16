from offsetx_apollo_builder.runner import extract_matches, pick_match_for_candidate


def test_extract_matches_from_matches():
    response = {"matches": [{"id": "abc"}]}
    assert extract_matches(response) == [{"id": "abc"}]


def test_pick_match_by_id():
    matches = [{"id": "111"}, {"id": "222"}]
    assert pick_match_for_candidate(matches, "222") == {"id": "222"}
