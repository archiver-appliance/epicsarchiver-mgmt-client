"""Pause or resume archiving."""

from __future__ import annotations

import logging
from typing import cast

from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus
from requests import HTTPError

from archiver_mgmt_operations.commands.validation import (
    RequestHTTPError,
    validate_operation_results,
    validate_pvs_status,
)
from archiver_mgmt_operations.mgmt.archiver_mgmt_operations import (
    ArchiverMgmtOperations,
    OperationResult,
)

LOG: logging.Logger = logging.getLogger(__name__)


def pause(archiver_fqdn: str, pvs: list[str]) -> None:
    """Pause PVs in the archiver.

    Args:
        archiver_fqdn (str): The url of the archiver.
        pvs (list[str]): The PVs to pause.

    Raises:
        RequestHTTPError: If there is an error pausing the PVs.
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

    try:
        pause_results = [archiver.pause_pv(pv) for pv in pvs]
    except HTTPError as e:
        LOG.error("Error pausing PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error pausing PVs.", exc_info=True)
        raise RequestHTTPError(e) from e

    # Validate output
    validate_operation_results(pvs, [cast("OperationResult", result) for result in pause_results], "paused")


def resume(archiver_fqdn: str, pvs: list[str]) -> None:
    """The resume command to resume PVs.

    Args:
        archiver_fqdn (str): The fully qualified domain name of the archiver.
        pvs (list[str]): The PVs to resume.

    Raises:
        RequestHTTPError: If there is an error resuming the PVs.
    """
    # Validate input
    archiver_info = ArchiverMgmtInfo(archiver_fqdn)
    validate_pvs_status(
        archiver_info,
        pvs,
        [
            ArchivingStatus.Paused,
        ],
    )

    # Action
    LOG.info("Resuming PVs %s", pvs)
    archiver = ArchiverMgmtOperations(archiver_fqdn)
    LOG.info("Using archiver %s", archiver.info)

    try:
        resume_results = [archiver.resume_pv(pv) for pv in pvs]
    except HTTPError as e:
        LOG.error("Error resuming PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error resuming PVs.", exc_info=True)
        raise RequestHTTPError(e) from e

    # Validate output
    validate_operation_results(pvs, [cast("OperationResult", result) for result in resume_results], "resumed")
