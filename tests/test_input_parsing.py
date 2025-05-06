from io import StringIO

import pytest

from archmgmt.input_parsing import ParseCSVError, double_column_csv


def test_parse_csv_success() -> None:
    """Test parse_csv with a valid file."""
    file_content = "old_pv1,new_pv1\nold_pv2,new_pv2"
    file_obj = StringIO(file_content)
    expected_result = [("old_pv1", "new_pv1"), ("old_pv2", "new_pv2")]
    assert double_column_csv(file_obj) == expected_result


def test_parse_csv_failure() -> None:
    """Test parse_csv with an invalid file (incorrect number of PVs)."""
    file_content = "old_pv1,new_pv1\nold_pv2"
    file_obj = StringIO(file_content)
    with pytest.raises(ParseCSVError, match="Invalid row \\['old_pv2'\\] in csv file"):
        double_column_csv(file_obj)


def test_parse_csv_empty_file() -> None:
    """Test parse_csv with an empty file."""
    file_content = ""
    file_obj = StringIO(file_content)
    assert double_column_csv(file_obj) == []


def test_parse_csv_with_whitespace() -> None:
    """Test parse_csv with whitespace around the commas."""
    file_content = "old_pv1 , new_pv1\nold_pv2 ,new_pv2 "
    file_obj = StringIO(file_content)
    expected_result = [("old_pv1 ", " new_pv1"), ("old_pv2 ", "new_pv2 ")]
    assert double_column_csv(file_obj) == expected_result
