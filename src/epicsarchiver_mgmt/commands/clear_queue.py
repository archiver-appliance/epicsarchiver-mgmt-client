"""Rearchive a pv to update the policy."""

from __future__ import annotations

import logging

from epicsarchiver.mgmt.archiver_mgmt_info import ArchivingStatus, InfoResultList

from epicsarchiver_mgmt.archiver.mgmt import (
    ArchiverMgmt,
)
from epicsarchiver_mgmt.commands import basic_commands

LOG: logging.Logger = logging.getLogger(__name__)


CURRENT_STATE = "currentState"
START_STATE = "START"
SUBMIT_STATE = "ARCHIVE_REQUEST_SUBMITTED"


def abort_archiving_pvs_in_queue(pvs: list[str], archiver: ArchiverMgmt, chunking: int = 1000) -> set[str]:
    """Get the list of PVs that are currently being archived in the queue and abort them.

    Args:
        pvs (list[str]): List of PV names to check.
        archiver (ArchiverMgmt): The archiver management instance.
        chunking (int): Number of PVs to check in each request to the archiver.

    Returns:
        list[str]: List of PV names that are currently being archived.
    """
    out: set[str] = set()
    for i in range(0, len(pvs), chunking):
        chunk = pvs[i : i + chunking]
        LOG.debug("Checking PVs in chunk: %s", chunk)
        pv_statuses = archiver.get_pv_status(",".join(chunk))

        if not pv_statuses:
            LOG.warning("No PV statuses found for chunk: %s", chunk)
            continue
        archiving_pvs = {
            pv_status["pvName"]
            for pv_status in pv_statuses
            if ArchivingStatus.from_str(pv_status["status"]) == ArchivingStatus.BeingArchived
        }
        if archiving_pvs:
            basic_commands.AbortCommand().run_command(archiver.hostname, list(archiving_pvs), skip_validation=True)
            out.update(archiving_pvs)

    return out


def clear_queue(archiver_fqdn: str) -> None:
    """Clear the queue of the archiver.

    Args:
        archiver_fqdn (str): The url of the archiver.
    """
    # Validate input

    archiver = ArchiverMgmt(archiver_fqdn)
    queue_info: InfoResultList = archiver.never_connected_pvs

    if not queue_info:
        LOG.info("The queue is empty, nothing to clear.")
        return
    # Action
    pvs = [item["pvName"] for item in queue_info if item[CURRENT_STATE] in {START_STATE, SUBMIT_STATE}]
    LOG.debug("PVs in the queue: %s", pvs)
    archiving_pvs = abort_archiving_pvs_in_queue(pvs, archiver)
    if not archiving_pvs:
        LOG.info("No PVs were being archived in the queue.")
        return
    LOG.info("PVs being archived in the queue: %s", archiving_pvs)
    LOG.info("Queue cleared successfully.")
