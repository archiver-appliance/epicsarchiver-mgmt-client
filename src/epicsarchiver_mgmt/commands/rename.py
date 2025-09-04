"""Rename PVs in the archiver."""

from __future__ import annotations

import datetime
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import click
from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus, InfoResultList
from epicsarchiver.retrieval.archiver_retrieval.archiver_retrieval import ArchiverRetrieval
from requests import HTTPError

from epicsarchiver_mgmt.archiver.mgmt import (
    ArchiverMgmt,
    OperationResult,
    Storage,
)
from epicsarchiver_mgmt.commands.basic_commands import PauseCommand, ResumeCommand
from epicsarchiver_mgmt.commands.statuses import get_statuses_from_archiver
from epicsarchiver_mgmt.commands.validation import (
    CONFIRMATION_PROMPT,
    OPERATION_RESULT_OK,
    OPERATION_RESULT_STATUS,
    RequestHTTPError,
    validate_archiver_fqdns,
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
    validate_archiver_fqdns(archiver_fqdns)
    archiver_info = ArchiverMgmtInfo(archiver_fqdns[0])
    validate_not_same(renames)
    # unpack list of pairs into two new lists
    old_pvs, new_pvs = zip(*renames, strict=False)
    old_pv_statuses: InfoResultList = get_statuses_from_archiver(archiver_info, old_pvs)
    new_pv_statuses: InfoResultList = get_statuses_from_archiver(archiver_info, new_pvs)
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

    PauseCommand().run_command(
        archiver_fqdns,
        [pv["pvName"] for pv in old_pv_statuses if pv["status"] == ArchivingStatus.BeingArchived],
        skip_validation=True,
    )

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

    ResumeCommand().run_command(archiver_fqdns, new_pvs)


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


def validate_size(archiver: ArchiverMgmtInfo, pvs: Sequence[str], max_storage: float = MAX_STORAGE_MB) -> None:
    """Validate the old PVs are not too large.

    Args:
        archiver (ArchiverMgmt): The archiver.
        pvs (Sequence[str]): The PVs to check.
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


class DataIsTheSameError(BaseMgmtError):
    """Exception for when the old and new PVs data is the same."""

    def __init__(self, old_pv: str, new_pv: str) -> None:
        """Error for when the old and new PVs data is the same.

        Args:
            old_pv (str): The old PV.
            new_pv (str): The new PV.
        """
        super().__init__(f"Data for {old_pv} and {new_pv} is the same.")
        self.old_pv = old_pv
        self.new_pv = new_pv


def validate_data(archiver: ArchiverMgmtInfo, renames: Sequence[tuple[str, str]]) -> None:
    """Validate the old and new PVs data is not the same.

    Args:
        archiver (ArchiverMgmt): The archiver.
        renames (Sequence[tuple[str, str]]): The PVs to check.

    Raises:
        DataIsTheSameError: If the old and new PVs data is the same.
    """
    arch_ret = ArchiverRetrieval(archiver.hostname)
    now = datetime.datetime.now(tz=datetime.UTC)
    for old_pv, new_pv in renames:
        old_data = arch_ret.get_events(
            old_pv,
            start=datetime.datetime(now.year, 1, 1, tzinfo=datetime.UTC),
            end=now,
        )
        if not old_data:
            LOG.warning("No data found for PV %s", old_pv)
            continue
        new_data = arch_ret.get_events(
            new_pv,
            start=datetime.datetime(now.year, 1, 1, tzinfo=datetime.UTC),
            end=now,
        )
        if not new_data:
            LOG.warning("No data found for PV %s", new_pv)
            continue
        if [(e.val, e.pd_timestamp) for e in old_data] == [(e.val, e.pd_timestamp) for e in new_data]:
            raise DataIsTheSameError(old_pv, new_pv)


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
    validate_archiver_fqdns(archiver_fqdns)
    archiver_info = ArchiverMgmtInfo(archiver_fqdns[0])
    # unpack list of pairs into two new lists
    old_pvs, new_pvs = zip(*renames, strict=False)
    old_pv_statuses: InfoResultList = get_statuses_from_archiver(archiver_info, old_pvs)
    new_pv_statuses: InfoResultList = get_statuses_from_archiver(archiver_info, new_pvs)
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
    validate_data(archiver_info, renames)

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
        PauseCommand().run_command(archiver_fqdns, to_pause_pvs, skip_validation=True)

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
        expected_operation_results={OPERATION_RESULT_STATUS: [OPERATION_RESULT_OK], "addAlias": [OPERATION_RESULT_OK]},
    )

    ResumeCommand().run_command(archiver_fqdns, new_pvs)


def _parallel_execute_rename_and_append(
    archivers: list[ArchiverMgmt], renames: Sequence[tuple[str, str]], storage: Storage
) -> list[OperationResult]:
    def rename_pv_task(task_input: tuple[ArchiverMgmt, str, str]) -> OperationResult:
        archiver, old_pv, new_pv = task_input
        return archiver.rename_and_append(old_pv, new_pv, storage)

    with ThreadPoolExecutor(max_workers=len(archivers)) as executer:
        executer_input = [(archivers[i % len(archivers)], old_pv, new_pv) for i, (old_pv, new_pv) in enumerate(renames)]
        return list(executer.map(rename_pv_task, executer_input))
