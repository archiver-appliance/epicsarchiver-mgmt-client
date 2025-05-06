import logging
from collections.abc import Callable
from typing import cast
from unittest.mock import MagicMock, call, patch

import pytest
from archmgmt.commands.pause_resume import pause, resume
from archmgmt.commands.validation import RequestHTTPError
from archmgmt.mgmt.archiver import (
    ArchiverMgmt,
    OperationResult,
)
from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus
from requests import HTTPError, Response


def test_pause_success(caplog: pytest.LogCaptureFixture) -> None:
    """Test successful pause operation."""
    caplog.set_level(logging.INFO)
    archiver_fqdn = "archiver.example.com"
    pvs = ["PV1", "PV2"]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    # Simulate the list comprehension result
    mock_pause_results = [
        OperationResult(pv="PV1", statusCode=200, statusMessage="OK"),
        OperationResult(pv="PV2", statusCode=200, statusMessage="OK"),
    ]
    # Make the mock iterable and return specific results for each call
    mock_archiver.pause_pv.side_effect = mock_pause_results

    with (
        patch("archiver_mgmt_operations.commands.pause_resume.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("archiver_mgmt_operations.commands.pause_resume.ArchiverMgmtOperations", return_value=mock_archiver),
        patch("archiver_mgmt_operations.commands.pause_resume.validate_pvs_status") as mock_validate_pvs_status,
        patch(
            "archiver_mgmt_operations.commands.pause_resume.validate_operation_results"
        ) as mock_validate_operation_results,
    ):
        pause(archiver_fqdn, pvs)

        mock_validate_pvs_status.assert_called_once_with(
            mock_archiver_info,
            pvs,
            [
                ArchivingStatus.BeingArchived,
                ArchivingStatus.NotBeingArchived,
                ArchivingStatus.Paused,
            ],
        )
        # Check that pause_pv was called for each PV
        mock_archiver.pause_pv.assert_has_calls([call("PV1"), call("PV2")], any_order=False)
        # Check the validation call with the cast results
        mock_validate_operation_results.assert_called_once_with(
            pvs, [cast("OperationResult", result) for result in mock_pause_results], "paused"
        )
        assert f"Pausing PVs {pvs}" in caplog.text
        assert f"Using archiver {mock_archiver.info}" in caplog.text


def test_resume_success(caplog: pytest.LogCaptureFixture) -> None:
    """Test successful resume operation."""
    caplog.set_level(logging.INFO)
    archiver_fqdn = "archiver.example.com"
    pvs = ["PV1", "PV2"]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    # Simulate the list comprehension result
    mock_resume_results = [
        OperationResult(pv="PV1", statusCode=200, statusMessage="OK"),
        OperationResult(pv="PV2", statusCode=200, statusMessage="OK"),
    ]
    # Make the mock iterable and return specific results for each call
    mock_archiver.resume_pv.side_effect = mock_resume_results

    with (
        patch("archiver_mgmt_operations.commands.pause_resume.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("archiver_mgmt_operations.commands.pause_resume.ArchiverMgmtOperations", return_value=mock_archiver),
        patch("archiver_mgmt_operations.commands.pause_resume.validate_pvs_status") as mock_validate_pvs_status,
        patch(
            "archiver_mgmt_operations.commands.pause_resume.validate_operation_results"
        ) as mock_validate_operation_results,
    ):
        resume(archiver_fqdn, pvs)

        mock_validate_pvs_status.assert_called_once_with(
            mock_archiver_info,
            pvs,
            [
                ArchivingStatus.Paused,
            ],
        )
        # Check that resume_pv was called for each PV
        mock_archiver.resume_pv.assert_has_calls([call("PV1"), call("PV2")], any_order=False)
        # Check the validation call with the cast results
        mock_validate_operation_results.assert_called_once_with(
            pvs, [cast("OperationResult", result) for result in mock_resume_results], "resumed"
        )
        assert f"Resuming PVs {pvs}" in caplog.text
        assert f"Using archiver {mock_archiver.info}" in caplog.text


@pytest.mark.parametrize(
    ("func_to_test", "api_method_name", "expected_statuses", "operation_name"),
    [
        (
            pause,
            "pause_pv",
            [
                ArchivingStatus.BeingArchived,
                ArchivingStatus.NotBeingArchived,
                ArchivingStatus.Paused,
            ],
            "pausing",
        ),
        (
            resume,
            "resume_pv",
            [
                ArchivingStatus.Paused,
            ],
            "resuming",
        ),
    ],
)
def test_raise_http_error(
    func_to_test: Callable[[str, list[str]], None],
    api_method_name: str,
    expected_statuses: list[ArchivingStatus],
    operation_name: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test pause/resume operation with HTTP error during API call."""
    caplog.set_level(logging.DEBUG)
    archiver_fqdn = "archiver.example.com"
    pvs = ["PV1"]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    request_response = Response()
    request_response.status_code = 500
    request_response.reason = "Internal Server Error"
    http_error = HTTPError(response=request_response)
    # Simulate error during the list comprehension by setting side_effect on the relevant method
    setattr(mock_archiver, api_method_name, MagicMock(side_effect=http_error))

    with (
        patch("archiver_mgmt_operations.commands.pause_resume.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("archiver_mgmt_operations.commands.pause_resume.ArchiverMgmtOperations", return_value=mock_archiver),
        patch("archiver_mgmt_operations.commands.pause_resume.validate_pvs_status") as mock_validate_pvs_status,
        patch(
            "archiver_mgmt_operations.commands.pause_resume.validate_operation_results"
        ) as mock_validate_operation_results,
    ):
        with pytest.raises(RequestHTTPError) as exc_info:
            func_to_test(archiver_fqdn, pvs)

        mock_validate_pvs_status.assert_called_once_with(
            mock_archiver_info,
            pvs,
            expected_statuses,
        )
        # The API method should have been called once before raising the error
        getattr(mock_archiver, api_method_name).assert_called_once_with("PV1")
        mock_validate_operation_results.assert_not_called()
        assert f"Error {operation_name} PVs" in caplog.text
        assert str(http_error) in caplog.text  # Check if the original error message is logged
        assert exc_info.value.__cause__ is http_error
