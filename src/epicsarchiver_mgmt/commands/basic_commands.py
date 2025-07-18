"""Basic commands to modify PVs in the archiver."""

from __future__ import annotations

import logging
from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus
from requests import HTTPError

from epicsarchiver_mgmt.archiver.mgmt import (
    ArchiverMgmt,
    OperationResult,
)
from epicsarchiver_mgmt.commands.validation import (
    OPERATION_RESULT_STATUS,
    RequestHTTPError,
    validate_operation_results,
    validate_pvs_status,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

LOG: logging.Logger = logging.getLogger(__name__)

PAUSE_EXPECTED_STATUS = {OPERATION_RESULT_STATUS: ["ok", "no"]}


@dataclass
class BasicCommand:
    """Basic command to modify PVs in the archiver."""

    command_name: str
    expected_statuses: list[ArchivingStatus]
    expected_operation_results: dict[str, list[str]] | None = None

    @abstractmethod
    def __call__(
        self,
        archiver: ArchiverMgmt,
        pv: str,
    ) -> OperationResult:
        """Command to execute.

        Args:
            archiver (ArchiverMgmt): The archiver to use.
            pv (str): The PV to modify.

        Returns:
            OperationResult: The result of the command.
        """
        msg = "Subclasses must implement this method."
        raise NotImplementedError(msg)

    def run_command(
        self,
        archiver_fqdn: str,
        pvs: Sequence[str],
        *,
        skip_validation: bool = False,
    ) -> None:
        """Basic command to modify PVs in the archiver.

        Args:
            archiver_fqdn (str): The url of the archiver.
            pvs (list[str]): The PVs to change.
            skip_validation (bool): Whether to skip validation of the PVs status.

        Raises:
            RequestHTTPError: If there is an error changing the PVs.
        """
        # Validate input
        archiver_info = ArchiverMgmtInfo(archiver_fqdn)
        if not skip_validation:
            validate_pvs_status(archiver_info, pvs, self.expected_statuses)

        # Action
        LOG.info("%s PVs %s", self.command_name, pvs)

        archiver = ArchiverMgmt(archiver_fqdn)

        LOG.info("Using archiver %s", archiver.info)

        try:
            command_results = [self(archiver, pv) for pv in pvs]
        except HTTPError as e:
            LOG.error("Error %s PVs: %s", self.command_name, str(e))  # noqa: TRY400
            LOG.debug("Error %s PVs.", self.command_name, exc_info=True)
            raise RequestHTTPError(e) from e

        # Validate output
        validate_operation_results(
            pvs,
            command_results,
            f"{self.command_name} done",
            expected_operation_results=self.expected_operation_results,
        )


class PauseCommand(BasicCommand):
    """Pause command to modify PVs in the archiver."""

    def __init__(self) -> None:
        """Initialize the PauseCommand class."""
        super().__init__(
            command_name="Pausing",
            expected_statuses=[
                ArchivingStatus.BeingArchived,
                ArchivingStatus.NotBeingArchived,
                ArchivingStatus.Paused,
            ],
        )

    def __call__(
        self,
        archiver: ArchiverMgmt,
        pv: str,
    ) -> OperationResult:
        """Pause PV in the archiver.

        Args:
            archiver (ArchiverMgmt): The archiver to use.
            pv (str): The PV to pause.

        Returns:
            OperationResult: The result of the command.
        """
        return archiver.pause_pv(pv)


class ResumeCommand(BasicCommand):
    """Resume command to modify PVs in the archiver."""

    def __init__(self) -> None:
        """Initialize the ResumeCommand class."""
        super().__init__(
            command_name="Resuming",
            expected_statuses=[
                ArchivingStatus.Paused,
            ],
        )

    def __call__(
        self,
        archiver: ArchiverMgmt,
        pv: str,
    ) -> OperationResult:
        """Resume PV in the archiver.

        Args:
            archiver (ArchiverMgmt): The archiver to use.
            pv (str): The PV to resume.

        Returns:
            OperationResult: The result of the command.
        """
        return archiver.resume_pv(pv)


class DeleteCommand(BasicCommand):
    """Delete command to modify PVs in the archiver."""

    def __init__(self) -> None:
        """Initialize the DeleteCommand class."""
        super().__init__(
            command_name="Deleting",
            expected_statuses=[
                ArchivingStatus.Paused,
            ],
        )

    def __call__(
        self,
        archiver: ArchiverMgmt,
        pv: str,
    ) -> OperationResult:
        """Delete PV in the archiver.

        Args:
            archiver (ArchiverMgmt): The archiver to use.
            pv (str): The PV to delete.

        Returns:
            OperationResult: The result of the command.
        """
        return archiver.delete_pv(pv)


class AbortCommand(BasicCommand):
    """Abort command to modify PVs in the archiver."""

    def __init__(self) -> None:
        """Initialize the AbortCommand class."""
        super().__init__(
            command_name="Aborting",
            expected_statuses=[
                ArchivingStatus.BeingArchived,
            ],
            expected_operation_results=PAUSE_EXPECTED_STATUS,
        )

    def __call__(
        self,
        archiver: ArchiverMgmt,
        pv: str,
    ) -> OperationResult:
        """Abort archiving PV in the archiver.

        Args:
            archiver (ArchiverMgmt): The archiver to use.
            pv (str): The PV to abort.

        Returns:
            OperationResult: The result of the command.
        """
        return archiver.abort_pv(pv)
