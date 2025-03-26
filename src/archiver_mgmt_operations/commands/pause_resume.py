"""Pause or resume archiving."""

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
        """Error for when the operation results are not valid.

        Args:
            action_results (dict[str, OperationResult  |  OperationResultList]): The results of the operation.
            operation_name (str): The name of the operation.
        """
        super().__init__(f"Operation results for {operation_name} were not valid for PVs {action_results.keys()}.")
        self.action_results = action_results
        self.operation_name = operation_name


def validate_operation_results(
    pvs: list[str],
    action_results: list[OperationResult | OperationResultList],
    operation_name: str,
) -> None:
    """Validate the results of an operation.

    Args:
        pvs (list[str]): The PVs that were acted on.
        action_results (list[OperationResult  |  OperationResultList]): The results of the operation.
        operation_name (str): The name of the operation.

    Raises:
        ValidOperationResultsError: If the results are not valid.
    """
    invalid_pvs: dict[str, OperationResult | OperationResultList] = {}
    for pv, result in zip(pvs, action_results, strict=False):
        LOG.debug("PV %s result %s for operation %s", pv, result, operation_name)
        if isinstance(result, dict) and result.get(OPERATION_RESULT_STATUS, "false") != "ok":
            invalid_pvs[pv] = result
    if not invalid_pvs:
        raise ValidOperationResultsError(invalid_pvs, operation_name)


class ValidPVStatusError(BaseMgmtError):
    """Exception for when a PV is not in the expected status."""

    def __init__(self, pv: str, archiving_status: ArchivingStatus | None) -> None:
        """Initialize the exception.

        Args:
            pv (str): The PV that is not in the expected status.
            archiving_status (ArchivingStatus | None): The status of the PV.
        """
        super().__init__(f"PV {pv} is {archiving_status}.")


def validate_pvs_status(
    archiver_info: ArchiverMgmtInfo,
    pvs: list[str],
    expected_statuses: list[ArchivingStatus],
) -> None:
    """Validate the status of PVs.

    Args:
        archiver_info (ArchiverMgmtInfo): The archiver management server.
        pvs (list[str]): The PVs to validate.
        expected_statuses (list[ArchivingStatus]): The allowed statuses for the PVs.

    Raises:
        ValidPVStatusError: If a PV is not in the expected status.
    """
    for pv in pvs:
        archiving_status = archiver_info.get_archiving_status(pv)
        LOG.debug("PV %s has status %s", pv, archiving_status)
        if archiving_status not in expected_statuses:
            raise ValidPVStatusError(pv, archiving_status)


def pause(archiver_fqdn: str, pvs: list[str]) -> None:
    """Pause PVs in the archiver.

    Args:
        archiver_fqdn (str): The url of the archiver.
        pvs (list[str]): The PVs to pause.
    """
    # Validate input
    archiver_info = ArchiverMgmtInfo(archiver_fqdn)
    validate_pvs_status(
        archiver_info,
        pvs,
        [
            ArchivingStatus.BeingArchived,
            ArchivingStatus.NotBeingArchived,
            ArchivingStatus.Paused,
        ],
    )

    # Action
    LOG.info("Pausing PVs %s", pvs)
    archiver = ArchiverMgmtOperations(archiver_fqdn)
    LOG.info("Using archiver %s", archiver.info)
    pause_results = [archiver.pause_pv(pv) for pv in pvs]

    # Validate output
    validate_operation_results(pvs, pause_results, "paused")
