import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser_multi_map_proxy_smoke import assert_markers, evaluate_multi_result


def state():
    positions = {"first": {"lon": 116.3, "lat": 39.9}}
    snapshot = {"markerIds": ["first"], "markers": {"first": {"point": [116.31, 39.91], "identity": 1}},
                "businessPositions": copy.deepcopy(positions)}
    return snapshot, positions, {"first": [116.31, 39.91]}


def test_multi_acceptance_checks_native_coordinate_without_modifying_business_data():
    snapshot, positions, expected = state()
    before = copy.deepcopy((snapshot, positions, expected))
    assert_markers(snapshot, positions, expected, {"first": 1})
    assert (snapshot, positions, expected) == before


@pytest.mark.parametrize("failure", ["coordinate", "membership", "identity", "business", "no_position"])
def test_multi_acceptance_rejects_invalid_native_state(failure):
    snapshot, positions, expected = state()
    if failure == "coordinate":
        snapshot["markers"]["first"]["point"][0] += .001
    elif failure == "membership":
        snapshot["markerIds"] = []
    elif failure == "identity":
        snapshot["markers"]["first"]["identity"] = 2
    elif failure == "business":
        snapshot["businessPositions"]["first"]["lon"] += .001
    elif failure == "no_position":
        snapshot["markers"]["first"]["point"] = None
    with pytest.raises(AssertionError):
        assert_markers(snapshot, positions, expected, {"first": 1})


def accepted_row():
    return {"route_success": True, "route_points": 8, "proxy_enabled": True,
            "rounds": [{"functional_pass": True, "lifecycle_pass": True}]}


@pytest.mark.parametrize('failure', ['script_errors', 'unhandled_rejections', 'console_error_messages', 'proxy_failures', 'upstream_failures', 'direct_requests'])
def test_multi_acceptance_rejects_runtime_or_transport_failures(failure):
    row = accepted_row()
    row[failure] = ["observed failure"]
    assert evaluate_multi_result(row)['passed'] is False


def test_multi_acceptance_retains_failed_first_round_after_successful_round():
    row = accepted_row()
    row['rounds'].insert(0, {"functional_pass": True, "lifecycle_pass": False})
    assert evaluate_multi_result(row)['passed'] is False
    row['rounds'][0]['lifecycle_pass'] = True
    assert evaluate_multi_result(row)['passed'] is True


def test_multi_acceptance_does_not_pass_an_empty_route_or_absent_rounds():
    row = accepted_row()
    row['route_points'] = 0
    assert evaluate_multi_result(row)['passed'] is False
    row['route_points'] = 8
    row['rounds'] = []
    assert evaluate_multi_result(row)['passed'] is False


def test_multi_acceptance_distinguishes_expected_direct_mode_and_recovered_attempts():
    row = accepted_row()
    row.update(proxy_enabled=False, direct_requests=[{'host': 'map.qq.com'}], upstream_attempt_failures=[{'error_type': 'ReadTimeout'}], recovered_upstream_requests=1)
    assert evaluate_multi_result(row)['passed'] is True
