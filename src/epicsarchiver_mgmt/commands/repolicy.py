"""Pause or resume archiving."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus, InfoResultList

from epicsarchiver_mgmt.archiver.mgmt import (
    ArchivePVRequest,
    ArchiverMgmt,
)
from epicsarchiver_mgmt.commands import archive, basic_commands
from epicsarchiver_mgmt.commands.validation import (
    validate_pvs_status,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

LOG: logging.Logger = logging.getLogger(__name__)


def create_new_archive_requests(pv_statuses: InfoResultList) -> list[ArchivePVRequest]:
    """Create the archive requests from the appliance names in the pv statuses and new protocol.

    Args:
        pv_statuses (InfoResultList): The statuses of the PVs.

    Returns:
        list[ArchivePVRequest]: The archive requests of the PVs.
    """
    return [
        ArchivePVRequest(
            pv_status["pvName"],
            appliance=pv_status["appliance"],
        )
        for pv_status in pv_statuses
    ]


def repolicy(archiver_fqdn: str, pvs: Sequence[str]) -> None:
    """Re do the policy of pvs in arhiver.

    Args:
        archiver_fqdn (str): The url of the archiver.
        pvs (list[str]): The PVs to change type.
    """
    # Validate input
    archiver_info = ArchiverMgmtInfo(archiver_fqdn)
    pv_statuses: InfoResultList = archiver_info.get_pv_status(list(pvs))
    validate_pvs_status(
        archiver_info=archiver_info,
        pvs=pvs,
        expected_statuses=[
            ArchivingStatus.BeingArchived,
            ArchivingStatus.Paused,
        ],
        existing_status_infos=pv_statuses,
    )

    pv_requests = create_new_archive_requests(pv_statuses)
    archiver = ArchiverMgmt(archiver_fqdn)

    # Action
    LOG.info("Using archiver %s", archiver.info)
    LOG.info("Re doing policy of the PVs %s", pvs)
    basic_commands.PauseCommand().run_command(archiver_fqdn, pvs)
    basic_commands.DeleteCommand().run_command(archiver_fqdn, pvs)
    archive.archive(archiver_fqdn, pv_requests, dry_run=False)
