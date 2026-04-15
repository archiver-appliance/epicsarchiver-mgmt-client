"""Add aliases to PVs in the archiver."""

from __future__ import annotations

import logging
from itertools import starmap
from typing import TYPE_CHECKING

from requests import HTTPError

from epicsarchiver_mgmt.archiver.info import ArchiverMgmtInfo, ArchivingStatus
from epicsarchiver_mgmt.archiver.mgmt import (
    ArchiverMgmt,
)
from epicsarchiver_mgmt.commands.validation import (
    RequestHTTPError,
    validate_not_same,
    validate_operation_results,
    validate_pvs_status,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

LOG: logging.Logger = logging.getLogger(__name__)


def add_aliases(archiver_fqdn: str, alias_maps: Sequence[tuple[str, str]]) -> None:
    """Add aliases to PVs in the archiver.

    Args:
        archiver_fqdn (str): The url of the archiver.
        alias_maps (list[tuple[str, str]]): The PVs to add aliases.

    Raises:
        RequestHTTPError: If there is an error aliasing the PVs.
    """
    # Validate input
    archiver_info = ArchiverMgmtInfo(archiver_fqdn)
    validate_not_same(alias_maps)
    validate_pvs_status(
        archiver_info,
        [original_pv for original_pv, _alias_pv in alias_maps],
        [
            ArchivingStatus.BeingArchived,
            ArchivingStatus.Paused,
        ],
    )
    validate_pvs_status(
        archiver_info,
        [alias_pv for _original_pv, alias_pv in alias_maps],
        [
            ArchivingStatus.NotBeingArchived,
        ],
    )

    # Action
    LOG.info("Adding aliases for PVs %s", alias_maps)

    archiver = ArchiverMgmt(archiver_fqdn)

    LOG.info("Using archiver %s", archiver.info)

    try:
        add_alias_results = list(starmap(archiver.add_alias, alias_maps))

    except HTTPError as e:
        LOG.error("Error adding alias PVs: %s", e)  # noqa: TRY400
        LOG.debug("Error adding alias PVs.", exc_info=True)
        raise RequestHTTPError(e) from e

    # Validate output
    validate_operation_results(
        [alias_pv for _original_pv, alias_pv in alias_maps],
        add_alias_results,
        "Added Alaises",
    )


def remove_aliases(archiver_fqdn: str, alias_maps: Sequence[tuple[str, str]]) -> None:
    """Remove aliases from PVs in the archiver.

    Args:
        archiver_fqdn (str): The url of the archiver.
        alias_maps (list[tuple[str, str]]): The PVs to remove aliases.

    Raises:
        RequestHTTPError: If there is an error aliasing the PVs.
    """
    # Validate input
    archiver_info = ArchiverMgmtInfo(archiver_fqdn)
    validate_not_same(alias_maps)
    validate_pvs_status(
        archiver_info,
        [original_pv for original_pv, _alias_pv in alias_maps],
        [
            ArchivingStatus.BeingArchived,
            ArchivingStatus.Paused,
        ],
    )
    validate_pvs_status(
        archiver_info,
        [alias_pv for _original_pv, alias_pv in alias_maps],
        [
            ArchivingStatus.BeingArchived,
            ArchivingStatus.Paused,
        ],
    )

    # Action
    LOG.info("Removing aliases for PVs %s", alias_maps)

    archiver = ArchiverMgmt(archiver_fqdn)

    LOG.info("Using archiver %s", archiver.info)

    try:
        remove_alias_results = list(starmap(archiver.remove_alias, alias_maps))

    except HTTPError as e:
        LOG.error("Error removing alias PVs: %s", e)  # noqa: TRY400
        LOG.debug("Error removing alias PVs.", exc_info=True)
        raise RequestHTTPError(e) from e

    # Validate output
    validate_operation_results(
        [original_pv for original_pv, _alias_pv in alias_maps],
        remove_alias_results,
        "Removed alaises",
    )
