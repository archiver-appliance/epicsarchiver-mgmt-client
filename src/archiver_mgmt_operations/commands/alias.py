"""Add aliases to PVs in the archiver."""

from __future__ import annotations

import logging
from itertools import starmap

from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus
from requests import HTTPError

from archiver_mgmt_operations.commands.validation import (
    RequestHTTPError,
    validate_not_same,
    validate_operation_results,
    validate_pvs_status,
)
from archiver_mgmt_operations.mgmt.archiver_mgmt_operations import (
    ArchiverMgmtOperations,
)

LOG: logging.Logger = logging.getLogger(__name__)


def add_aliases(archiver_fqdn: str, alias_maps: list[tuple[str, str]]) -> None:
    """Add aliases to PVs in the archiver.

    Args:
        archiver_fqdn (str): The url of the archiver.
        alias_maps (list[tuple[str, str]]): The PVs to rename.

    Raises:
        RequestHTTPError: If there is an error renaming the PVs.
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

    archiver = ArchiverMgmtOperations(archiver_fqdn)

    LOG.info("Using archiver %s", archiver.info)

    try:
        add_alias_results = list(starmap(archiver.add_alias, alias_maps))

    except HTTPError as e:
        LOG.error("Error adding alias PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error adding alias PVs.", exc_info=True)
        raise RequestHTTPError(e) from e

    # Validate output
    validate_operation_results(
        [alias_pv for _original_pv, alias_pv in alias_maps],
        add_alias_results,
        "added alaises",
    )
