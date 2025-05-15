"""Pause or resume archiving."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from epicsarchiver.common import ArchDbrType
from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus
from requests import HTTPError

from epicsarchiver_mgmt.archiver.mgmt import (
    ArchiverMgmt,
    OperationResult,
)
from epicsarchiver_mgmt.commands import basic_commands
from epicsarchiver_mgmt.commands.validation import (
    RequestHTTPError,
    validate_operation_results,
    validate_pvs_status,
)
from epicsarchiver_mgmt.mgmt_exception import BaseMgmtError

if TYPE_CHECKING:
    from collections.abc import Sequence

LOG: logging.Logger = logging.getLogger(__name__)


class InvalidArchDbrTypeError(BaseMgmtError):
    """Exception for when the arch dbr type is invalid."""

    def __init__(self, new_type: str) -> None:
        """Error for when the rename type is invalid.

        Args:
            new_type (str): The invalid arch dbr type.
        """
        super().__init__(f"Invalid arch dbr type {new_type}.")
        self.new_type = new_type


def archdbrtype_from_str(value: str) -> ArchDbrType:
    """Convert a string to a ArchDbrType.

    Args:
        value (str): The value to convert.

    Returns:
        ArchDbrType: The ArchDbrType.

    Raises:
        InvalidArchDbrTypeError: If the value is invalid.
    """
    for t in ArchDbrType:
        if t.name.lower() == value.lower():
            return t
    raise InvalidArchDbrTypeError(value)


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

    basic_commands.pause(archiver_fqdn, pvs)
    # Action
    LOG.info("Changing type of the PVs %s to %s", pvs, new_type)

    LOG.info("Using archiver %s", archiver.info)

    try:
        change_type_results = [archiver.change_type(pv, new_type) for pv in pvs]
    except HTTPError as e:
        LOG.error("Error changing type of PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error changing type of PVs.", exc_info=True)
        raise RequestHTTPError(e) from e

    # Validate output
    validate_operation_results(pvs, [cast("OperationResult", result) for result in change_type_results], "change type")
    basic_commands.resume(archiver_fqdn, pvs)
