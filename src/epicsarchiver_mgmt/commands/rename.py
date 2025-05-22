"""Rename PVs in the archiver."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus
from requests import HTTPError

from epicsarchiver_mgmt.archiver.mgmt import (
    ArchiverMgmt,
    OperationResult,
    Storage,
)
from epicsarchiver_mgmt.commands.validation import (
    RequestHTTPError,
    validate_not_same,
    validate_operation_results,
    validate_pvs_status,
)
from epicsarchiver_mgmt.mgmt_exception import BaseMgmtError

LOG: logging.Logger = logging.getLogger(__name__)

SIZE_KEY = "Estimated storage rate (MB/day)"
MAX_STORAGE_MB = 1000


def _pause_pvs(archivers: list[ArchiverMgmt], pvs: list[str]) -> None:
    try:
        # pause all the pvs
        pause_results = [(archivers[i % len(archivers)]).pause_pv(pv) for i, pv in enumerate(pvs)]

        validate_operation_results(
            pvs,
            pause_results,
            "paused",
        )

    except HTTPError as e:
        LOG.error("Error pausing PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error pausing PVs.", exc_info=True)
        raise RequestHTTPError(e) from e


def rename(archiver_fqdns: list[str], renames: list[tuple[str, str]]) -> None:
    """Rename PVs in the archiver, runs in parallel on multiple archivers.

    Args:
        archiver_fqdns (list[str]): The urls of the archivers.
        renames (list[tuple[str, str]]): The PVs to rename.

    Raises:
        RequestHTTPError: If there is an error renaming the PVs.
    """
    # Validate input
    archiver_info = ArchiverMgmtInfo(archiver_fqdns[0])
    validate_not_same(renames)
    validate_pvs_status(
        archiver_info,
        [old_pv for old_pv, _new_pv in renames],
        [
            ArchivingStatus.BeingArchived,
            ArchivingStatus.Paused,
        ],
    )
    validate_pvs_status(
        archiver_info,
        [new_pv for _old_pv, new_pv in renames],
        [
            ArchivingStatus.NotBeingArchived,
        ],
    )

    # Action
    LOG.info("Renaming PVs %s", renames)

    archivers = [ArchiverMgmt(archiver_fqdn) for archiver_fqdn in archiver_fqdns]

    LOG.info("Using archivers %s", [archiver.info for archiver in archivers])

    _pause_pvs(archivers, [old_pv for old_pv, _new_pv in renames])
    try:
        # rename all the pvs, this can take a long time so we do it in parallel
        rename_results = _parallel_execute_rename(archivers, renames)
    except HTTPError as e:
        LOG.error("Error Renaming PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error Renaming PVs.", exc_info=True)
        raise RequestHTTPError(e) from e

    # Validate output
    validate_operation_results(
        [new_pv for _old_pv, new_pv in renames],
        rename_results,
        "renamed",
    )


def _parallel_execute_rename(archivers: list[ArchiverMgmt], renames: list[tuple[str, str]]) -> list[OperationResult]:
    def rename_pv_task(task_input: tuple[ArchiverMgmt, str, str]) -> OperationResult:
        archiver, old_pv, new_pv = task_input
        return archiver.rename_pv(old_pv, new_pv)

    with ThreadPoolExecutor(max_workers=len(archivers)) as executer:
        executer_input = [(archivers[i % len(archivers)], old_pv, new_pv) for i, (old_pv, new_pv) in enumerate(renames)]
        return list(executer.map(rename_pv_task, executer_input))


class TooMuchStoredDataError(BaseMgmtError):
    """Exception for when the old PV has a lot of data stored."""

    def __init__(self, pv: str, storage: float) -> None:
        """Error for when the old PV has a lot of stored data.

        Args:
            pv (str): The PV.
            storage (float): The storage.
        """
        super().__init__(f"Old PV {pv} has {storage} MB data stored. Manual intervention required.")
        self.pv = pv
        self.storage = storage


def validate_size(archiver: ArchiverMgmt, old_pvs: list[str], max_storage: float = MAX_STORAGE_MB) -> None:
    """Validate the old PVs are not too large.

    Args:
        archiver (ArchiverMgmt): The archiver.
        old_pvs (list[str]): The PVs to check.
        max_storage (float): The maximum storage allowed in MB per day.

    Raises:
        TooMuchStoredDataError: If the old and new PVs are the same.
    """
    for old_pv in old_pvs:
        pv_details = archiver.get_pv_details(old_pv)
        for detail in pv_details:
            if detail["name"] == SIZE_KEY and float(detail["value"]) > max_storage:
                raise TooMuchStoredDataError(old_pv, float(detail["value"]))


def rename_and_append(
    archiver_fqdns: list[str], renames: list[tuple[str, str]], storage: Storage = Storage.MTS
) -> None:
    """Rename and append PVs in the archiver, runs in parallel on multiple archivers.

    Args:
        archiver_fqdns (list[str]): The urls of the archivers.
        renames (list[tuple[str, str]]): The PVs to rename.
        storage (Storage): The storage to consolidate the data first.

    Raises:
        RequestHTTPError: If there is an error renaming the PVs.
    """
    # Validate input
    archiver_info = ArchiverMgmtInfo(archiver_fqdns[0])
    validate_not_same(renames)
    validate_pvs_status(
        archiver_info,
        [old_pv for old_pv, _new_pv in renames],
        [
            ArchivingStatus.BeingArchived,
            ArchivingStatus.Paused,
        ],
    )
    validate_pvs_status(
        archiver_info,
        [new_pv for _old_pv, new_pv in renames],
        [
            ArchivingStatus.BeingArchived,
            ArchivingStatus.Paused,
        ],
    )

    # Action
    LOG.info("Renaming and Appending PVs %s", renames)

    archivers = [ArchiverMgmt(archiver_fqdn) for archiver_fqdn in archiver_fqdns]

    LOG.info("Using archivers %s", [archiver.info for archiver in archivers])

    _pause_pvs(archivers, [old_pv for old_pv, _new_pv in renames] + [new_pv for _old_pv, new_pv in renames])

    try:
        # rename all the pvs, this can take a long time so we do it in parallel
        rename_results = _parallel_execute_rename_and_append(archivers, renames, storage)
    except HTTPError as e:
        LOG.error("Error Renaming and Appending PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error Renaming and Appending PVs.", exc_info=True)
        raise RequestHTTPError(e) from e

    # Validate output
    validate_operation_results(
        [new_pv for _old_pv, new_pv in renames],
        rename_results,
        "Renamed and Appended",
    )


def _parallel_execute_rename_and_append(
    archivers: list[ArchiverMgmt], renames: list[tuple[str, str]], storage: Storage
) -> list[OperationResult]:
    def rename_pv_task(task_input: tuple[ArchiverMgmt, str, str]) -> OperationResult:
        archiver, old_pv, new_pv = task_input
        return archiver.rename_and_append(old_pv, new_pv, storage)

    with ThreadPoolExecutor(max_workers=len(archivers)) as executer:
        executer_input = [(archivers[i % len(archivers)], old_pv, new_pv) for i, (old_pv, new_pv) in enumerate(renames)]
        return list(executer.map(rename_pv_task, executer_input))
