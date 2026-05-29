"""Change the archiving protocol in use."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from epicsarchiver_mgmt.archiver.info import ArchiverMgmtInfo, ArchivingStatus, InfoResultList
from epicsarchiver_mgmt.archiver.mgmt import (
    ArchivePVRequest,
    ArchiverMgmt,
    EpicsProto,
)
from epicsarchiver_mgmt.commands import archive, basic_commands
from epicsarchiver_mgmt.commands.statuses import get_statuses_from_archiver
from epicsarchiver_mgmt.commands.validation import (
    validate_current_protocol,
    validate_pvs_status,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

LOG: logging.Logger = logging.getLogger(__name__)


def create_new_protocol_archive_requests(pv_statuses: InfoResultList, protocol: EpicsProto) -> list[ArchivePVRequest]:
    """Create the archive requests from the appliance names in the pv statuses and new protocol.

    Args:
        pv_statuses (InfoResultList): The statuses of the PVs.
        protocol (EpicsProto): The new protocol to change to.

    Returns:
        list[ArchivePVRequest]: The archive requests of the PVs.
    """
    return [
        ArchivePVRequest(
            protocol.create_archive_request_pv_name(pv_status["pvName"]),
            appliance=pv_status["appliance"],
            samplingperiod=float(pv_status["samplingPeriod"]),
        )
        for pv_status in pv_statuses
    ]


def change_protocol(archiver_fqdn: str, pvs: Sequence[str], protocol: EpicsProto) -> None:
    """Change the protocol of PVs in the archiver.

    Args:
        archiver_fqdn (str): The url of the archiver.
        pvs (list[str]): The PVs to change type.
        protocol (EpicsProto): The new protocol to change to.
    """
    # Validate input
    archiver_info = ArchiverMgmtInfo(archiver_fqdn)
    pv_statuses: InfoResultList = get_statuses_from_archiver(archiver_info, pvs)
    validate_pvs_status(
        archiver_info=archiver_info,
        pvs=pvs,
        expected_statuses=[
            ArchivingStatus.BeingArchived,
            ArchivingStatus.Paused,
        ],
        existing_status_infos=pv_statuses,
    )
    validate_current_protocol(archiver_info, pvs, protocol)

    pv_requests = create_new_protocol_archive_requests(pv_statuses, protocol)
    archiver = ArchiverMgmt(archiver_fqdn)

    # Action
    LOG.info("Using archiver %s", archiver.info)
    LOG.info("Changing protocol of the PVs %s to %s", pvs, protocol)
    basic_commands.PauseCommand().run_command([archiver_fqdn], pvs)
    basic_commands.DeleteCommand().run_command([archiver_fqdn], pvs)
    archive.archive(archiver_fqdn, pv_requests, dry_run=False)
