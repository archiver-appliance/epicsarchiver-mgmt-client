"""Rename PVs in the archiver."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import click
from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus, InfoResultList
from requests import HTTPError

from epicsarchiver_mgmt.archiver.mgmt import (
    ArchiverMgmt,
    OperationResult,
    Storage,
)
from epicsarchiver_mgmt.commands.validation import (
    CONFIRMATION_PROMPT,
    RequestHTTPError,
    validate_not_same,
    validate_operation_results,
    validate_pvs_status,
)
from epicsarchiver_mgmt.mgmt_exception import BaseMgmtError

if TYPE_CHECKING:
    from collections.abc import Sequence

LOG: logging.Logger = logging.getLogger(__name__)

SIZE_KEY = "Estimated storage rate (MB/day)"
NO_SIZE_VAL = "Not enough info"
MAX_STORAGE_MB = 1000


def _pause_pvs(archivers: list[ArchiverMgmt], pvs: list[str]) -> None:
    try:
        # pause all the pvs
        pause_results = [(archivers[i % len(archivers)]).pause_pv(pv) for i, pv in enumerate(pvs)]

        validate_operation_results(pvs, pause_results, "paused")

    except HTTPError as e:
        LOG.error("Error pausing PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error pausing PVs.", exc_info=True)
        raise RequestHTTPError(e) from e


def rename(archiver_fqdns: list[str], renames: Sequence[tuple[str, str]], *, dry_run: bool = False) -> None:
    """Rename PVs in the archiver, runs in parallel on multiple archivers.

    Args:
        archiver_fqdns (list[str]): The urls of the archivers.
        renames (Sequence[tuple[str, str]]): The PVs to rename.
        dry_run (bool): Whether to do a dry run or not.

    Raises:
        RequestHTTPError: If there is an error renaming the PVs.
    """
    # Validate input
    archiver_info = ArchiverMgmtInfo(archiver_fqdns[0])
    validate_not_same(renames)
    old_pvs = [old_pv for old_pv, _new_pv in renames]
    new_pvs = [new_pv for _old_pv, new_pv in renames]
    old_pv_statuses: InfoResultList = archiver_info.get_pv_status(",".join(old_pvs))
    new_pv_statuses: InfoResultList = archiver_info.get_pv_status(",".join(new_pvs))
    validate_pvs_status(
        archiver_info,
        old_pvs,
        [
            ArchivingStatus.BeingArchived,
            ArchivingStatus.Paused,
        ],
        existing_status_infos=old_pv_statuses,
    )
    validate_pvs_status(
        archiver_info,
        new_pvs,
        [
            ArchivingStatus.NotBeingArchived,
        ],
        existing_status_infos=new_pv_statuses,
    )
    validate_size(
        archiver_info,
        old_pvs,
    )

    # Action
    LOG.info("Renaming PVs %s", renames)

    archivers = [ArchiverMgmt(archiver_fqdn) for archiver_fqdn in archiver_fqdns]

    LOG.info("Using archivers %s", [archiver.info for archiver in archivers])

    if dry_run:
        LOG.info("Dry run, not executing.")
        return

    click.confirm(CONFIRMATION_PROMPT, abort=True)

    _pause_pvs(archivers, [pv["pvName"] for pv in old_pv_statuses if pv["status"] == ArchivingStatus.BeingArchived])

    try:
        # rename all the pvs, this can take a long time so we do it in parallel
        rename_results = _parallel_execute_rename(archivers, renames)
    except HTTPError as e:
        LOG.error("Error Renaming PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error Renaming PVs.", exc_info=True)
        raise RequestHTTPError(e) from e

    # Validate output
    validate_operation_results(
        new_pvs,
        rename_results,
        "renamed",
    )


def _parallel_execute_rename(
    archivers: list[ArchiverMgmt], renames: Sequence[tuple[str, str]]
) -> list[OperationResult]:
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


def validate_size(archiver: ArchiverMgmtInfo, pvs: list[str], max_storage: float = MAX_STORAGE_MB) -> None:
    """Validate the old PVs are not too large.

    Args:
        archiver (ArchiverMgmt): The archiver.
        pvs (list[str]): The PVs to check.
        max_storage (float): The maximum storage allowed in MB per day.

    Raises:
        TooMuchStoredDataError: If the old and new PVs are the same.
    """
    for pv in pvs:
        pv_details = archiver.get_pv_details(pv)
        for detail in pv_details:
            if detail["name"] != SIZE_KEY:
                continue
            size_value = detail["value"]
            if size_value == NO_SIZE_VAL:
                continue
            pv_storage = float(size_value)
            if pv_storage > max_storage:
                raise TooMuchStoredDataError(pv, pv_storage)


def rename_and_append(
    archiver_fqdns: list[str],
    renames: Sequence[tuple[str, str]],
    storage: Storage = Storage.MTS,
    *,
    dry_run: bool = False,
) -> None:
    """Rename and append PVs in the archiver, runs in parallel on multiple archivers.

    Args:
        archiver_fqdns (list[str]): The urls of the archivers.
        renames (Sequence[tuple[str, str]]): The PVs to rename.
        storage (Storage): The storage to consolidate the data first.
        dry_run (bool): Whether to do a dry run or not.

    Raises:
        RequestHTTPError: If there is an error renaming the PVs.
    """
    # Validate input
    archiver_info = ArchiverMgmtInfo(archiver_fqdns[0])
    old_pvs = [old_pv for old_pv, _new_pv in renames]
    new_pvs = [new_pv for _old_pv, new_pv in renames]
    old_pv_statuses: InfoResultList = archiver_info.get_pv_status(",".join(old_pvs))
    new_pv_statuses: InfoResultList = archiver_info.get_pv_status(",".join(new_pvs))
    validate_not_same(renames)
    validate_pvs_status(
        archiver_info,
        old_pvs,
        [
            ArchivingStatus.BeingArchived,
            ArchivingStatus.Paused,
        ],
        existing_status_infos=old_pv_statuses,
    )
    validate_pvs_status(
        archiver_info,
        new_pvs,
        [
            ArchivingStatus.BeingArchived,
            ArchivingStatus.Paused,
        ],
        existing_status_infos=new_pv_statuses,
    )
    validate_size(
        archiver_info,
        old_pvs,
    )
    validate_size(
        archiver_info,
        new_pvs,
    )

    # Action
    LOG.info("Renaming and Appending PVs %s", renames)

    archivers = [ArchiverMgmt(archiver_fqdn) for archiver_fqdn in archiver_fqdns]

    LOG.info("Using archivers %s", [archiver.info for archiver in archivers])

    if dry_run:
        LOG.info("Dry run, not executing.")
        return

    click.confirm(CONFIRMATION_PROMPT, abort=True)

    to_pause_pvs = [pv["pvName"] for pv in old_pv_statuses if pv["status"] == ArchivingStatus.BeingArchived] + [
        pv["pvName"] for pv in new_pv_statuses if pv["status"] == ArchivingStatus.BeingArchived
    ]
    if not to_pause_pvs:
        LOG.info("No PVs to pause, skipping.")
    else:
        LOG.info("Pausing PVs %s", to_pause_pvs)
        _pause_pvs(archivers, to_pause_pvs)

    try:
        # rename all the pvs, this can take a long time so we do it in parallel
        rename_results = _parallel_execute_rename_and_append(archivers, renames, storage)
    except HTTPError as e:
        LOG.error("Error Renaming and Appending PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error Renaming and Appending PVs.", exc_info=True)
        raise RequestHTTPError(e) from e

    # Validate output
    validate_operation_results(
        new_pvs,
        rename_results,
        "Renamed and Appended",
    )


def _parallel_execute_rename_and_append(
    archivers: list[ArchiverMgmt], renames: Sequence[tuple[str, str]], storage: Storage
) -> list[OperationResult]:
    def rename_pv_task(task_input: tuple[ArchiverMgmt, str, str]) -> OperationResult:
        archiver, old_pv, new_pv = task_input
        return archiver.rename_and_append(old_pv, new_pv, storage)

    with ThreadPoolExecutor(max_workers=len(archivers)) as executer:
        executer_input = [(archivers[i % len(archivers)], old_pv, new_pv) for i, (old_pv, new_pv) in enumerate(renames)]
        return list(executer.map(rename_pv_task, executer_input))
