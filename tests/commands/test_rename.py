import logging
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from requests import HTTPError, Response

from epicsarchiver_mgmt.archiver.info import ArchiverMgmtInfo
from epicsarchiver_mgmt.archiver.mgmt import (
    ArchiverMgmt,
)
from epicsarchiver_mgmt.commands.rename import (
    TooMuchStoredDataError,
    rename,
    rename_and_append,
    validate_size,
)
from epicsarchiver_mgmt.commands.validation import RequestHTTPError
from tests.commands.test_validation import accept_confirmation


@pytest.fixture
def rename_fixture() -> Generator[dict[str, MagicMock]]:
    """Fixture to mock dependencies for rename tests.

    Mocks ArchiverMgmtInfo, ArchiverMgmt, and various validation functions.
    Also mocks PauseCommand and ResumeCommand to avoid actual command execution.

    Yields:
        dict[str, MagicMock]: A dictionary of mocked objects for use in tests.
    """
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver1 = MagicMock(spec=ArchiverMgmt)
    mock_archiver1.info = {"identity": "archiver1"}
    mock_archiver1.appliances_in_cluster = [{"identity": "archiver1"}, {"identity": "archiver2"}]
    mock_archiver2 = MagicMock(spec=ArchiverMgmt)
    mock_archiver2.info = {"identity": "archiver2"}
    mock_archiver2.appliances_in_cluster = [{"identity": "archiver1"}, {"identity": "archiver2"}]

    patches = {
        "ArchiverMgmtInfo": patch(
            "epicsarchiver_mgmt.commands.rename.ArchiverMgmtInfo", return_value=mock_archiver_info
        ),
        "ArchiverMgmt_rename": patch(
            "epicsarchiver_mgmt.commands.rename.ArchiverMgmt", side_effect=[mock_archiver1, mock_archiver2]
        ),
        "ArchiverMgmt_validation": patch(
            "epicsarchiver_mgmt.commands.validation.ArchiverMgmt", side_effect=[mock_archiver1, mock_archiver2]
        ),
        "validate_not_same": patch("epicsarchiver_mgmt.commands.rename.validate_not_same"),
        "validate_pvs_status": patch("epicsarchiver_mgmt.commands.rename.validate_pvs_status"),
        "validate_size": patch("epicsarchiver_mgmt.commands.rename.validate_size"),
        "PauseCommand": patch("epicsarchiver_mgmt.commands.rename.PauseCommand.run_command"),
        "ResumeCommand": patch("epicsarchiver_mgmt.commands.rename.ResumeCommand.run_command"),
        "validate_operation_results": patch("epicsarchiver_mgmt.commands.rename.validate_operation_results"),
        "_parallel_execute_rename": patch("epicsarchiver_mgmt.commands.rename._parallel_execute_rename"),
        "_parallel_execute_rename_and_append": patch(
            "epicsarchiver_mgmt.commands.rename._parallel_execute_rename_and_append"
        ),
    }

    mocks = {name: p.start() for name, p in patches.items()}
    yield mocks
    patch.stopall()


def test_rename_success(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch, rename_fixture: dict[str, MagicMock]
) -> None:
    """Test successful rename operation."""
    caplog.set_level(logging.INFO)
    archiver_fqdns = ["archiver1.example.com", "archiver2.example.com"]
    renames = [("old_pv1", "new_pv1"), ("old_pv2", "new_pv2")]

    rename_fixture["_parallel_execute_rename"].return_value = [
        {"status": "ok", "desc": "Renamed"},
        {"status": "ok", "desc": "Renamed"},
    ]
    accept_confirmation(monkeypatch)
    rename(archiver_fqdns, renames)

    rename_fixture["validate_not_same"].assert_called_once_with(renames)
    rename_fixture["validate_pvs_status"].assert_called()
    assert rename_fixture["validate_pvs_status"].call_count == 2
    rename_fixture["validate_size"].assert_called()
    rename_fixture["PauseCommand"].assert_called_once()
    rename_fixture["ResumeCommand"].assert_called_once_with(archiver_fqdns, ("new_pv1", "new_pv2"))
    rename_fixture["validate_operation_results"].assert_called_once()
    rename_fixture["_parallel_execute_rename"].assert_called_once()
    assert "Renaming PVs" in caplog.text
    assert "Using archivers" in caplog.text


def test_rename_http_error(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch, rename_fixture: dict[str, MagicMock]
) -> None:
    """Test rename operation with HTTP error."""
    caplog.set_level(logging.DEBUG)
    archiver_fqdns = ["archiver.example.com"]
    renames = [("old_pv1", "new_pv1")]
    request_response = Response()
    request_response.status_code = 500
    request_response.reason = "HTTP Error"

    rename_fixture["_parallel_execute_rename"].side_effect = HTTPError(response=request_response)
    accept_confirmation(monkeypatch)
    with pytest.raises(RequestHTTPError):
        rename(archiver_fqdns, renames)

    rename_fixture["validate_not_same"].assert_called_once_with(renames)
    rename_fixture["validate_pvs_status"].assert_called()
    rename_fixture["validate_size"].assert_called()
    assert rename_fixture["validate_pvs_status"].call_count == 2
    rename_fixture["PauseCommand"].assert_called_once()
    rename_fixture["ResumeCommand"].assert_not_called()
    rename_fixture["_parallel_execute_rename"].assert_called_once()
    assert "Error Renaming PVs" in caplog.text
    assert "HTTPError" in caplog.text


def test_append_rename_success(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch, rename_fixture: dict[str, MagicMock]
) -> None:
    """Test successful append_rename operation."""
    caplog.set_level(logging.INFO)
    archiver_fqdns = ["archiver1.example.com", "archiver2.example.com"]
    renames = [("old_pv1", "new_pv1"), ("old_pv2", "new_pv2")]

    rename_fixture["_parallel_execute_rename_and_append"].return_value = [
        {"status": "ok", "desc": "Renamed"},
        {"status": "ok", "desc": "Renamed"},
    ]
    accept_confirmation(monkeypatch)
    rename_and_append(archiver_fqdns, renames)

    rename_fixture["validate_not_same"].assert_called_once_with(renames)
    rename_fixture["validate_pvs_status"].assert_called()
    rename_fixture["validate_size"].assert_called()
    rename_fixture["ResumeCommand"].assert_called_once_with(archiver_fqdns, ("new_pv1", "new_pv2"))
    assert rename_fixture["validate_pvs_status"].call_count == 2
    rename_fixture["validate_operation_results"].assert_called_once()
    rename_fixture["_parallel_execute_rename_and_append"].assert_called_once()
    assert "Renaming and Appending PVs" in caplog.text
    assert "Using archivers" in caplog.text


def test_append_rename_http_error(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch, rename_fixture: dict[str, MagicMock]
) -> None:
    """Test append_rename operation with HTTP error."""
    caplog.set_level(logging.DEBUG)
    archiver_fqdns = ["archiver.example.com"]
    renames = [("old_pv1", "new_pv1")]
    request_response = Response()
    request_response.status_code = 500
    request_response.reason = "HTTP Error"

    rename_fixture["_parallel_execute_rename_and_append"].side_effect = HTTPError(response=request_response)

    accept_confirmation(monkeypatch)
    with pytest.raises(RequestHTTPError):
        rename_and_append(archiver_fqdns, renames)

    rename_fixture["validate_not_same"].assert_called_once_with(renames)
    rename_fixture["validate_pvs_status"].assert_called()
    rename_fixture["validate_size"].assert_called()
    assert rename_fixture["validate_pvs_status"].call_count == 2
    rename_fixture["_parallel_execute_rename_and_append"].assert_called_once()
    assert "Error Renaming and Appending PVs" in caplog.text
    assert "HTTPError" in caplog.text


def test_validate_not_large_success(caplog: pytest.LogCaptureFixture) -> None:
    """Test validate_not_large with PVs that are not too large."""
    caplog.set_level(logging.INFO)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.get_pv_details.return_value = [{"name": "Estimated storage rate (MB/day)", "value": "500"}]
    old_pvs = ["old_pv1", "old_pv2"]

    with patch("epicsarchiver_mgmt.commands.rename.ArchiverMgmt", return_value=mock_archiver):
        validate_size(mock_archiver, old_pvs)

    assert "Old PV" not in caplog.text


def test_validate_not_large_failure() -> None:
    """Test validate_not_large with PVs that are too large."""
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.get_pv_details.return_value = [{"name": "Estimated storage rate (MB/day)", "value": "1500"}]
    old_pvs = ["old_pv1"]

    with patch("epicsarchiver_mgmt.commands.rename.ArchiverMgmt", return_value=mock_archiver):
        with pytest.raises(TooMuchStoredDataError) as exc_info:
            validate_size(mock_archiver, old_pvs)

        assert "Old PV old_pv1 has 1500.0 MB data stored. Manual intervention required." in str(exc_info.value)
