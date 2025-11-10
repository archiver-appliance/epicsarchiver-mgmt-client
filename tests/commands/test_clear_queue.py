import datetime
import logging
from unittest.mock import MagicMock, patch

import pytest
from requests import HTTPError, Response

from epicsarchiver_mgmt.archiver.mgmt import ArchiverMgmt
from epicsarchiver_mgmt.commands.clear_queue import (
    ArchivingState,
    NeverConnectedPV,
    QueueFilter,
    clear_queue,
)
from epicsarchiver_mgmt.commands.validation import RequestHTTPError


@pytest.fixture
def mock_archiver_mgmt() -> MagicMock:
    """Fixture for a mocked ArchiverMgmt instance."""
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.hostname = "mock.archiver.host"
    return mock_archiver


NOW = datetime.datetime.now(tz=datetime.UTC)
START_TIME_DELTA = datetime.timedelta(hours=1)
METAINFO_TIME_DELTA = datetime.timedelta(minutes=30)


@pytest.mark.parametrize(
    ("queue_filter", "old_time", "queue_info", "get_archived_pvs_return", "mock_now", "expected_aborted_pvs"),
    [
        (
            QueueFilter.ALL,
            None,
            [
                NeverConnectedPV(
                    request_time=NOW,
                    appliance="test",
                    pv_name="PV1",
                    current_state=ArchivingState.START,
                    start_of_workflow=NOW,
                ),
                NeverConnectedPV(
                    request_time=NOW,
                    appliance="test",
                    pv_name="PV2",
                    current_state=ArchivingState.ARCHIVE_REQUEST_SUBMITTED,
                    start_of_workflow=NOW,
                ),
            ],
            None,
            None,
            ["PV1", "PV2"],
        ),
        (
            QueueFilter.START,
            START_TIME_DELTA,
            [
                NeverConnectedPV(
                    request_time=NOW - START_TIME_DELTA * 2,
                    appliance="test",
                    pv_name="PV1",
                    current_state=ArchivingState.START,
                    start_of_workflow=NOW - START_TIME_DELTA * 2,
                ),
                NeverConnectedPV(
                    request_time=NOW,
                    appliance="test",
                    pv_name="PV2",
                    current_state=ArchivingState.START,
                    start_of_workflow=NOW,
                ),
            ],
            None,
            NOW,
            ["PV1"],
        ),
        (
            QueueFilter.METAINFO_GATHERING,
            METAINFO_TIME_DELTA,
            [
                NeverConnectedPV(
                    request_time=NOW,
                    appliance="test",
                    pv_name="PV1",
                    current_state=ArchivingState.METAINFO_GATHERING,
                    start_of_workflow=NOW - METAINFO_TIME_DELTA * 2,
                ),
                NeverConnectedPV(
                    request_time=NOW,
                    appliance="test",
                    pv_name="PV2",
                    current_state=ArchivingState.METAINFO_GATHERING,
                    start_of_workflow=NOW,
                ),
                NeverConnectedPV(
                    request_time=NOW,
                    appliance="test",
                    pv_name="PV3",
                    current_state=ArchivingState.START,
                    start_of_workflow=NOW - METAINFO_TIME_DELTA * 2,
                ),
            ],
            None,
            NOW,
            ["PV1"],
        ),
        (
            QueueFilter.ARCHIVING,
            None,
            [
                NeverConnectedPV(
                    request_time=None,
                    appliance="test",
                    pv_name="PV1",
                    current_state=ArchivingState.START,
                    start_of_workflow=NOW,
                ),
                NeverConnectedPV(
                    request_time=None,
                    appliance="test",
                    pv_name="PV2",
                    current_state=ArchivingState.ARCHIVE_REQUEST_SUBMITTED,
                    start_of_workflow=NOW,
                ),
            ],
            ["PV1"],
            None,
            ["PV1"],
        ),
        (
            QueueFilter.ALL,
            None,
            [],
            None,
            None,
            [],
        ),
    ],
)
def test_clear_queue_successfully(
    caplog: pytest.LogCaptureFixture,
    mock_archiver_mgmt: MagicMock,
    queue_filter: QueueFilter,
    old_time: datetime.timedelta | None,
    queue_info: list[NeverConnectedPV],
    get_archived_pvs_return: list[str] | None,
    mock_now: datetime.datetime | None,
    expected_aborted_pvs: list[str],
) -> None:
    """Test clear_queue with different filters."""
    caplog.set_level(logging.INFO)
    archiver_fqdn = "archiver.example.com"

    if get_archived_pvs_return is not None:
        mock_archiver_mgmt.get_archived_pvs.return_value = get_archived_pvs_return

    with (
        patch(
            "epicsarchiver_mgmt.commands.clear_queue.ArchiverMgmt", return_value=mock_archiver_mgmt
        ) as mock_mgmt_class,
        patch(
            "epicsarchiver_mgmt.commands.clear_queue.get_never_connected_pvs", return_value=queue_info
        ) as mock_get_never_connected_pvs,
        patch("epicsarchiver_mgmt.commands.clear_queue.abort_pvs_in_queue") as mock_abort_pvs_in_queue,
        patch("epicsarchiver_mgmt.commands.clear_queue.datetime") as mock_datetime,
    ):
        if mock_now:
            # We need to mock datetime.datetime within the module, not the global one
            mock_datetime.datetime.now.return_value = mock_now
            mock_datetime.UTC = datetime.UTC

        clear_queue(archiver_fqdn, queue_filter, old_time=old_time)

        mock_mgmt_class.assert_called_once_with(archiver_fqdn)
        mock_get_never_connected_pvs.assert_called_once_with(mock_archiver_mgmt)

        if not queue_info:
            assert "The queue is empty, nothing to clear." in caplog.text
            mock_abort_pvs_in_queue.assert_not_called()
            return

        if expected_aborted_pvs:
            mock_abort_pvs_in_queue.assert_called_once()
            call_args = mock_abort_pvs_in_queue.call_args[0][0]
            assert sorted(call_args) == sorted(expected_aborted_pvs)
            assert f"PVs being archived in the queue: {expected_aborted_pvs}" in caplog.text
            assert "Queue cleared successfully." in caplog.text
            assert "No PVs were being archived in the queue." not in caplog.text
        else:
            mock_abort_pvs_in_queue.assert_not_called()
            assert "No PVs were being archived in the queue." in caplog.text
            assert "Queue cleared successfully." not in caplog.text


def test_clear_queue_http_error_on_abort_command(
    caplog: pytest.LogCaptureFixture, mock_archiver_mgmt: MagicMock
) -> None:
    """Test clear_queue when AbortCommand().run_command raises an HTTP error."""
    caplog.set_level(logging.DEBUG)
    archiver_fqdn = "archiver.example.com"

    queue_info = [
        NeverConnectedPV(
            request_time=NOW,
            appliance="test",
            pv_name="PV1",
            current_state=ArchivingState.START,
            start_of_workflow=NOW,
        )
    ]

    http_error_response = Response()
    http_error_response.status_code = 500
    http_error_response.reason = "Internal Server Error"
    http_error = HTTPError(response=http_error_response)
    abort_command_error = RequestHTTPError(http_error)

    with (
        patch("epicsarchiver_mgmt.commands.clear_queue.ArchiverMgmt", return_value=mock_archiver_mgmt),
        patch("epicsarchiver_mgmt.commands.clear_queue.get_never_connected_pvs", return_value=queue_info),
        patch("epicsarchiver_mgmt.commands.clear_queue.abort_pvs_in_queue") as mock_abort_pvs_in_queue,
    ):
        mock_abort_pvs_in_queue.side_effect = abort_command_error

        with pytest.raises(RequestHTTPError) as exc_info:
            clear_queue(archiver_fqdn, queue_filter=QueueFilter.ALL, old_time=None)

        assert exc_info.value is abort_command_error
        mock_abort_pvs_in_queue.assert_called_once_with(["PV1"], mock_archiver_mgmt)
        # Check that the final success logs are not present
        assert "Queue cleared successfully." not in caplog.text
