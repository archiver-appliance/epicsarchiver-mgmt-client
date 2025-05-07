from unittest.mock import MagicMock

import pytest
from epicsarchiver.mgmt.archiver_mgmt_info import ArchivingStatus

from epicsarchiver_mgmt.commands.validation import (
    NotSamePVError,
    ValidOperationResultsError,
    ValidPVStatusError,
    validate_not_same,
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


def test_validate_not_same_success() -> None:
    """Test validate_not_same with valid renames."""
    renames = [("old_pv1", "new_pv1"), ("old_pv2", "new_pv2")]
    validate_not_same(renames)  # Should not raise an exception


def test_validate_not_same_failure() -> None:
    """Test validate_not_same with invalid renames (same old and new PV)."""
    renames = [("old_pv1", "new_pv1"), ("pv1", "pv1")]
    with pytest.raises(NotSamePVError) as exc_info:
        validate_not_same(renames)
    assert str(exc_info.value) == "Old and new PVs are the same for PV pv1."
