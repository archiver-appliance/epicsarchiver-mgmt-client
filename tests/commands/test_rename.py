import logging
from unittest.mock import MagicMock, patch

import pytest
from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo
from requests import HTTPError, Response

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


def test_rename_success(caplog: pytest.LogCaptureFixture) -> None:
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
        patch("epicsarchiver_mgmt.commands.rename._pause_pvs") as mock_pause_pvs,
        patch("epicsarchiver_mgmt.commands.rename.validate_operation_results") as mock_validate_operation_results,
        patch("epicsarchiver_mgmt.commands.rename._parallel_execute_rename") as mock_parallel_execute_rename,
    ):
        mock_parallel_execute_rename.return_value = [
            {"status": "ok", "desc": "Renamed"},
            {"status": "ok", "desc": "Renamed"},
        ]
        rename(archiver_fqdns, renames)

        mock_validate_not_same.assert_called_once_with(renames)
        mock_validate_pvs_status.assert_called()
        assert mock_validate_pvs_status.call_count == 2
        mock_pause_pvs.assert_called_once()
        mock_validate_operation_results.assert_called_once()
        mock_parallel_execute_rename.assert_called_once()
        assert "Renaming PVs" in caplog.text
        assert "Using archivers" in caplog.text


def test_rename_http_error(caplog: pytest.LogCaptureFixture) -> None:
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
        patch("epicsarchiver_mgmt.commands.rename._pause_pvs") as mock_pause_pvs,
        patch("epicsarchiver_mgmt.commands.rename._parallel_execute_rename") as mock_parallel_execute_rename,
    ):
        mock_parallel_execute_rename.side_effect = HTTPError(response=request_response)
        with pytest.raises(RequestHTTPError):
            rename(archiver_fqdns, renames)

        mock_validate_not_same.assert_called_once_with(renames)
        mock_validate_pvs_status.assert_called()
        assert mock_validate_pvs_status.call_count == 2
        mock_pause_pvs.assert_called_once()
        mock_parallel_execute_rename.assert_called_once()
        assert "Error Renaming PVs" in caplog.text
        assert "HTTPError" in caplog.text


def test_append_rename_success(caplog: pytest.LogCaptureFixture) -> None:
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
        patch("epicsarchiver_mgmt.commands.rename._pause_pvs") as mock_pause_pvs,
        patch("epicsarchiver_mgmt.commands.rename.validate_operation_results") as mock_validate_operation_results,
        patch(
            "epicsarchiver_mgmt.commands.rename._parallel_execute_rename_and_append"
        ) as mock_parallel_execute_rename_and_append,
    ):
        mock_parallel_execute_rename_and_append.return_value = [
            {"status": "ok", "desc": "Renamed"},
            {"status": "ok", "desc": "Renamed"},
        ]
        rename_and_append(archiver_fqdns, renames)

        mock_validate_not_same.assert_called_once_with(renames)
        mock_validate_pvs_status.assert_called()
        assert mock_validate_pvs_status.call_count == 2
        mock_pause_pvs.assert_called_once()
        mock_validate_operation_results.assert_called_once()
        mock_parallel_execute_rename_and_append.assert_called_once()
        assert "Renaming and Appending PVs" in caplog.text
        assert "Using archivers" in caplog.text


def test_append_rename_http_error(caplog: pytest.LogCaptureFixture) -> None:
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
        patch("epicsarchiver_mgmt.commands.rename._pause_pvs") as mock_pause_pvs,
        patch(
            "epicsarchiver_mgmt.commands.rename._parallel_execute_rename_and_append"
        ) as mock_parallel_execute_rename_and_append,
    ):
        mock_parallel_execute_rename_and_append.side_effect = HTTPError(response=request_response)
        with pytest.raises(RequestHTTPError):
            rename_and_append(archiver_fqdns, renames)

        mock_validate_not_same.assert_called_once_with(renames)
        mock_validate_pvs_status.assert_called()
        assert mock_validate_pvs_status.call_count == 2
        mock_pause_pvs.assert_called_once()
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
