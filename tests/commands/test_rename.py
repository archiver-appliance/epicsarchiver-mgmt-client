import logging
from unittest.mock import MagicMock, patch

import pytest
from epicsarchiver import ArchiveEvent
from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo
from epicsarchiver.retrieval.archiver_retrieval.archiver_retrieval import ArchiverRetrieval
from requests import HTTPError, Response

from epicsarchiver_mgmt.archiver.mgmt import (
    ArchiverMgmt,
)
from epicsarchiver_mgmt.commands.rename import (
    DataIsTheSameError,
    TooMuchStoredDataError,
    rename,
    rename_and_append,
    validate_data,
    validate_size,
)
from epicsarchiver_mgmt.commands.validation import RequestHTTPError
from tests.commands.test_validation import accept_confirmation


def test_rename_success(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test successful rename operation."""
    caplog.set_level(logging.INFO)
    archiver_fqdns = ["archiver1.example.com", "archiver2.example.com"]
    renames = [("old_pv1", "new_pv1"), ("old_pv2", "new_pv2")]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver1 = MagicMock(spec=ArchiverMgmt)
    mock_archiver1.info = "Archiver1 Info"
    mock_archiver2 = MagicMock(spec=ArchiverMgmt)
    mock_archiver2.info = "Archiver2 Info"
    mock_archiver1.rename_pv.return_value = {"status": "ok", "desc": "Renamed"}
    mock_archiver2.rename_pv.return_value = {"status": "ok", "desc": "Renamed"}

    with (
        patch("epicsarchiver_mgmt.commands.rename.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch(
            "epicsarchiver_mgmt.commands.rename.ArchiverMgmt",
            side_effect=[mock_archiver1, mock_archiver2],
        ),
        patch("epicsarchiver_mgmt.commands.rename.validate_not_same") as mock_validate_not_same,
        patch("epicsarchiver_mgmt.commands.rename.validate_pvs_status") as mock_validate_pvs_status,
        patch("epicsarchiver_mgmt.commands.rename.validate_size") as mock_validate_size,
        patch("epicsarchiver_mgmt.commands.rename.PauseCommand.run_command") as mock_pause_command,
        patch("epicsarchiver_mgmt.commands.rename.ResumeCommand.run_command") as mock_resume_command,
        patch("epicsarchiver_mgmt.commands.rename.validate_operation_results") as mock_validate_operation_results,
        patch("epicsarchiver_mgmt.commands.rename._parallel_execute_rename") as mock_parallel_execute_rename,
    ):
        mock_parallel_execute_rename.return_value = [
            {"status": "ok", "desc": "Renamed"},
            {"status": "ok", "desc": "Renamed"},
        ]
        accept_confirmation(monkeypatch)
        rename(archiver_fqdns, renames)

        mock_validate_not_same.assert_called_once_with(renames)
        mock_validate_pvs_status.assert_called()
        assert mock_validate_pvs_status.call_count == 2
        mock_validate_size.assert_called()
        mock_pause_command.assert_called_once()
        mock_resume_command.assert_called_once_with(archiver_fqdns, ("new_pv1", "new_pv2"))
        mock_validate_operation_results.assert_called_once()
        mock_parallel_execute_rename.assert_called_once()
        assert "Renaming PVs" in caplog.text
        assert "Using archivers" in caplog.text


def test_rename_http_error(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test rename operation with HTTP error."""
    caplog.set_level(logging.DEBUG)
    archiver_fqdns = ["archiver.example.com"]
    renames = [("old_pv1", "new_pv1")]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    request_response = Response()
    request_response.status_code = 500
    request_response.reason = "HTTP Error"
    mock_archiver.rename_pv.side_effect = HTTPError(response=request_response)

    with (
        patch("epicsarchiver_mgmt.commands.rename.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("epicsarchiver_mgmt.commands.rename.ArchiverMgmt", return_value=mock_archiver),
        patch("epicsarchiver_mgmt.commands.rename.validate_not_same") as mock_validate_not_same,
        patch("epicsarchiver_mgmt.commands.rename.validate_pvs_status") as mock_validate_pvs_status,
        patch("epicsarchiver_mgmt.commands.rename.validate_size") as mock_validate_size,
        patch("epicsarchiver_mgmt.commands.rename.PauseCommand.run_command") as mock_pause_command,
        patch("epicsarchiver_mgmt.commands.rename.ResumeCommand.run_command") as mock_resume_command,
        patch("epicsarchiver_mgmt.commands.rename._parallel_execute_rename") as mock_parallel_execute_rename,
    ):
        mock_parallel_execute_rename.side_effect = HTTPError(response=request_response)
        accept_confirmation(monkeypatch)
        with pytest.raises(RequestHTTPError):
            rename(archiver_fqdns, renames)

        mock_validate_not_same.assert_called_once_with(renames)
        mock_validate_pvs_status.assert_called()
        mock_validate_size.assert_called()
        assert mock_validate_pvs_status.call_count == 2
        mock_pause_command.assert_called_once()
        mock_resume_command.assert_not_called()
        mock_parallel_execute_rename.assert_called_once()
        assert "Error Renaming PVs" in caplog.text
        assert "HTTPError" in caplog.text


def test_append_rename_success(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test successful append_rename operation."""
    caplog.set_level(logging.INFO)
    archiver_fqdns = ["archiver1.example.com", "archiver2.example.com"]
    renames = [("old_pv1", "new_pv1"), ("old_pv2", "new_pv2")]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver1 = MagicMock(spec=ArchiverMgmt)
    mock_archiver1.info = "Archiver1 Info"
    mock_archiver2 = MagicMock(spec=ArchiverMgmt)
    mock_archiver2.info = "Archiver2 Info"
    mock_archiver1.rename_and_append.return_value = {"status": "ok", "desc": "Renamed"}
    mock_archiver2.rename_and_append.return_value = {"status": "ok", "desc": "Renamed"}

    with (
        patch("epicsarchiver_mgmt.commands.rename.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch(
            "epicsarchiver_mgmt.commands.rename.ArchiverMgmt",
            side_effect=[mock_archiver1, mock_archiver2],
        ),
        patch("epicsarchiver_mgmt.commands.rename.validate_not_same") as mock_validate_not_same,
        patch("epicsarchiver_mgmt.commands.rename.validate_pvs_status") as mock_validate_pvs_status,
        patch("epicsarchiver_mgmt.commands.rename.validate_size") as mock_validate_size,
        patch("epicsarchiver_mgmt.commands.rename.validate_data") as mock_validate_data,
        patch("epicsarchiver_mgmt.commands.rename.PauseCommand.run_command") as _mock_pause_command,
        patch("epicsarchiver_mgmt.commands.rename.ResumeCommand.run_command") as mock_resume_command,
        patch("epicsarchiver_mgmt.commands.rename.validate_operation_results") as mock_validate_operation_results,
        patch(
            "epicsarchiver_mgmt.commands.rename._parallel_execute_rename_and_append"
        ) as mock_parallel_execute_rename_and_append,
    ):
        mock_parallel_execute_rename_and_append.return_value = [
            {"status": "ok", "desc": "Renamed"},
            {"status": "ok", "desc": "Renamed"},
        ]
        accept_confirmation(monkeypatch)
        rename_and_append(archiver_fqdns, renames)

        mock_validate_not_same.assert_called_once_with(renames)
        mock_validate_pvs_status.assert_called()
        mock_validate_size.assert_called()
        mock_validate_data.assert_called_once()
        mock_resume_command.assert_called_once_with(archiver_fqdns, ("new_pv1", "new_pv2"))
        assert mock_validate_pvs_status.call_count == 2
        mock_validate_operation_results.assert_called_once()
        mock_parallel_execute_rename_and_append.assert_called_once()
        assert "Renaming and Appending PVs" in caplog.text
        assert "Using archivers" in caplog.text


def test_append_rename_http_error(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test append_rename operation with HTTP error."""
    caplog.set_level(logging.DEBUG)
    archiver_fqdns = ["archiver.example.com"]
    renames = [("old_pv1", "new_pv1")]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    request_response = Response()
    request_response.status_code = 500
    request_response.reason = "HTTP Error"
    mock_archiver.rename_and_append.side_effect = HTTPError(response=request_response)

    with (
        patch("epicsarchiver_mgmt.commands.rename.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("epicsarchiver_mgmt.commands.rename.ArchiverMgmt", return_value=mock_archiver),
        patch("epicsarchiver_mgmt.commands.rename.validate_not_same") as mock_validate_not_same,
        patch("epicsarchiver_mgmt.commands.rename.validate_pvs_status") as mock_validate_pvs_status,
        patch("epicsarchiver_mgmt.commands.rename.validate_size") as mock_validate_size,
        patch("epicsarchiver_mgmt.commands.rename.validate_data") as mock_validate_data,
        patch("epicsarchiver_mgmt.commands.rename.PauseCommand.run_command") as _mock_pause_command,
        patch(
            "epicsarchiver_mgmt.commands.rename._parallel_execute_rename_and_append"
        ) as mock_parallel_execute_rename_and_append,
    ):
        mock_parallel_execute_rename_and_append.side_effect = HTTPError(response=request_response)

        accept_confirmation(monkeypatch)
        with pytest.raises(RequestHTTPError):
            rename_and_append(archiver_fqdns, renames)

        mock_validate_not_same.assert_called_once_with(renames)
        mock_validate_pvs_status.assert_called()
        mock_validate_size.assert_called()
        mock_validate_data.assert_called_once()
        assert mock_validate_pvs_status.call_count == 2
        mock_parallel_execute_rename_and_append.assert_called_once()
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


def test_validate_data_success(caplog: pytest.LogCaptureFixture) -> None:
    """Test validate_data with PVs that have the same data."""
    caplog.set_level(logging.INFO)
    mock_archiver = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver.hostname = "archiver.example.com"
    mock_ret = MagicMock(spec=ArchiverRetrieval)
    mock_ret.get_events.return_value = [
        ArchiveEvent(pv="old_pv1", val=1, secondsintoyear=0, year=2023, nanos=0, severity=0, status=0, field_values=[])
    ]
    mock_ret.get_events.return_value = []
    with patch("epicsarchiver_mgmt.commands.rename.ArchiverRetrieval", return_value=mock_ret):
        validate_data(mock_archiver, [("old_pv1", "new_pv1")])

    assert "Data for old_pv1 is the same as new_pv1" not in caplog.text


def test_validate_data_failure() -> None:
    """Test validate_data with PVs that have the same data."""
    mock_archiver = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver.hostname = "archiver.example.com"
    mock_ret = MagicMock(spec=ArchiverRetrieval)
    mock_ret.get_events.return_value = [
        ArchiveEvent(pv="old_pv1", val=1, secondsintoyear=0, year=2023, nanos=0, severity=0, status=0, field_values=[])
    ]
    mock_ret.get_events.return_value = [
        ArchiveEvent(pv="new_pv1", val=1, secondsintoyear=0, year=2023, nanos=0, severity=0, status=0, field_values=[])
    ]
    with patch("epicsarchiver_mgmt.commands.rename.ArchiverRetrieval", return_value=mock_ret):
        with pytest.raises(DataIsTheSameError) as exc_info:
            validate_data(mock_archiver, [("old_pv1", "new_pv1")])
        assert "Data for old_pv1 and new_pv1 is the same." in str(exc_info.value)
