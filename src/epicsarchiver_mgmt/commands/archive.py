"""Provides the archive command to archive PVs."""

from __future__ import annotations

import logging

from requests import HTTPError

from epicsarchiver_mgmt.archiver.info import ArchiverMgmtInfo, ArchivingStatus
from epicsarchiver_mgmt.archiver.mgmt import (
    ArchivePVRequest,
    ArchiverMgmt,
)
from epicsarchiver_mgmt.commands.validation import (
    OPERATION_RESULT_STATUS,
    RequestHTTPError,
    validate_operation_results,
    validate_pvs_status,
)
from epicsarchiver_mgmt.exceptions import BaseMgmtError

LOG: logging.Logger = logging.getLogger(__name__)


class ArchivePolicyNotFoundError(BaseMgmtError):
    """Exception for when the policy is not found."""

    def __init__(self, pv_request: ArchivePVRequest, policy_names: set[str]) -> None:
        """Error for when the policy is not found.

        Args:
            pv_request (ArchivePVRequest): The PV request
            policy_names (set[str]): The available policy names.
        """
        super().__init__(f"Policy {pv_request.policy} not found in {policy_names} for archive request {pv_request.pv}.")
        self.pv_request = pv_request
        self.policy_names = policy_names


def validate_policy_names(archiver: ArchiverMgmt, pv_requests: list[ArchivePVRequest]) -> None:
    """Validate the policy names.

    Args:
        archiver (ArchiverMgmt): The archiver information.
        pv_requests (list[ArchivePVRequest]): The PVs to archive.

    Raises:
        ArchivePolicyNotFoundError: If the policy is not found.
    """
    policy_names = archiver.get_policy_list().keys()
    for request in pv_requests:
        if request.policy and request.policy not in policy_names:
            raise ArchivePolicyNotFoundError(request, set(policy_names))


ARCHIVE_OPERATION_RESULT_STATUS_OK = "Archive request submitted"
ARCHIVE_OPERATION_EXPECTED_STATUS = {OPERATION_RESULT_STATUS: [ARCHIVE_OPERATION_RESULT_STATUS_OK]}


def archive(archiver_fqdn: str, pv_requests: list[ArchivePVRequest], *, dry_run: bool = False) -> None:
    """Provide the archive command to archive PVs.

    Args:
        archiver_fqdn (str): The fully qualified domain name of the archiver.
        pv_requests (list[ArchivePVRequest]): The PVs to archive.
        dry_run (bool): Whether to do a dry run or not.

    Raises:
       RequestHTTPError: If there is an error archiving the PVs.
    """
    pvs = [request.pv for request in pv_requests]
    # Validate input
    archiver_info = ArchiverMgmtInfo(archiver_fqdn)
    validate_pvs_status(
        archiver_info=archiver_info,
        pvs=pvs,
        expected_statuses=[
            ArchivingStatus.NotBeingArchived,
        ],
    )
    archiver = ArchiverMgmt(archiver_fqdn)
    validate_policy_names(archiver, pv_requests)

    # Action
    LOG.info("Archiving PVs %s", pv_requests)
    LOG.info("Using archiver %s", archiver.info)

    if dry_run:
        LOG.info("Dry run, not executing.")
        return

    try:
        archive_results = archiver.archive_pv_requests(pv_requests)
    except HTTPError as e:
        LOG.error("Error archiving PVs: %s", e)  # noqa: TRY400
        LOG.debug("Error archiving PVs.", exc_info=True)
        raise RequestHTTPError(e) from e

    # Validate output
    validate_operation_results(
        pvs,
        archive_results,
        "archived",
        expected_operation_results=ARCHIVE_OPERATION_EXPECTED_STATUS,
    )
