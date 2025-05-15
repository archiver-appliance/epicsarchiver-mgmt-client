"""Basic commands to modify PVs in the archiver."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus
from requests import HTTPError

from epicsarchiver_mgmt.archiver.mgmt import (
    ArchiverMgmt,
    OperationResult,
    OperationResultList,
)
from epicsarchiver_mgmt.commands.validation import (
    RequestHTTPError,
    validate_operation_results,
    validate_pvs_status,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

LOG: logging.Logger = logging.getLogger(__name__)


def _basic_command(
    command_name: str,
    command: Callable[[ArchiverMgmt, str], OperationResult | OperationResultList],
    expected_statuses: list[ArchivingStatus],
    archiver_fqdn: str,
    pvs: Sequence[str],
) -> None:
    """Basic command to modify PVs in the archiver.

    Args:
        command_name (str): The name of the command.
        command (Callable): The command to execute.
        expected_statuses (list[ArchivingStatus]): The expected statuses of the PVs.
        archiver_fqdn (str): The url of the archiver.
        pvs (list[str]): The PVs to change.

    Raises:
        RequestHTTPError: If there is an error changing the PVs.
    """
    # Validate input
    archiver_info = ArchiverMgmtInfo(archiver_fqdn)
    validate_pvs_status(archiver_info, pvs, expected_statuses)

    # Action
    LOG.info("%s PVs %s", command_name, pvs)

    archiver = ArchiverMgmt(archiver_fqdn)

    LOG.info("Using archiver %s", archiver.info)

    try:
        command_results = [command(archiver, pv) for pv in pvs]
    except HTTPError as e:
        LOG.error("Error %s PVs: %s", command_name, str(e))  # noqa: TRY400
        LOG.debug("Error %s PVs.", command_name, exc_info=True)
        raise RequestHTTPError(e) from e

    # Validate output
    validate_operation_results(
        pvs, [cast("OperationResult", result) for result in command_results], f"{command_name} done"
    )


def pause(archiver_fqdn: str, pvs: Sequence[str]) -> None:
    """Pause PVs in the archiver.

    Args:
        archiver_fqdn (str): The url of the archiver.
        pvs (list[str]): The PVs to pause.
    """
    expected_statues = [
        ArchivingStatus.BeingArchived,
        ArchivingStatus.NotBeingArchived,
        ArchivingStatus.Paused,
    ]
    _basic_command(
        "Pausing",
        lambda archiver, pv: archiver.pause_pv(pv),
        expected_statues,
        archiver_fqdn,
        pvs,
    )


def resume(archiver_fqdn: str, pvs: Sequence[str]) -> None:
    """The resume command to resume PVs.

    Args:
        archiver_fqdn (str): The fully qualified domain name of the archiver.
        pvs (list[str]): The PVs to resume.
    """
    expected_statues = [
        ArchivingStatus.Paused,
    ]
    _basic_command(
        "Resuming",
        lambda archiver, pv: archiver.resume_pv(pv),
        expected_statues,
        archiver_fqdn,
        pvs,
    )


def delete(archiver_fqdn: str, pvs: Sequence[str]) -> None:
    """Delete PVs in the archiver.

    Args:
        archiver_fqdn (str): The url of the archiver.
        pvs (list[str]): The PVs to delete.
    """
    expected_statues = [
        ArchivingStatus.Paused,
    ]
    _basic_command(
        "Deleting",
        lambda archiver, pv: archiver.delete_pv(pv),
        expected_statues,
        archiver_fqdn,
        pvs,
    )
