"""Pause or resume archiving."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus, InfoResultList

from epicsarchiver_mgmt.archiver.mgmt import (
    ArchivePVRequest,
    ArchiverMgmt,
    EpicsProto,
)
from epicsarchiver_mgmt.commands import archive, delete, pause_resume
from epicsarchiver_mgmt.commands.validation import (
    validate_current_protocol,
    validate_pvs_status,
)
from epicsarchiver_mgmt.mgmt_exception import BaseMgmtError

if TYPE_CHECKING:
    from collections.abc import Sequence

LOG: logging.Logger = logging.getLogger(__name__)


class InvalidEpicsProtoError(BaseMgmtError):
    """Exception for when the epics protocol is invalid."""

    def __init__(self, new_protocol: str) -> None:
        """Error for when the rename type is invalid.

        Args:
            new_protocol (str): The invalid epics protocol.
        """
        super().__init__(f"Invalid epics protocol {new_protocol}.")
        self.new_protocol = new_protocol


def epicsproto_from_str(value: str) -> EpicsProto:
    """Convert a string to a EpicsProto.

    Args:
        value (str): The value to convert.

    Returns:
        EpicsProto: The EpicsProto.

    Raises:
        InvalidEpicsProtoError: If the value is invalid.
    """
    for t in EpicsProto:
        if t.name.lower() == value.lower():
            return t
    raise InvalidEpicsProtoError(value)


def statuses_archive_requests(pv_statuses: InfoResultList, new_protocol: EpicsProto) -> list[ArchivePVRequest]:
    """Copy the archive requests from the PV statuses.

    Args:
        pv_statuses (InfoResultList): The statuses of the PVs.
        new_protocol (EpicsProto): The new protocol to change to.

    Returns:
        list[ArchivePVRequest]: The archive requests of the PVs.
    """
    return [
        ArchivePVRequest(
            new_protocol.pv_name(pv_status["pvName"]),
            appliance=pv_status["appliance"],
            samplingperiod=pv_status["samplingPeriod"],
        )
        for pv_status in pv_statuses
    ]


def change_protocol(archiver_fqdn: str, pvs: Sequence[str], new_protocol: EpicsProto) -> None:
    """Change the protocol of PVs in the archiver.

    Args:
        archiver_fqdn (str): The url of the archiver.
        pvs (list[str]): The PVs to change type.
        new_protocol (EpicsProto): The new protocol to change to.
    """
    # Validate input
    archiver_info = ArchiverMgmtInfo(archiver_fqdn)
    pv_statuses: InfoResultList = archiver_info.get_pv_status(list(pvs))
    validate_pvs_status(
        archiver_info,
        pvs,
        [
            ArchivingStatus.BeingArchived,
            ArchivingStatus.Paused,
        ],
        pv_statuses,
    )
    validate_current_protocol(archiver_info, pvs, new_protocol)

    pv_requests = statuses_archive_requests(pv_statuses, new_protocol)
    archiver = ArchiverMgmt(archiver_fqdn)

    # Action
    LOG.info("Changing protocol of the PVs %s to %s", pvs, new_protocol)
    pause_resume.pause(archiver_fqdn, pvs)
    delete.delete(archiver_fqdn, pvs)
    archive.archive(archiver_fqdn, pv_requests, dry_run=False)

    LOG.info("Using archiver %s", archiver.info)

    # Validate output
    validate_pvs_status(
        archiver_info,
        pvs,
        [
            ArchivingStatus.BeingArchived,
        ],
    )
