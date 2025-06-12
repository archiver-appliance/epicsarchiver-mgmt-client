import logging
from unittest.mock import MagicMock, patch

import pytest
from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus
from requests import HTTPError, Response

from epicsarchiver_mgmt.archiver.mgmt import (
    ArchivePVRequest,
    ArchiverMgmt,
)
from epicsarchiver_mgmt.commands.repolicy import repolicy
from epicsarchiver_mgmt.commands.validation import RequestHTTPError


# --- Tests for repolicy ---
def test_repolicy_success(caplog: pytest.LogCaptureFixture) -> None:
    """Test successful repolicy operation."""
    caplog.set_level(logging.INFO)
    archiver_fqdn = "archiver.example.com"
    pvs = ["PV1", "PV2"]
    pv_requests = [
        ArchivePVRequest(pv="PV1", appliance="appliance1"),
        ArchivePVRequest(pv="PV2", appliance="appliance1"),
    ]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    existing_status = [
        {"pvName": "PV1", "status": "Paused", "appliance": "appliance1", "samplingPeriod": "1"},
        {"pvName": "PV2", "status": "Paused", "appliance": "appliance1", "samplingPeriod": "1"},
    ]
    mock_archiver_info.get_pv_status.return_value = existing_status

    with (
        patch("epicsarchiver_mgmt.commands.repolicy.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("epicsarchiver_mgmt.commands.repolicy.ArchiverMgmt", return_value=mock_archiver),
        patch("epicsarchiver_mgmt.commands.repolicy.validate_pvs_status") as mock_validate_pvs_status,
        patch("epicsarchiver_mgmt.commands.repolicy.basic_commands.PauseCommand.run_command") as mock_pause,
        patch("epicsarchiver_mgmt.commands.repolicy.basic_commands.DeleteCommand.run_command") as mock_delete,
        patch("epicsarchiver_mgmt.commands.repolicy.archive.archive") as mock_archive,
    ):
        repolicy(archiver_fqdn, pvs)

        mock_validate_pvs_status.assert_called_once_with(
            archiver_info=mock_archiver_info,
            pvs=pvs,
            expected_statuses=[
                ArchivingStatus.BeingArchived,
                ArchivingStatus.Paused,
            ],
            existing_status_infos=existing_status,
        )
        mock_pause.assert_called_once_with(archiver_fqdn, pvs)
        mock_delete.assert_called_once_with(archiver_fqdn, pvs)
        mock_archive.assert_called_once_with(archiver_fqdn, pv_requests, dry_run=False)
        assert f"Re doing policy of the PVs {pvs}" in caplog.text
        assert f"Using archiver {mock_archiver.info}" in caplog.text


def test_repolicy_http_error_on_archive(caplog: pytest.LogCaptureFixture) -> None:
    """Test repolicy operation with HTTP error during the repolicy API call."""
    caplog.set_level(logging.DEBUG)
    archiver_fqdn = "archiver.example.com"
    pvs = ["PV1"]
    pv_requests = [
        ArchivePVRequest(pv="PV1", appliance="appliance1"),
    ]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    existing_status = [
        {"pvName": "PV1", "status": "Paused", "appliance": "appliance1", "samplingPeriod": "1"},
    ]
    mock_archiver_info.get_pv_status.return_value = existing_status
    request_response = Response()
    request_response.status_code = 500
    request_response.reason = "Internal Server Error"
    http_error = HTTPError(response=request_response)
    archive_error = RequestHTTPError(http_error)  # Simulate error raised by pause

    with (
        patch("epicsarchiver_mgmt.commands.repolicy.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("epicsarchiver_mgmt.commands.repolicy.ArchiverMgmt", return_value=mock_archiver),
        patch("epicsarchiver_mgmt.commands.repolicy.validate_pvs_status") as mock_validate_pvs_status,
        patch("epicsarchiver_mgmt.commands.repolicy.basic_commands.PauseCommand.run_command") as mock_pause,
        patch("epicsarchiver_mgmt.commands.repolicy.basic_commands.DeleteCommand.run_command") as mock_delete,
        patch("epicsarchiver_mgmt.commands.repolicy.archive.archive", side_effect=archive_error) as mock_archive,
    ):
        with pytest.raises(RequestHTTPError) as exc_info:
            repolicy(archiver_fqdn, pvs)

        mock_validate_pvs_status.assert_called_once_with(
            archiver_info=mock_archiver_info,
            pvs=pvs,
            expected_statuses=[
                ArchivingStatus.BeingArchived,
                ArchivingStatus.Paused,
            ],
            existing_status_infos=existing_status,
        )
        mock_pause.assert_called_once_with(archiver_fqdn, pvs)
        mock_delete.assert_called_once_with(archiver_fqdn, pvs)
        mock_archive.assert_called_once_with(archiver_fqdn, pv_requests, dry_run=False)
        assert exc_info.value is archive_error  # Check it's the exact exception from archive


def test_repolicy_error_on_pause(caplog: pytest.LogCaptureFixture) -> None:
    """Test repolicy operation when pause fails."""
    caplog.set_level(logging.DEBUG)
    archiver_fqdn = "archiver.example.com"
    pvs = ["PV1"]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    existing_status = [
        {"pvName": "PV1", "status": "Paused", "appliance": "appliance1", "samplingPeriod": "1"},
    ]
    mock_archiver_info.get_pv_status.return_value = existing_status
    request_response = Response()
    request_response.status_code = 400
    request_response.reason = "Bad Request"
    http_error = HTTPError(response=request_response)
    pause_error = RequestHTTPError(http_error)  # Simulate error raised by pause

    with (
        patch("epicsarchiver_mgmt.commands.repolicy.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("epicsarchiver_mgmt.commands.repolicy.ArchiverMgmt", return_value=mock_archiver),
        patch("epicsarchiver_mgmt.commands.repolicy.validate_pvs_status") as mock_validate_pvs_status,
        patch(
            "epicsarchiver_mgmt.commands.repolicy.basic_commands.PauseCommand.run_command",
            side_effect=pause_error,
        ) as mock_pause,
        patch("epicsarchiver_mgmt.commands.repolicy.basic_commands.DeleteCommand.run_command") as mock_delete,
        patch("epicsarchiver_mgmt.commands.repolicy.archive.archive") as mock_archive,
    ):
        with pytest.raises(RequestHTTPError) as exc_info:
            repolicy(archiver_fqdn, pvs)

        mock_validate_pvs_status.assert_called_once()
        mock_pause.assert_called_once_with(archiver_fqdn, pvs)
        mock_delete.assert_not_called()
        mock_archive.assert_not_called()
        assert exc_info.value is pause_error  # Check it's the exact exception from pause


def test_repolicy_error_on_delete(caplog: pytest.LogCaptureFixture) -> None:
    """Test repolicy operation when delete fails."""
    caplog.set_level(logging.DEBUG)
    archiver_fqdn = "archiver.example.com"
    pvs = ["PV1"]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    existing_status = [
        {"pvName": "PV1", "status": "Paused", "appliance": "appliance1", "samplingPeriod": "1"},
    ]
    mock_archiver_info.get_pv_status.return_value = existing_status

    request_response = Response()
    request_response.status_code = 503
    request_response.reason = "Service Unavailable"
    http_error = HTTPError(response=request_response)
    delete_error = RequestHTTPError(http_error)  # Simulate error raised by delete

    with (
        patch("epicsarchiver_mgmt.commands.repolicy.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("epicsarchiver_mgmt.commands.repolicy.ArchiverMgmt", return_value=mock_archiver),
        patch("epicsarchiver_mgmt.commands.repolicy.validate_pvs_status") as mock_validate_pvs_status,
        patch("epicsarchiver_mgmt.commands.repolicy.basic_commands.PauseCommand.run_command") as mock_pause,
        patch(
            "epicsarchiver_mgmt.commands.repolicy.basic_commands.DeleteCommand.run_command",
            side_effect=delete_error,
        ) as mock_delete,
        patch("epicsarchiver_mgmt.commands.repolicy.archive.archive") as mock_archive,
    ):
        with pytest.raises(RequestHTTPError) as exc_info:
            repolicy(archiver_fqdn, pvs)

        mock_validate_pvs_status.assert_called_once()
        mock_pause.assert_called_once_with(archiver_fqdn, pvs)
        mock_delete.assert_called_once_with(archiver_fqdn, pvs)
        mock_archive.assert_not_called()
        assert exc_info.value is delete_error  # Check it's the exact exception from delete
