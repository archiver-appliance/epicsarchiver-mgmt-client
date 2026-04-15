"""Change the type of the pv being archived."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import click
from requests import HTTPError

from epicsarchiver_mgmt.archiver.info import ArchiverMgmtInfo, ArchivingStatus
from epicsarchiver_mgmt.archiver.mgmt import (
    ArchiverMgmt,
)
from epicsarchiver_mgmt.commands import basic_commands
from epicsarchiver_mgmt.commands.validation import (
    CONFIRMATION_PROMPT,
    RequestHTTPError,
    validate_operation_results,
    validate_pvs_status,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from epicsarchiver_mgmt.archiver.mgmt import ArchDbrType

LOG: logging.Logger = logging.getLogger(__name__)


def change_type(archiver_fqdn: str, pvs: Sequence[str], new_type: ArchDbrType) -> None:
    """Change the type of PVs in the archiver.

    Args:
        archiver_fqdn (str): The url of the archiver.
        pvs (list[str]): The PVs to change type.
        new_type (ArchDbrType): The new type to change to.

    Raises:
        RequestHTTPError: If there is an error changing the type of the PVs.
    """
    # Validate input
    archiver_info = ArchiverMgmtInfo(archiver_fqdn)
    validate_pvs_status(
        archiver_info,
        pvs,
        [
            ArchivingStatus.BeingArchived,
            ArchivingStatus.Paused,
        ],
    )

    archiver = ArchiverMgmt(archiver_fqdn)

    basic_commands.PauseCommand().run_command([archiver_fqdn], pvs)
    # Action
    LOG.info("Changing type of the PVs %s to %s", pvs, new_type)

    LOG.info("Using archiver %s", archiver.info)

    click.confirm(CONFIRMATION_PROMPT, abort=True)

    try:
        change_type_results = [archiver.change_type(pv, new_type) for pv in pvs]
    except HTTPError as e:
        LOG.error("Error changing type of PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error changing type of PVs.", exc_info=True)
        raise RequestHTTPError(e) from e

    # Validate output
    validate_operation_results(pvs, change_type_results, "change type")
    basic_commands.ResumeCommand().run_command([archiver_fqdn], pvs)
