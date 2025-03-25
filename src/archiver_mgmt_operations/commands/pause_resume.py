from __future__ import annotations

import logging

from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus

from archiver_mgmt_operations.mgmt.archiver_mgmt_operations import (
    ArchiverMgmtOperations,
    OperationResult,
    OperationResultList,
)
from archiver_mgmt_operations.mgmt_exception import BaseMgmtError

LOG: logging.Logger = logging.getLogger(__name__)

OPERATION_RESULT_STATUS = "status"


class ValidOperationResultsError(BaseMgmtError):
    """Exception for when the operation results are not valid."""

    def __init__(self, action_results: dict[str, OperationResult | OperationResultList], operation_name: str) -> None:
        super().__init__(f"Operation results for {operation_name} were not valid for PVs {action_results.keys()}.")
        self.action_results = action_results
        self.operation_name = operation_name


def validate_operation_results(
    pvs: list[str],
    action_results: list[OperationResult | OperationResultList],
    operation_name: str,
) -> None:
    invalid_pvs: dict[str, OperationResult | OperationResultList] = {}
    for pv, result in zip(pvs, action_results):
        LOG.debug("PV %s result %s for operation %s", pv, result, operation_name)
        if isinstance(result, dict) and result.get(OPERATION_RESULT_STATUS, "false") != "ok":
            invalid_pvs[pv] = result
    if not invalid_pvs:
        raise ValidOperationResultsError(invalid_pvs, operation_name)


class ValidPVStatusError(BaseMgmtError):
    """Exception for when a PV is not in the expected status."""

    def __init__(self, pv: str, archiving_status: ArchivingStatus | None) -> None:
        super().__init__(f"PV {pv} is {archiving_status}.")


def validate_pvs_status(
    archiver_info: ArchiverMgmtInfo,
    pvs: list[str],
    expected_statuses: list[ArchivingStatus],
) -> None:
    for pv in pvs:
        archiving_status = archiver_info.get_archiving_status(pv)
        LOG.debug("PV %s has status %s", pv, archiving_status)
        if archiving_status not in expected_statuses:
            raise ValidPVStatusError(pv, archiving_status)


def pause(archiver_fqdn: str, pvs: list[str]) -> None:
    # Validate input
    archiver_info = ArchiverMgmtInfo(archiver_fqdn)
    validate_pvs_status(
        archiver_info,
        pvs,
        [
            ArchivingStatus.BeingArchived,
            ArchivingStatus.NotBeingArchived,
        ],
    )

    # Action
    LOG.info("Pausing PVs %s", pvs)
    archiver = ArchiverMgmtOperations(archiver_fqdn)
    LOG.info("Using archiver %s", archiver.info)
    pause_results = [archiver.pause_pv(pv) for pv in pvs]

    # Validate output
    validate_operation_results(pvs, pause_results, "paused")
