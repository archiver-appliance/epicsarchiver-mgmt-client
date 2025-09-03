import logging
from unittest.mock import MagicMock, patch

import pytest
from epicsarchiver.mgmt.archiver_mgmt_info import ArchivingStatus
from requests import HTTPError, Response

from epicsarchiver_mgmt.archiver.mgmt import ArchiverMgmt
from epicsarchiver_mgmt.commands.clear_queue import (
    CURRENT_STATE,
    START_STATE,
    SUBMIT_STATE,
    clear_queue,
)
from epicsarchiver_mgmt.commands.validation import RequestHTTPError


@pytest.fixture
def mock_archiver_mgmt() -> MagicMock:
    """Fixture for a mocked ArchiverMgmt instance."""
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.hostname = "mock.archiver.host"
    return mock_archiver


def test_clear_queue_pvs_aborted_successfully(caplog: pytest.LogCaptureFixture, mock_archiver_mgmt: MagicMock) -> None:
    """Test clear_queue when PVs are found in queue, are being archived, and aborted successfully."""
    caplog.set_level(logging.INFO)
    archiver_fqdn = "archiver.example.com"

    # PVs that will be identified from the queue
    queue_pvs_to_check = ["PV1", "PV2"]
    queue_data = [
        {"pvName": "PV1", CURRENT_STATE: START_STATE},
        {"pvName": "PV2", CURRENT_STATE: SUBMIT_STATE},
        {"pvName": "PV3", CURRENT_STATE: "SOME_OTHER_STATE"},  # This PV won't be processed further
    ]

    # Status for the PVs taken from the queue; PV1 is being archived, PV2 is not.
    pv_status_data = [
        {"pvName": "PV1", "status": ArchivingStatus.BeingArchived.value},
        {"pvName": "PV2", "status": ArchivingStatus.Paused.value},
    ]
    # So, only "PV1" should be aborted.
    expected_aborted_pvs = {"PV1"}

    mock_archiver_mgmt.never_connected_pvs = queue_data
    mock_archiver_mgmt.get_pv_status.return_value = pv_status_data

    with (
        patch(
            "epicsarchiver_mgmt.commands.clear_queue.ArchiverMgmt", return_value=mock_archiver_mgmt
        ) as mock_mgmt_class,
        patch("epicsarchiver_mgmt.commands.clear_queue.basic_commands.AbortCommand.run_command") as mock_abort_command,
    ):
        clear_queue(archiver_fqdn)

        mock_mgmt_class.assert_called_once_with(archiver_fqdn)
        # The list of PVs passed to get_pv_status depends on the order from the set comprehension
        # in clear_queue, so we check the content rather than exact string.
        call_args = mock_archiver_mgmt.get_pv_status.call_args[0][0].split(",")
        assert sorted(call_args) == sorted(queue_pvs_to_check)

        mock_abort_command.assert_called_once()
        mock_abort_command.assert_called_once_with(
            [mock_archiver_mgmt.hostname], list(expected_aborted_pvs), skip_validation=True
        )

        # Check logs with caplog.text for INFO level
        assert f"PVs being archived in the queue: {expected_aborted_pvs}" in caplog.text
        assert "Queue cleared successfully." in caplog.text
        assert "No PVs were being archived in the queue." not in caplog.text


def test_clear_queue_http_error_on_abort_command(
    caplog: pytest.LogCaptureFixture, mock_archiver_mgmt: MagicMock
) -> None:
    """Test clear_queue when AbortCommand().run_command raises an HTTP error."""
    caplog.set_level(logging.DEBUG)
    archiver_fqdn = "archiver.example.com"

    queue_data = [{"pvName": "PV1", CURRENT_STATE: START_STATE}]
    pv_status_data = [{"pvName": "PV1", "status": ArchivingStatus.BeingArchived.value}]
    # PV1 is in queue and being archived, so AbortCommand will be called for it.

    mock_archiver_mgmt.never_connected_pvs = queue_data
    mock_archiver_mgmt.get_pv_status.return_value = pv_status_data

    http_error_response = Response()
    http_error_response.status_code = 500
    http_error_response.reason = "Internal Server Error"
    http_error = HTTPError(response=http_error_response)
    abort_command_error = RequestHTTPError(http_error)

    with (
        patch("epicsarchiver_mgmt.commands.clear_queue.ArchiverMgmt", return_value=mock_archiver_mgmt),
        patch("epicsarchiver_mgmt.commands.clear_queue.basic_commands.AbortCommand.run_command") as mock_abort_command,
    ):
        mock_abort_command.side_effect = abort_command_error

        with pytest.raises(RequestHTTPError) as exc_info:
            clear_queue(archiver_fqdn)

        assert exc_info.value is abort_command_error
        mock_abort_command.assert_called_once_with([mock_archiver_mgmt.hostname], ["PV1"], skip_validation=True)
        # Check that the final success logs are not present
        assert "Queue cleared successfully." not in caplog.text
