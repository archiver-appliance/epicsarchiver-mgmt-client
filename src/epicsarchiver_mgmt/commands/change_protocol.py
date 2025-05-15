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
from epicsarchiver_mgmt.commands import archive, basic_commands, delete
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

    def __init__(self, protocol: str) -> None:
        """Error for when the rename type is invalid.

        Args:
            protocol (str): The invalid epics protocol.
        """
        super().__init__(f"Invalid epics protocol {protocol}.")
        self.protocol = protocol


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
            samplingperiod=pv_status["samplingPeriod"],
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
    validate_current_protocol(archiver_info, pvs, protocol)

    pv_requests = create_new_protocol_archive_requests(pv_statuses, protocol)
    archiver = ArchiverMgmt(archiver_fqdn)

    # Action
    LOG.info("Using archiver %s", archiver.info)
    LOG.info("Changing protocol of the PVs %s to %s", pvs, protocol)
    basic_commands.pause(archiver_fqdn, pvs)
    delete.delete(archiver_fqdn, pvs)
    archive.archive(archiver_fqdn, pv_requests, dry_run=False)
