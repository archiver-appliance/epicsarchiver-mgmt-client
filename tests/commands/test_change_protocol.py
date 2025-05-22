import logging
from unittest.mock import MagicMock, patch

import pytest
from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus
from requests import HTTPError, Response

from epicsarchiver_mgmt.archiver.mgmt import (
    ArchivePVRequest,
    ArchiverMgmt,
    EpicsProto,
)
from epicsarchiver_mgmt.commands.change_protocol import (
    InvalidEpicsProtoError,
    change_protocol,
    epicsproto_from_str,
)
from epicsarchiver_mgmt.commands.validation import RequestHTTPError


# --- Tests for epicsproto_from_str ---
@pytest.mark.parametrize(
    ("input_str", "expected_type"),
    [
        ("PVA", EpicsProto.PVA),
        ("ca", EpicsProto.CA),
    ],
)
def test_epicsproto_from_str_success(input_str: str, expected_type: EpicsProto) -> None:
    """Test successful conversion from string to epicsproto."""
    assert epicsproto_from_str(input_str) == expected_type


def test_epicsproto_from_str_invalid() -> None:
    """Test conversion with an invalid type string."""
    invalid_type = "INVALID_TYPE"
    with pytest.raises(InvalidEpicsProtoError) as exc_info:
        epicsproto_from_str(invalid_type)
    assert exc_info.value.protocol == invalid_type
    assert f"Invalid epics protocol {invalid_type}" in str(exc_info.value)


# --- Tests for change_protocol ---
def test_change_protocol_success(caplog: pytest.LogCaptureFixture) -> None:
    """Test successful change_protocol operation."""
    caplog.set_level(logging.INFO)
    archiver_fqdn = "archiver.example.com"
    pvs = ["PV1", "PV2"]
    pv_requests = [
        ArchivePVRequest(pv="pva://PV1", samplingperiod="1", appliance="appliance1"),
        ArchivePVRequest(pv="pva://PV2", samplingperiod="1", appliance="appliance1"),
    ]
    protocol = EpicsProto.PVA
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    existing_status = [
        {"pvName": "PV1", "status": "Paused", "appliance": "appliance1", "samplingPeriod": "1"},
        {"pvName": "PV2", "status": "Paused", "appliance": "appliance1", "samplingPeriod": "1"},
    ]
    mock_archiver_info.get_pv_status.return_value = existing_status

    with (
        patch("epicsarchiver_mgmt.commands.change_protocol.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("epicsarchiver_mgmt.commands.change_protocol.ArchiverMgmt", return_value=mock_archiver),
        patch("epicsarchiver_mgmt.commands.change_protocol.validate_pvs_status") as mock_validate_pvs_status,
        patch("epicsarchiver_mgmt.commands.change_protocol.basic_commands.PauseCommand.run_command") as mock_pause,
        patch("epicsarchiver_mgmt.commands.change_protocol.basic_commands.DeleteCommand.run_command") as mock_delete,
        patch("epicsarchiver_mgmt.commands.change_protocol.archive.archive") as mock_archive,
    ):
        change_protocol(archiver_fqdn, pvs, protocol)

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
        assert f"Changing protocol of the PVs {pvs} to {protocol}" in caplog.text
        assert f"Using archiver {mock_archiver.info}" in caplog.text


def test_change_protocol_http_error_on_archive(caplog: pytest.LogCaptureFixture) -> None:
    """Test change_protocol operation with HTTP error during the change_protocol API call."""
    caplog.set_level(logging.DEBUG)
    archiver_fqdn = "archiver.example.com"
    pvs = ["PV1"]
    pv_requests = [
        ArchivePVRequest(pv="pva://PV1", samplingperiod="1", appliance="appliance1"),
    ]
    protocol = EpicsProto.PVA
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
        patch("epicsarchiver_mgmt.commands.change_protocol.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("epicsarchiver_mgmt.commands.change_protocol.ArchiverMgmt", return_value=mock_archiver),
        patch("epicsarchiver_mgmt.commands.change_protocol.validate_pvs_status") as mock_validate_pvs_status,
        patch("epicsarchiver_mgmt.commands.change_protocol.basic_commands.PauseCommand.run_command") as mock_pause,
        patch("epicsarchiver_mgmt.commands.change_protocol.basic_commands.DeleteCommand.run_command") as mock_delete,
        patch("epicsarchiver_mgmt.commands.change_protocol.archive.archive", side_effect=archive_error) as mock_archive,
    ):
        with pytest.raises(RequestHTTPError) as exc_info:
            change_protocol(archiver_fqdn, pvs, protocol)

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


def test_change_protocol_error_on_pause(caplog: pytest.LogCaptureFixture) -> None:
    """Test change_protocol operation when pause fails."""
    caplog.set_level(logging.DEBUG)
    archiver_fqdn = "archiver.example.com"
    pvs = ["PV1"]
    protocol = EpicsProto.PVA
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
        patch("epicsarchiver_mgmt.commands.change_protocol.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("epicsarchiver_mgmt.commands.change_protocol.ArchiverMgmt", return_value=mock_archiver),
        patch("epicsarchiver_mgmt.commands.change_protocol.validate_pvs_status") as mock_validate_pvs_status,
        patch(
            "epicsarchiver_mgmt.commands.change_protocol.basic_commands.PauseCommand.run_command",
            side_effect=pause_error,
        ) as mock_pause,
        patch("epicsarchiver_mgmt.commands.change_protocol.basic_commands.DeleteCommand.run_command") as mock_delete,
        patch("epicsarchiver_mgmt.commands.change_protocol.archive.archive") as mock_archive,
    ):
        with pytest.raises(RequestHTTPError) as exc_info:
            change_protocol(archiver_fqdn, pvs, protocol)

        mock_validate_pvs_status.assert_called_once()
        mock_pause.assert_called_once_with(archiver_fqdn, pvs)
        mock_delete.assert_not_called()
        mock_archive.assert_not_called()
        assert exc_info.value is pause_error  # Check it's the exact exception from pause


def test_change_protocol_error_on_delete(caplog: pytest.LogCaptureFixture) -> None:
    """Test change_protocol operation when delete fails."""
    caplog.set_level(logging.DEBUG)
    archiver_fqdn = "archiver.example.com"
    pvs = ["PV1"]
    protocol = EpicsProto.PVA
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
        patch("epicsarchiver_mgmt.commands.change_protocol.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("epicsarchiver_mgmt.commands.change_protocol.ArchiverMgmt", return_value=mock_archiver),
        patch("epicsarchiver_mgmt.commands.change_protocol.validate_pvs_status") as mock_validate_pvs_status,
        patch("epicsarchiver_mgmt.commands.change_protocol.basic_commands.PauseCommand.run_command") as mock_pause,
        patch(
            "epicsarchiver_mgmt.commands.change_protocol.basic_commands.DeleteCommand.run_command",
            side_effect=delete_error,
        ) as mock_delete,
        patch("epicsarchiver_mgmt.commands.change_protocol.archive.archive") as mock_archive,
    ):
        with pytest.raises(RequestHTTPError) as exc_info:
            change_protocol(archiver_fqdn, pvs, protocol)

        mock_validate_pvs_status.assert_called_once()
        mock_pause.assert_called_once_with(archiver_fqdn, pvs)
        mock_delete.assert_called_once_with(archiver_fqdn, pvs)
        mock_archive.assert_not_called()
        assert exc_info.value is delete_error  # Check it's the exact exception from delete
