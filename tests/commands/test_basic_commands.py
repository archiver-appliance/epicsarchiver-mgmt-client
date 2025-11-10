import logging
from unittest.mock import MagicMock, call, patch

import pytest
from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus
from requests import HTTPError, Response

from epicsarchiver_mgmt.archiver.mgmt import (
    ArchiverMgmt,
    OperationResult,
)
from epicsarchiver_mgmt.commands.basic_commands import (
    AbortCommand,
    BasicCommand,
    DeleteCommand,
    PauseCommand,
    ResumeCommand,
)
from epicsarchiver_mgmt.commands.validation import RequestHTTPError


@pytest.mark.parametrize(
    ("command_name", "archiver_command", "basic_command", "expected_statuses", "expected_operation_results"),
    [
        (
            "Pausing",
            "pause_pv",
            PauseCommand(),
            [
                ArchivingStatus.BeingArchived,
                ArchivingStatus.NotBeingArchived,
                ArchivingStatus.Paused,
            ],
            None,
        ),
        (
            "Resuming",
            "resume_pv",
            ResumeCommand(),
            [
                ArchivingStatus.Paused,
            ],
            None,
        ),
        (
            "Deleting",
            "delete_pv",
            DeleteCommand(),
            [
                ArchivingStatus.Paused,
            ],
            None,
        ),
        (
            "Aborting",
            "abort_pv",
            AbortCommand(),
            [ArchivingStatus.BeingArchived, None],
            None,
        ),
    ],
)
def test_basic_command_success(
    command_name: str,
    archiver_command: str,
    basic_command: BasicCommand,
    expected_statuses: list[ArchivingStatus],
    expected_operation_results: list[str] | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test successful command operation."""
    caplog.set_level(logging.INFO)
    archiver_fqdn = "archiver.example.com"
    pvs = ["PV1", "PV2"]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    # Simulate the list comprehension result
    mock_command_results = [
        OperationResult(pv="PV1", statusCode=200, statusMessage="OK"),
        OperationResult(pv="PV2", statusCode=200, statusMessage="OK"),
    ]
    # Make the mock iterable and return specific results for each call
    getattr(mock_archiver, archiver_command).side_effect = mock_command_results

    with (
        patch("epicsarchiver_mgmt.commands.basic_commands.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("epicsarchiver_mgmt.commands.basic_commands.ArchiverMgmt", return_value=mock_archiver),
        patch("epicsarchiver_mgmt.commands.basic_commands.validate_pvs_status") as mock_validate_pvs_status,
        patch(
            "epicsarchiver_mgmt.commands.basic_commands.validate_operation_results"
        ) as mock_validate_operation_results,
    ):
        basic_command.run_command([archiver_fqdn], pvs)
        mock_validate_pvs_status.assert_called_once_with(
            mock_archiver_info,
            pvs,
            expected_statuses,
        )
        # Check that command_pv was called for each PV
        getattr(mock_archiver, archiver_command).assert_has_calls([call("PV1"), call("PV2")], any_order=False)
        # Check the validation call with the cast results
        mock_validate_operation_results.assert_called_once_with(
            pvs, mock_command_results, f"{command_name} done", expected_operation_results=expected_operation_results
        )
        assert f"{command_name} PVs {pvs}" in caplog.text


@pytest.mark.parametrize(
    ("command_name", "archiver_command", "basic_command", "expected_statuses"),
    [
        (
            "Pausing",
            "pause_pv",
            PauseCommand(),
            [
                ArchivingStatus.BeingArchived,
                ArchivingStatus.NotBeingArchived,
                ArchivingStatus.Paused,
            ],
        ),
        (
            "Resuming",
            "resume_pv",
            ResumeCommand(),
            [
                ArchivingStatus.Paused,
            ],
        ),
        (
            "Deleting",
            "delete_pv",
            DeleteCommand(),
            [
                ArchivingStatus.Paused,
            ],
        ),
        (
            "Aborting",
            "abort_pv",
            AbortCommand(),
            [ArchivingStatus.BeingArchived, None],
        ),
    ],
)
def test_raise_http_error(
    command_name: str,
    archiver_command: str,
    basic_command: BasicCommand,
    expected_statuses: list[ArchivingStatus | None],
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
    setattr(mock_archiver, archiver_command, MagicMock(side_effect=http_error))

    with (
        patch("epicsarchiver_mgmt.commands.basic_commands.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("epicsarchiver_mgmt.commands.basic_commands.ArchiverMgmt", return_value=mock_archiver),
        patch("epicsarchiver_mgmt.commands.basic_commands.validate_pvs_status") as mock_validate_pvs_status,
        patch(
            "epicsarchiver_mgmt.commands.basic_commands.validate_operation_results"
        ) as mock_validate_operation_results,
    ):
        with pytest.raises(RequestHTTPError) as exc_info:
            basic_command.run_command([archiver_fqdn], pvs)

        mock_validate_pvs_status.assert_called_once_with(
            mock_archiver_info,
            pvs,
            expected_statuses,
        )
        # The API method should have been called once before raising the error
        getattr(mock_archiver, archiver_command).assert_called_once_with("PV1")
        mock_validate_operation_results.assert_not_called()
        assert f"Error {command_name} PVs" in caplog.text
        assert str(http_error) in caplog.text  # Check if the original error message is logged
        assert exc_info.value.__cause__ is http_error
