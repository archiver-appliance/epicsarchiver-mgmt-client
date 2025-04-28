from unittest.mock import MagicMock

import pytest
from epicsarchiver.mgmt.archiver_mgmt_info import ArchivingStatus

from archiver_mgmt_operations.commands.validation import (
    ValidOperationResultsError,
    ValidPVStatusError,
    validate_operation_results,
    validate_pvs_status,
)


def test_validate_operation_results_success() -> None:
    pvs = ["pv1", "pv2"]
    action_results = [{"status": "ok"}, {"status": "ok"}]
    operation_name = "test_operation"

    # Should not raise an exception
    validate_operation_results(pvs, action_results, operation_name)


def test_validate_operation_results_failure() -> None:
    pvs = ["pv1", "pv2"]
    action_results = [{"status": "ok"}, {"status": "error"}]
    operation_name = "test_operation"

    with pytest.raises(ValidOperationResultsError, match="Operation results for test_operation were not valid"):
        validate_operation_results(pvs, action_results, operation_name)


def test_validate_pvs_status_success(mocker: MagicMock) -> None:
    archiver_info = mocker.MagicMock()
    archiver_info.get_archiving_status.side_effect = [ArchivingStatus.BeingArchived, ArchivingStatus.Paused]
    pvs = ["pv1", "pv2"]
    expected_statuses = [ArchivingStatus.BeingArchived, ArchivingStatus.Paused]

    # Should not raise an exception
    validate_pvs_status(archiver_info, pvs, expected_statuses)


def test_validate_pvs_status_failure(mocker: MagicMock) -> None:
    archiver_info = mocker.MagicMock()
    archiver_info.get_archiving_status.side_effect = [ArchivingStatus.BeingArchived, ArchivingStatus.NotBeingArchived]
    pvs = ["pv1", "pv2"]
    expected_statuses = [ArchivingStatus.BeingArchived, ArchivingStatus.Paused]

    with pytest.raises(ValidPVStatusError, match=r"PV pv2 archiving status is ArchivingStatus.NotBeingArchived"):
        validate_pvs_status(archiver_info, pvs, expected_statuses)
