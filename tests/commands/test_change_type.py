import logging
from typing import cast
from unittest.mock import MagicMock, call, patch

import pytest
from epicsarchiver.common import ArchDbrType
from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus
from requests import HTTPError, Response

from archmgmt.commands.change_type import (
    InvalidArchDbrTypeError,
    archdbrtype_from_str,
    change_type,
)
from archmgmt.commands.validation import RequestHTTPError
from archmgmt.mgmt.archiver import (
    ArchiverMgmt,
    OperationResult,
)


# --- Tests for archdbrtype_from_str ---
@pytest.mark.parametrize(
    ("input_str", "expected_type"),
    [
        ("DBR_SCALAR_SHORT", ArchDbrType.DBR_SCALAR_SHORT),
        ("dbr_scalar_double", ArchDbrType.DBR_SCALAR_DOUBLE),
    ],
)
def test_archdbrtype_from_str_success(input_str: str, expected_type: ArchDbrType) -> None:
    """Test successful conversion from string to ArchDbrType."""
    assert archdbrtype_from_str(input_str) == expected_type


def test_archdbrtype_from_str_invalid() -> None:
    """Test conversion with an invalid type string."""
    invalid_type = "INVALID_TYPE"
    with pytest.raises(InvalidArchDbrTypeError) as exc_info:
        archdbrtype_from_str(invalid_type)
    assert exc_info.value.new_type == invalid_type
    assert f"Invalid arch dbr type {invalid_type}" in str(exc_info.value)


# --- Tests for change_type ---
def test_change_type_success(caplog: pytest.LogCaptureFixture) -> None:
    """Test successful change_type operation."""
    caplog.set_level(logging.INFO)
    archiver_fqdn = "archiver.example.com"
    pvs = ["PV1", "PV2"]
    new_type = ArchDbrType.DBR_SCALAR_DOUBLE
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    # Simulate the list comprehension result for change_type
    mock_change_results = [
        OperationResult(pv="PV1", statusCode=200, statusMessage="OK"),
        OperationResult(pv="PV2", statusCode=200, statusMessage="OK"),
    ]
    # Make the mock iterable and return specific results for each call
    mock_archiver.change_type.side_effect = mock_change_results

    with (
        patch("archmgmt.commands.change_type.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("archmgmt.commands.change_type.ArchiverMgmt", return_value=mock_archiver),
        patch("archmgmt.commands.change_type.validate_pvs_status") as mock_validate_pvs_status,
        patch("archmgmt.commands.change_type.pause_resume.pause") as mock_pause,
        patch("archmgmt.commands.change_type.pause_resume.resume") as mock_resume,
        patch("archmgmt.commands.change_type.validate_operation_results") as mock_validate_operation_results,
    ):
        change_type(archiver_fqdn, pvs, new_type)

        mock_validate_pvs_status.assert_called_once_with(
            mock_archiver_info,
            pvs,
            [
                ArchivingStatus.BeingArchived,
                ArchivingStatus.Paused,
            ],
        )
        mock_pause.assert_called_once_with(archiver_fqdn, pvs)
        # Check that change_type was called for each PV
        mock_archiver.change_type.assert_has_calls([call("PV1", new_type), call("PV2", new_type)], any_order=False)
        # Check the validation call with the cast results
        mock_validate_operation_results.assert_called_once_with(
            pvs, [cast("OperationResult", result) for result in mock_change_results], "change type"
        )
        mock_resume.assert_called_once_with(archiver_fqdn, pvs)
        assert f"Changing type of the PVs {pvs} to {new_type}" in caplog.text
        assert f"Using archiver {mock_archiver.info}" in caplog.text


def test_change_type_http_error_on_change(caplog: pytest.LogCaptureFixture) -> None:
    """Test change_type operation with HTTP error during the change_type API call."""
    caplog.set_level(logging.DEBUG)
    archiver_fqdn = "archiver.example.com"
    pvs = ["PV1"]
    new_type = ArchDbrType.DBR_SCALAR_DOUBLE
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    request_response = Response()
    request_response.status_code = 500
    request_response.reason = "Internal Server Error"
    http_error = HTTPError(response=request_response)
    # Simulate error during the list comprehension for change_type
    mock_archiver.change_type.side_effect = http_error

    with (
        patch("archmgmt.commands.change_type.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("archmgmt.commands.change_type.ArchiverMgmt", return_value=mock_archiver),
        patch("archmgmt.commands.change_type.validate_pvs_status") as mock_validate_pvs_status,
        patch("archmgmt.commands.change_type.pause_resume.pause") as mock_pause,
        patch("archmgmt.commands.change_type.pause_resume.resume") as mock_resume,
        patch("archmgmt.commands.change_type.validate_operation_results") as mock_validate_operation_results,
    ):
        with pytest.raises(RequestHTTPError) as exc_info:
            change_type(archiver_fqdn, pvs, new_type)

        mock_validate_pvs_status.assert_called_once_with(
            mock_archiver_info,
            pvs,
            [
                ArchivingStatus.BeingArchived,
                ArchivingStatus.Paused,
            ],
        )
        mock_pause.assert_called_once_with(archiver_fqdn, pvs)
        # change_type should have been called once before raising the error
        mock_archiver.change_type.assert_called_once_with("PV1", new_type)
        mock_validate_operation_results.assert_not_called()
        mock_resume.assert_not_called()  # Resume should not be called if change fails
        assert "Error changing type of PVs" in caplog.text
        assert str(http_error) in caplog.text  # Check if the original error message is logged
        assert "Error changing type of PVs." in caplog.text  # Check debug log message
        assert exc_info.value.__cause__ is http_error


def test_change_type_error_on_pause(caplog: pytest.LogCaptureFixture) -> None:
    """Test change_type operation when pause fails."""
    caplog.set_level(logging.DEBUG)
    archiver_fqdn = "archiver.example.com"
    pvs = ["PV1"]
    new_type = ArchDbrType.DBR_SCALAR_DOUBLE
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    request_response = Response()
    request_response.status_code = 400
    request_response.reason = "Bad Request"
    http_error = HTTPError(response=request_response)
    pause_error = RequestHTTPError(http_error)  # Simulate error raised by pause

    with (
        patch("archmgmt.commands.change_type.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("archmgmt.commands.change_type.ArchiverMgmt", return_value=mock_archiver),
        patch("archmgmt.commands.change_type.validate_pvs_status") as mock_validate_pvs_status,
        patch("archmgmt.commands.change_type.pause_resume.pause", side_effect=pause_error) as mock_pause,
        patch("archmgmt.commands.change_type.pause_resume.resume") as mock_resume,
        patch("archmgmt.commands.change_type.validate_operation_results") as mock_validate_operation_results,
    ):
        with pytest.raises(RequestHTTPError) as exc_info:
            change_type(archiver_fqdn, pvs, new_type)

        mock_validate_pvs_status.assert_called_once()
        mock_pause.assert_called_once_with(archiver_fqdn, pvs)
        mock_archiver.change_type.assert_not_called()
        mock_validate_operation_results.assert_not_called()
        mock_resume.assert_not_called()
        assert exc_info.value is pause_error  # Check it's the exact exception from pause


def test_change_type_error_on_resume(caplog: pytest.LogCaptureFixture) -> None:
    """Test change_type operation when resume fails."""
    caplog.set_level(logging.DEBUG)
    archiver_fqdn = "archiver.example.com"
    pvs = ["PV1"]
    new_type = ArchDbrType.DBR_SCALAR_DOUBLE
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    mock_change_results = [OperationResult(pv="PV1", statusCode=200, statusMessage="OK")]
    mock_archiver.change_type.side_effect = mock_change_results

    request_response = Response()
    request_response.status_code = 503
    request_response.reason = "Service Unavailable"
    http_error = HTTPError(response=request_response)
    resume_error = RequestHTTPError(http_error)  # Simulate error raised by resume

    with (
        patch("archmgmt.commands.change_type.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("archmgmt.commands.change_type.ArchiverMgmt", return_value=mock_archiver),
        patch("archmgmt.commands.change_type.validate_pvs_status") as mock_validate_pvs_status,
        patch("archmgmt.commands.change_type.pause_resume.pause") as mock_pause,
        patch("archmgmt.commands.change_type.pause_resume.resume", side_effect=resume_error) as mock_resume,
        patch("archmgmt.commands.change_type.validate_operation_results") as mock_validate_operation_results,
    ):
        with pytest.raises(RequestHTTPError) as exc_info:
            change_type(archiver_fqdn, pvs, new_type)

        mock_validate_pvs_status.assert_called_once()
        mock_pause.assert_called_once_with(archiver_fqdn, pvs)
        mock_archiver.change_type.assert_called_once_with("PV1", new_type)
        mock_validate_operation_results.assert_called_once()
        mock_resume.assert_called_once_with(archiver_fqdn, pvs)
        assert exc_info.value is resume_error  # Check it's the exact exception from resume
