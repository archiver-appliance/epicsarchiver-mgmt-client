"""Pause or resume archiving."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus
from requests import HTTPError

from epicsarchiver_mgmt.archiver.mgmt import (
    ArchiverMgmt,
    OperationResult,
)
from epicsarchiver_mgmt.commands.validation import (
    RequestHTTPError,
    validate_operation_results,
    validate_pvs_status,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

LOG: logging.Logger = logging.getLogger(__name__)


def delete(archiver_fqdn: str, pvs: Sequence[str]) -> None:
    """Delete PVs in the archiver.

    Args:
        archiver_fqdn (str): The url of the archiver.
        pvs (list[str]): The PVs to delete.

    Raises:
        RequestHTTPError: If there is an error deleting the PVs.
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
    LOG.info("Deleting PVs %s", pvs)

    archiver = ArchiverMgmt(archiver_fqdn)

    LOG.info("Using archiver %s", archiver.info)

    try:
        delete_results = [archiver.delete_pv(pv) for pv in pvs]
    except HTTPError as e:
        LOG.error("Error deleting PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error deleting PVs.", exc_info=True)
        raise RequestHTTPError(e) from e

    # Validate output
    validate_operation_results(pvs, [cast("OperationResult", result) for result in delete_results], "deleted")
