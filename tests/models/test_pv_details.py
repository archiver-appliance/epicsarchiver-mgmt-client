"""Tests for PV details model conversion."""

from epicsarchiver_mgmt.models.pv_details import DetailEnum, Details


def test_convert_json_to_details_list() -> None:
    data = [{"name": detail.value, "value": detail.name} for detail in DetailEnum]

    result = Details.from_json(data)

    assert set(result.keys()) == set(DetailEnum)
    assert len(result) == len(DetailEnum)
    assert all(result[detail] == detail.name for detail in DetailEnum)
