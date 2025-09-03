import io
from unittest.mock import MagicMock

import pytest
from epicsarchiver.mgmt.archiver_mgmt_info import ArchivingStatus

from epicsarchiver_mgmt.commands.validation import (
    DifferentArchiverClusterError,
    NotSamePVError,
    ValidOperationResultsError,
    ValidPVStatusError,
    validate_archiver_fqdns,
    validate_not_same,
    validate_operation_results,
    validate_pvs_status,
)


def accept_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))


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
    archiver_info.get_pv_status.return_value = [
        {"pvName": "pv1", "status": ArchivingStatus.BeingArchived.value},
        {"pvName": "pv2", "status": ArchivingStatus.Paused.value},
    ]
    pvs = ["pv1", "pv2"]
    expected_statuses = [ArchivingStatus.BeingArchived, ArchivingStatus.Paused]

    # Should not raise an exception
    validate_pvs_status(archiver_info, pvs, expected_statuses)


def test_validate_pvs_status_failure(mocker: MagicMock) -> None:
    archiver_info = mocker.MagicMock()
    archiver_info.get_pv_status.return_value = [
        {"pvName": "pv1", "status": ArchivingStatus.BeingArchived.value},
        {"pvName": "pv2", "status": ArchivingStatus.NotBeingArchived.value},
    ]
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


def test_validate_archiver_fqdns_success(mocker: MagicMock) -> None:
    archiver_mgmt = mocker.MagicMock()
    archiver_mgmt.info = {"identity": "archiver1"}
    archiver_mgmt.appliances_in_cluster = [
        {
            "identity": "archiver1",
        }
    ]
    mocker.patch("epicsarchiver_mgmt.commands.validation.ArchiverMgmt", return_value=archiver_mgmt)

    validate_archiver_fqdns(["archiver1.example.com", "archiver2.example.com"])
    validate_archiver_fqdns(["archiver1.example.com"])


def test_validate_archiver_fqdns_failure(mocker: MagicMock) -> None:
    archiver_mgmt = mocker.MagicMock()
    archiver_mgmt.info = {"identity": "archiver1"}
    archiver_mgmt.appliances_in_cluster = [
        {
            "identity": "archiver2",
        }
    ]
    mocker.patch("epicsarchiver_mgmt.commands.validation.ArchiverMgmt", return_value=archiver_mgmt)

    with pytest.raises(DifferentArchiverClusterError):
        validate_archiver_fqdns(["archiver1.example.com", "archiver2.example.com"])
