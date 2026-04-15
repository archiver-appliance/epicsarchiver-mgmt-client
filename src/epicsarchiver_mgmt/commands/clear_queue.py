"""Rearchive a pv to update the policy."""

from __future__ import annotations

import datetime
import enum
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from dateutil.parser import parse

from epicsarchiver_mgmt.archiver.mgmt import (
    ArchiverMgmt,
)
from epicsarchiver_mgmt.commands import basic_commands
from epicsarchiver_mgmt.exceptions import BaseMgmtError

if TYPE_CHECKING:
    from epicsarchiver_mgmt.archiver.info import InfoResultList

LOG: logging.Logger = logging.getLogger(__name__)


CURRENT_STATE = "currentState"


class ArchivingState(enum.Enum):
    """Archiving state of a PV in the queue."""

    START = enum.auto()
    """
    Start is the start of the archiving workflow.
    """
    ARCHIVE_REQUEST_SUBMITTED = enum.auto()
    """
    Request has been submitted to the archiver.
    """
    METAINFO_GATHERING = enum.auto()
    """
    Reading data from the PV to decide archiving policy.
    """
    UNKNOWN = enum.auto()
    """
    Unknown state.
    """

    @classmethod
    def from_str(cls, state: str) -> ArchivingState:
        """Convert a string to an ArchivingState.

        Args:
            state (str): The string to convert.

        Returns:
            ArchivingState: The ArchivingState.
        """
        for s in ArchivingState:
            if s.name == state:
                return s
        return ArchivingState.UNKNOWN


@dataclass
class NeverConnectedPV:
    """Response struct from never connected pvs."""

    request_time: datetime.datetime | None
    appliance: str
    pv_name: str
    current_state: ArchivingState
    start_of_workflow: datetime.datetime


DATE_FORMAT = "%b/%d/%Y %H:%M:%S %Z"


def get_never_connected_pvs(archiver: ArchiverMgmt) -> list[NeverConnectedPV]:
    """Get Never connected pvs from archiver.

    Args:
        archiver (ArchiverMgmt): The archiver management instance.

    Returns:
        list[NeverConnectedPV]: List of Never connected pvs.
    """
    queue_info: InfoResultList = archiver.never_connected_pvs
    return [
        NeverConnectedPV(
            request_time=parse(item["requestTime"]) if item["requestTime"] and item["requestTime"] != "N/A" else None,
            appliance=item["appliance"],
            pv_name=item["pvName"],
            current_state=ArchivingState.from_str(item[CURRENT_STATE]),
            start_of_workflow=parse(item["startOfWorkflow"]),
        )
        for item in queue_info
    ]


def abort_pvs_in_queue(pvs: list[str], archiver: ArchiverMgmt, chunking: int = 1000) -> set[str]:
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
        basic_commands.AbortCommand().run_command([archiver.hostname], list(chunk), skip_validation=True)
        out.update(chunk)

    return out


class QueueFilter(enum.Enum):
    """Filter for the queue."""

    ALL = enum.auto()
    START = enum.auto()
    METAINFO_GATHERING = enum.auto()
    ARCHIVING = enum.auto()


class OldTimeValueError(BaseMgmtError):
    """Custom exception for when old_time is required but not provided."""

    def __init__(self, queue_filter: QueueFilter) -> None:
        """Initialize the OldTimeValueError.

        Args:
            queue_filter (QueueFilter): The filter that requires old_time.
        """
        super().__init__(f"old_time must be provided for the {queue_filter.name} filter")


def filter_queue_by_state(
    archiver: ArchiverMgmt,
    queue_info: list[NeverConnectedPV],
    queue_filter: QueueFilter,
    old_time: datetime.timedelta | None,
) -> list[str]:
    """Filter the queue by state.

    Args:
        archiver (ArchiverMgmt): The archiver management instance.
        queue_info (list[NeverConnectedPV]): The queue information.
        queue_filter (QueueFilter): The filter to apply.
        old_time (datetime.timedelta | None): The time after which a PV is considered stuck.

    Returns:
        list[NeverConnectedPV]: The filtered queue information.

    Raises:
        OldTimeValueError: If old_time is required but not provided.
    """
    if queue_filter == QueueFilter.ALL:
        return [item.pv_name for item in queue_info]
    if queue_filter in {QueueFilter.METAINFO_GATHERING, QueueFilter.START}:
        if old_time is None:
            raise OldTimeValueError(queue_filter)
        return [
            item.pv_name
            for item in queue_info
            if item.start_of_workflow < datetime.datetime.now(tz=datetime.UTC) - old_time
            and item.current_state == ArchivingState.from_str(queue_filter.name)
        ]
    if queue_filter == QueueFilter.ARCHIVING:
        return archiver.get_archived_pvs([item.pv_name for item in queue_info])
    return []


def clear_queue(archiver_fqdn: str, queue_filter: QueueFilter, old_time: datetime.timedelta | None) -> None:
    """Clear the queue of the archiver.

    Args:
        archiver_fqdn (str): The url of the archiver.
        queue_filter (QueueFilter): The filter to apply.
        old_time (timedelta | None): The time after which a PV is considered stuck.
    """
    archiver = ArchiverMgmt(archiver_fqdn)
    queue_info = get_never_connected_pvs(archiver)
    if not queue_info:
        LOG.info("The queue is empty, nothing to clear.")
        return
    # Action
    filtered_pvs = filter_queue_by_state(archiver, queue_info, queue_filter, old_time)
    if not filtered_pvs:
        LOG.info("No PVs for filter %s found in the queue.", queue_filter.name)
        return
    LOG.info("PVs being archived in the queue: %s", filtered_pvs)
    abort_pvs_in_queue(filtered_pvs, archiver)
    LOG.info("Queue cleared successfully.")
