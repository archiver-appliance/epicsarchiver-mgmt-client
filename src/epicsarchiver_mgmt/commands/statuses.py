"""Get the status of a pv."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, InfoResultList

if TYPE_CHECKING:
    from collections.abc import Sequence

LOG: logging.Logger = logging.getLogger(__name__)


MAX_PVS = 1000


def get_statuses_from_archiver(archiver_info: ArchiverMgmtInfo, pvs: Sequence[str]) -> InfoResultList:
    """Get the statuses of PVs from the archiver.

    Fetches the statuses in chunks to avoid URL length limits.

    Args:
        archiver_info (ArchiverMgmtInfo): The archiver info to use.
        pvs (list[str]): The PVs to get status.

    Returns:
        InfoResultList: The statuses of the PVs.
    """
    pv_statuses: InfoResultList = []
    for i in range(0, len(pvs), MAX_PVS):
        validate_pvs = pvs[i : i + MAX_PVS]
        pv_temp_statuses = archiver_info.get_pv_status(",".join(validate_pvs))
        pv_statuses.extend(pv_temp_statuses)
    return pv_statuses


def get_statuses(archiver_fqdn: str, pvs: Sequence[str]) -> dict[str, list[str]]:
    """Get the statues and print them.

    Args:
        archiver_fqdn (str): The url of the archiver.
        pvs (list[str]): The PVs to get status.

    Returns:
        dict[str, list[str]] : The PVs that match the filter.
    """
    # Validate input
    archiver_info = ArchiverMgmtInfo(archiver_fqdn)
    pv_statuses = get_statuses_from_archiver(archiver_info, pvs)
    statuses_to_pvs: dict[str, list[str]] = {}
    for pv_status in pv_statuses:
        if pv_status["status"] not in statuses_to_pvs:
            statuses_to_pvs[pv_status["status"]] = []
        LOG.debug(
            "PV: %s, Status: %s",
            pv_status["pvName"],
            pv_status["status"],
        )
        statuses_to_pvs[pv_status["status"]].append(pv_status["pvName"])
    return statuses_to_pvs
