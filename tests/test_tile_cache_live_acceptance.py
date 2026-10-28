from tests.browser_map_tile_cache_smoke import evaluate_tile_probe, evaluate_tile_cache_policy


def test_live_cache_probe_requires_unchanged_bytes_and_no_second_upstream_call():
    baseline = dict(statuses=[200, 200], cache_states=["MISS", "HIT"],
                    same_body=True, size=100, second_upstream_calls=0)
    assert evaluate_tile_probe(baseline)
    for change in ({"cache_states": ["MISS", "MISS"]}, {"same_body": False},
                   {"second_upstream_calls": 1}, {"statuses": [200, 502]}, {"size": 0}):
        assert not evaluate_tile_probe({**baseline, **change})


def test_live_cache_policy_requires_evidence_for_expected_bypass():
    row = dict(statuses=[200, 200], cache_states=["BYPASS", "BYPASS"],
               same_body=True, size=100, second_upstream_calls=1)
    assert not evaluate_tile_cache_policy(row)
    assert evaluate_tile_cache_policy({**row, "bypass_reason": "set_cookie"})
    assert evaluate_tile_cache_policy({**row, "bypass_reason": "upstream_cache_policy"})
    assert not evaluate_tile_probe({**row, "bypass_reason": "set_cookie"})
    for change in ({"statuses": [200, 502]}, {"same_body": False}, {"size": 0},
                   {"second_upstream_calls": 0}, {"cache_states": ["MISS", "MISS"]}):
        assert not evaluate_tile_cache_policy({**row, "bypass_reason": "set_cookie", **change})
