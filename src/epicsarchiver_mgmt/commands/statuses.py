"""Get the status of a pv."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus, InfoResultList

if TYPE_CHECKING:
    from collections.abc import Sequence

LOG: logging.Logger = logging.getLogger(__name__)


def get_statuses(
    archiver_fqdn: str, pvs: Sequence[str], filter_statuses: list[ArchivingStatus] | None = None
) -> list[str]:
    """Get the statues and print them.

    Args:
        archiver_fqdn (str): The url of the archiver.
        pvs (list[str]): The PVs to get status.
        filter_statuses (list[ArchivingStatus] | None): Filter the PVs by status.

    Returns:
        list[str]: The PVs that match the filter.
    """
    # Validate input
    filter_statuses_str = [] if filter_statuses is None else [status.value for status in filter_statuses]
    archiver_info = ArchiverMgmtInfo(archiver_fqdn)
    pv_statuses: InfoResultList = archiver_info.get_pv_status(",".join(pvs))
    filtered_pvs = []
    for pv_status in pv_statuses:
        if not filter_statuses or pv_status["status"] in filter_statuses_str:
            LOG.info("Status: %s, PV: %s", pv_status["status"], pv_status["pvName"])
            filtered_pvs.append(pv_status["pvName"])
        else:
            LOG.debug("Skipping PV %s with status %s", pv_status["pvName"], pv_status["status"])
    return filtered_pvs
