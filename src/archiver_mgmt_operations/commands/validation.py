"""Provide validation functions for the archiver management operations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from archiver_mgmt_operations.mgmt_exception import BaseMgmtError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus
    from requests import HTTPError

    from archiver_mgmt_operations.mgmt.archiver_mgmt_operations import (
        OperationResult,
        OperationResultList,
    )

LOG: logging.Logger = logging.getLogger(__name__)
OPERATION_RESULT_STATUS = "status"
OPERATION_RESULT_OK = "ok"


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
    pvs: Sequence[str],
    action_results: list[OperationResult] | OperationResultList,
    operation_name: str,
    expected_status: str = OPERATION_RESULT_OK,
) -> None:
    """Validate the results of an operation.

    Args:
        pvs (Sequence[str]): The PVs that were acted on.
        action_results (list[OperationResult  |  OperationResultList]): The results of the operation.
        operation_name (str): The name of the operation.
        expected_status (str, optional): The expected status. Defaults to OPERATION_RESULT_OK.

    Raises:
        ValidOperationResultsError: If the results are not valid.
    """
    invalid_pvs: dict[str, OperationResult | OperationResultList] = {}
    for pv, result in zip(pvs, action_results, strict=False):
        LOG.debug("PV %s result %s for operation %s", pv, result, operation_name)
        if isinstance(result, dict) and result.get(OPERATION_RESULT_STATUS, "false") != expected_status:
            invalid_pvs[pv] = result
    if invalid_pvs != {}:
        raise ValidOperationResultsError(invalid_pvs, operation_name)
    LOG.info("Operation %s succeeded for PVs %s", operation_name, pvs)


class ValidPVStatusError(BaseMgmtError):
    """Exception for when a PV is not in the expected status."""

    def __init__(self, pv: str, archiving_status: ArchivingStatus | None) -> None:
        """Initialize the exception.

        Args:
            pv (str): The PV that is not in the expected status.
            archiving_status (ArchivingStatus | None): The status of the PV.
        """
        super().__init__(f"PV {pv} archiving status is {archiving_status}.")


def validate_pvs_status(
    archiver_info: ArchiverMgmtInfo,
    pvs: Sequence[str],
    expected_statuses: list[ArchivingStatus],
) -> None:
    """Validate the status of PVs.

    Args:
        archiver_info (ArchiverMgmtInfo): The archiver management server.
        pvs (Sequence[str]): The PVs to validate.
        expected_statuses (list[ArchivingStatus]): The allowed statuses for the PVs.

    Raises:
        ValidPVStatusError: If a PV is not in the expected status.
    """
    for pv in pvs:
        archiving_status = archiver_info.get_archiving_status(pv)
        LOG.debug("PV %s has status %s", pv, archiving_status)
        if archiving_status not in expected_statuses:
            raise ValidPVStatusError(pv, archiving_status)


class RequestHTTPError(BaseMgmtError):
    """Exception for when there is an HTTP error."""

    def __init__(self, http_error: HTTPError) -> None:
        """Error for when there is an HTTP error.

        Args:
            http_error (HTTPError): The HTTP error.
        """
        super().__init__(f"HTTP error: {http_error} occurred. {http_error.response.text}")
        self.http_error = http_error
